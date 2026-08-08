# brickles.py -- break-out for MicroPython
#
# A rewrite of BRICKLES.PAS (Byte Works, 1990; ORCA/Pascal 1.2, Apple IIgs)
# for any display object exposing the framebuf API, with the paddle on an ADC.
#
# The display must provide:
#     .width, .height          screen size in pixels
#     .fill_rect(x, y, w, h, c)
#     .text(s, x, y, c)        8x8 font
#     .show()                  flush the buffer
# ssd1306, st7789, ili9341, pyb.LCD160CR wrappers and framebuf.FrameBuffer
# subclasses all qualify.
#
# Geometry is derived from the display size at construction time, so the same
# code runs on a 128x64 OLED and a 240x240 TFT. Only the *shape* of the
# original is preserved, not its 320x200 pixel constants.

try:
    from utime import ticks_ms, ticks_diff, sleep_ms
except ImportError:                     # CPython, for testing on a desktop
    import time as _time

    def ticks_ms():
        return int(_time.monotonic() * 1000)

    def ticks_diff(a, b):
        return a - b

    def sleep_ms(ms):
        _time.sleep(ms / 1000)

from urandom import getrandbits


# ---------------------------------------------------------------- palettes --
# Index 0 is always the background. 1..5 are the brick rows, matching the
# colors[] array in DrawBricks.

BG, BRICK1, BRICK2, BRICK3, BRICK4, BRICK5, PADDLE, BALL, TEXT, FRAME = range(10)

PALETTE_MONO = [0] + [1] * 9


def rgb565(r, g, b):
    """Pack 8-bit RGB into a big-endian RGB565 word."""
    v = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return ((v & 0xFF) << 8) | (v >> 8)


PALETTE_COLOR = [
    rgb565(0, 0, 0),        # background
    rgb565(255, 80, 80),    # brick row 1
    rgb565(255, 160, 40),   # brick row 2
    rgb565(240, 230, 60),   # brick row 3
    rgb565(80, 220, 100),   # brick row 4
    rgb565(90, 160, 255),   # brick row 5
    rgb565(255, 255, 255),  # paddle
    rgb565(255, 255, 255),  # ball
    rgb565(200, 200, 200),  # text
    rgb565(120, 120, 120),  # menu frame
]

ROWS = 5
COLUMNS = 10
FRAME_MS = 30                           # replaces the 60ths-of-a-second timer


class Brickles:

    def __init__(self, display, adc, button=None, palette=PALETTE_MONO,
                 frame_ms=FRAME_MS, speed=None):
        """display  -- framebuf-like object
        adc      -- ADC object, or any callable returning a raw reading
        button   -- optional Pin, active low, for 'click'
        palette  -- 10 colour values; see PALETTE_MONO / PALETTE_COLOR
        frame_ms -- ball update period; lower is faster
        speed    -- vertical ball speed in px/frame; None = derive from height
        """
        self.d = display
        self.button = button
        self.pal = palette
        self.frame_ms = frame_ms
        # Displays with a font other than 8x8 advertise it; framebuf is 8x8.
        self.cw = getattr(display, "char_w", 8)
        self.ch = getattr(display, "char_h", 8)

        # -- input -------------------------------------------------------
        if callable(adc):
            self._raw, self._full = adc, 65535
        elif hasattr(adc, "read_u16"):  # machine.ADC
            self._raw, self._full = adc.read_u16, 65535
        else:                           # pyb.ADC
            self._raw, self._full = adc.read, 4095

        # -- geometry, scaled from the display size ----------------------
        W = self.W = display.width
        H = self.H = display.height

        self.text_y = H - self.ch       # letterY
        self.brick_w = W // COLUMNS     # width
        self.spacing = max(3, H // 25)  # spacing
        self.thickness = max(2, self.spacing - 2)   # thickness
        self.start_height = self.spacing * (ROWS + 1)   # startHeight

        self.paddle_w = max(16, W // 6)             # paddleWidth
        self.paddle_h = max(2, H // 48)             # paddleHeight
        self.paddle_y = self.text_y - 6 - self.paddle_h  # paddleY
        self.max_x = W - self.paddle_w              # maxX

        self.ball_size = max(2, H // 60)
        self.br = self.ball_size // 2               # balldx / balldy

        self.speed = speed if speed else max(1, H // 70)  # speed
        self.easy = self.speed                      # easy
        self.hard = self.speed + 1                  # hard
        zone = self.paddle_w // 5                   # area1..area4
        self.areas = (zone, zone * 2, zone * 3, zone * 4)

        # -- state -------------------------------------------------------
        self.score = 0
        self.balls = 0
        self.level = 1
        self.brick_y = self.start_height
        self.num_bricks = 0
        self.x = self.y = 0
        self.dx = self.dy = 0
        self.paddle_pos = 0
        # Row 0 is a dummy so rows are 1-based, as in the Pascal. Columns 0
        # and COLUMNS+1 are the permanent False sentinels the collision code
        # relies on -- exactly the stillThere[1,0] / stillThere[1,columns1]
        # trick in DrawBricks.
        self.still = [[False] * (COLUMNS + 2) for _ in range(ROWS + 1)]

    # ------------------------------------------------------------- input --

    def read_paddle(self):
        """Averaged, scaled pot reading -> left edge of the paddle."""
        total = 0
        for _ in range(4):
            total += self._raw()
        return (total >> 2) * self.max_x // self._full

    def clicked(self):
        """True on a button release. Always False if no button is fitted."""
        if self.button is None:
            return False
        if self.button.value():
            return False
        while not self.button.value():
            sleep_ms(10)
        return True

    # ----------------------------------------------------------- drawing --

    def draw_paddle(self, position, color):
        """DrawPaddle. Colour BG erases."""
        self.d.fill_rect(position, self.paddle_y, self.paddle_w,
                         self.paddle_h, self.pal[color])

    def move_paddle(self):
        """MovePaddle -- erase and redraw only when the pot has moved."""
        pos = self.read_paddle()
        if pos != self.paddle_pos:
            self.draw_paddle(self.paddle_pos, BG)
            self.paddle_pos = pos
            self.draw_paddle(pos, PADDLE)

    def draw_brick(self, row, column, color):
        """DrawBrick. The 1px gap is the separator line the original drew."""
        x = (column - 1) * self.brick_w
        bottom = self.brick_y - row * self.spacing + self.spacing
        self.d.fill_rect(x, bottom - self.thickness, self.brick_w - 1,
                         self.thickness, self.pal[color])

    def draw_bricks(self):
        """DrawBricks."""
        self.num_bricks = ROWS * COLUMNS
        for row in range(1, ROWS + 1):
            for column in range(1, COLUMNS + 1):
                self.draw_brick(row, column, row)
                self.still[row][column] = True
            self.still[row][0] = False
            self.still[row][COLUMNS + 1] = False

    def write_balls(self):
        """WriteBalls. Trailing spaces erase the old digits."""
        self.d.text("Balls:%d " % self.balls, self.W - 9 * self.cw,
                    self.text_y, self.pal[TEXT])

    def write_score(self):
        """WriteScore."""
        self.d.text("%d    " % self.score, 0, self.text_y, self.pal[TEXT])

    def draw_ball(self, color=BALL):
        """DrawBall -- also used to erase, by passing BG."""
        self.d.fill_rect(self.x - self.br, self.y - self.br,
                         self.ball_size, self.ball_size, self.pal[color])

    # -------------------------------------------------------- game phases --

    def start_ball(self):
        """StartBall. getrandbits replaces the eventWhen parity trick."""
        self.dx = -self.easy if getrandbits(1) else self.easy
        self.x = self.W // 4 + getrandbits(1) * (self.W // 2)
        self.dy = self.speed
        self.y = self.start_height + self.spacing * ROWS + 4
        self.draw_ball()

    def wait_for_click(self):
        """WaitForClick. With no button fitted this is a fixed pause."""
        msg_y = self.H // 2
        self.d.text("Ready...", (self.W - 8 * self.cw) // 2, msg_y,
                    self.pal[TEXT])
        self.d.show()
        if self.button is None:
            deadline = ticks_ms() + 1200
            while ticks_diff(deadline, ticks_ms()) > 0:
                self.move_paddle()
                self.d.show()
                sleep_ms(self.frame_ms)
        else:
            while not self.clicked():
                self.move_paddle()
                self.d.show()
                sleep_ms(self.frame_ms)
        self.d.fill_rect(0, msg_y, self.W, self.ch, self.pal[BG])

    def play_a_game(self):
        """PlayAGame. The pot selects PLAY or QUIT, the button confirms.
        Returns True to play, False to quit. Always True with no button."""
        if self.button is None:
            return True

        w, h = 6 * self.cw, self.ch + 4
        left = (self.W - w) // 2
        top1 = self.H // 2 - 16
        top2 = self.H // 2 + 2
        selected = -1

        while True:
            choice = 0 if self.read_paddle() * 2 < self.max_x else 1
            if choice != selected:
                selected = choice
                for i, (label, top) in enumerate((("PLAY", top1),
                                                  ("QUIT", top2))):
                    c = self.pal[TEXT if i == choice else FRAME]
                    self.d.fill_rect(left - 2, top - 2, w + 4, h + 4,
                                     self.pal[BG])
                    self.d.fill_rect(left, top, w, h, self.pal[BG])
                    self.d.text(label, left + self.cw, top + 2, c)
                    self.d.fill_rect(left, top, w, 1, c)
                    self.d.fill_rect(left, top + h - 1, w, 1, c)
                    self.d.fill_rect(left, top, 1, h, c)
                    self.d.fill_rect(left + w - 1, top, 1, h, c)
                self.d.show()
            if self.clicked():
                self.d.fill_rect(left - 2, top1 - 2, w + 4,
                                 top2 - top1 + h + 4, self.pal[BG])
                return choice == 0
            sleep_ms(self.frame_ms)

    def hit_brick(self, row, column):
        """HitBrick."""
        self.still[row][column] = False
        self.draw_brick(row, column, BG)
        self.score += (row + self.level) * 5
        self.write_score()
        self.num_bricks -= 1
        if self.num_bricks == 0:        # cleared the screen: bonus ball,
            self.draw_ball(BG)          # bricks move one row closer
            self.balls += 1
            self.write_balls()
            self.brick_y += self.spacing
            self.level += 1
            self.draw_bricks()
            self.wait_for_click()
            self.start_ball()

    def check_bricks(self):
        """CheckBricks. Same divide-and-remainder scheme as the original:
        the ball's position maps straight onto a row and column, so no
        rectangle-by-rectangle search is needed."""
        row = (self.brick_y - self.y + self.spacing) // self.spacing
        disp_y = (self.brick_y - self.y) % self.spacing
        if not (1 <= row <= ROWS and disp_y <= self.thickness):
            return

        column = self.x // self.brick_w + 1
        if column > COLUMNS:
            column = COLUMNS
        disp_x = self.x % self.brick_w

        if self.still[row][column]:
            self.hit_brick(row, column)
            if disp_y in (0, self.thickness):
                self.dy = -self.dy      # hit a face
            else:
                self.dx = -self.dx      # hit an end
        elif disp_y in (0, self.thickness):
            if disp_x == 0:
                if self.still[row][column - 1]:
                    self.hit_brick(row, column - 1)
                    self.dy = -self.dy
            elif disp_x == self.brick_w:
                if self.still[row][column + 1]:
                    self.hit_brick(row, column + 1)
                    self.dy = -self.dy

    def get_a_new_ball(self):
        """GetANewBall."""
        self.balls -= 1
        self.write_balls()
        if self.balls:
            self.draw_ball(BG)
            self.wait_for_click()
            self.start_ball()

    def move_ball(self):
        """MoveBall."""
        self.draw_ball(BG)              # erase where it was

        self.x += self.dx
        if self.x < self.br:
            self.x = self.br
            self.dx = -self.dx
        elif self.x > self.W - self.br - 1:
            self.x = self.W - self.br - 1
            self.dx = -self.dx

        self.y += self.dy
        if self.y < self.br:
            self.y = self.br
            self.dy = -self.dy
        elif self.y >= self.paddle_y:
            if (self.x < self.paddle_pos or
                    self.x > self.paddle_pos + self.paddle_w):
                self.get_a_new_ball()
                return
            # Five zones across the paddle give the player spin control:
            # hard slice at the tips, dead straight in the middle.
            px = self.x - self.paddle_pos
            a1, a2, a3, a4 = self.areas
            if px < a1:
                self.dx = -self.hard
            elif px < a2:
                self.dx = -self.easy
            elif px < a3:
                self.dx = 0
            elif px < a4:
                self.dx = self.easy
            else:
                self.dx = self.hard
            self.dy = -self.dy
            self.y = self.paddle_y

        self.draw_ball()                # draw where it is now

    def init_screen(self):
        """InitScreen."""
        self.d.fill_rect(0, 0, self.W, self.H, self.pal[BG])
        self.brick_y = self.start_height
        self.draw_bricks()
        self.paddle_pos = self.read_paddle()
        self.draw_paddle(self.paddle_pos, PADDLE)
        self.score = 0
        self.write_score()
        self.balls = 3
        self.write_balls()

    # -------------------------------------------------------- main program --

    def run(self):
        """The main body of the Pascal program."""
        self.level = 1
        self.init_screen()
        self.d.show()

        while self.play_a_game():
            self.init_screen()
            self.start_ball()
            last = ticks_ms()
            while self.balls:
                now = ticks_ms()
                if ticks_diff(now, last) >= self.frame_ms:
                    last = now
                    self.move_ball()
                    if self.balls:
                        self.check_bricks()
                self.move_paddle()
                self.d.show()
                sleep_ms(1)             # don't spin the bus flat out
            self.draw_ball(BG)
            self.d.text("GAME OVER", (self.W - 9 * self.cw) // 2, self.H // 2,
                        self.pal[TEXT])
            self.d.show()
            sleep_ms(2000)


# --------------------------------------------------------------- wiring up --

def demo():
    """Example: Pyboard, SSD1306 on I2C(1), pot on X1, button on X2.
    Change the three lines under 'hardware' for your own board."""
    from machine import Pin, I2C, ADC
    import ssd1306

    # hardware
    i2c = I2C(1)
    pot = ADC(Pin("X1"))
    button = Pin("X2", Pin.IN, Pin.PULL_UP)

    display = ssd1306.SSD1306_I2C(128, 64, i2c)
    Brickles(display, pot, button, PALETTE_MONO).run()


if __name__ == "__main__":
    demo()
