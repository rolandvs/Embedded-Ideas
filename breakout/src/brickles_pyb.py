# brickles_pyb.py -- Brickles on a Pyboard v1.1 + LCD160CR skin
#
#   >>> import brickles_pyb
#   >>> brickles_pyb.play()              # pot on Y12, USR switch to click
#   >>> brickles_pyb.play(touch=True)    # no wiring at all: finger + tap
#
# The LCD160CR is not a framebuf device. It is a smart display: you send it
# drawing commands over I2C and it renders them itself. That suits this game
# perfectly, because the original was written for a machine that also could
# not afford to repaint the whole screen -- it only ever erases and redraws
# the paddle and the ball. So instead of a 40KB RGB565 framebuffer, this
# adapter turns each fill_rect into one LCD160CR rect command and makes
# show() a no-op.

import lcd160cr
from lcd160cr import LCD160CR
import pyb

from brickles import Brickles, rgb565     # noqa: F401  (rgb565 re-exported)


# ------------------------------------------------------------------ display --

class LCDDisplay:
    """Adapts LCD160CR to the small framebuf-like API brickles.py expects."""

    # Font metrics are in the display's firmware and are not published, so
    # these are deliberate over-estimates. Guessing too WIDE only costs a
    # little layout margin; guessing too narrow lets a string run past the
    # right edge, which wraps the cursor and scrolls the screen.
    char_w = 8
    char_h = 10

    def __init__(self, lcd):
        self.lcd = lcd
        self.width = lcd.w
        self.height = lcd.h
        self._pen = None                # cache: a pen change costs an I2C round
        self._fg = None                 # trip, and most frames reuse one colour
        lcd.set_font(1, 0, 0, 0, 0)     # scroll=0: never soft-scroll on wrap
        lcd.set_scroll(False)

    def fill_rect(self, x, y, w, h, c):
        if w <= 0 or h <= 0:
            return
        if c != self._pen:
            self.lcd.set_pen(c, c)      # line and fill the same -> solid block
            self._pen = c
        self.lcd.rect(x, y, w, h)       # rect() clips, so off-screen is safe

    def text(self, s, x, y, c):
        # Hard backstop: truncate so the cursor can never reach the right
        # margin. Without this, one long string scrolls the whole playfield.
        room = (self.width - 1 - x) // self.char_w
        if room <= 0:
            return
        if len(s) > room:
            s = s[:room]
        if c != self._fg:
            self.lcd.set_text_color(c, 0)
            self._fg = c
        self.lcd.set_pos(x, y)
        self.lcd.write(s)

    def show(self):
        pass                            # nothing to flush; drawing is immediate


# -------------------------------------------------------------------- input --

class TouchPaddle:
    """Paddle from the resistive touch panel. Returns a 0..65535 reading,
    which is the scale Brickles expects from a 16-bit ADC."""

    def __init__(self, lcd):
        self.lcd = lcd
        self.last = 32768

    def __call__(self):
        active, x, _ = self.lcd.get_touch()
        if active:
            self.last = min(65535, max(0, x * 65535 // (self.lcd.w - 1)))
        return self.last                # hold position when the finger lifts


class TouchButton:
    """Pin-like object so a screen tap counts as a click."""

    def __init__(self, lcd):
        self.lcd = lcd

    def value(self):
        return 0 if self.lcd.is_touched() else 1


class SwitchButton:
    """Pin-like object wrapping the pyboard's own USR switch."""

    def __init__(self):
        self.sw = pyb.Switch()

    def value(self):
        return 0 if self.sw() else 1


# ----------------------------------------------------------------- palette --

PALETTE = [
    LCD160CR.rgb(0, 0, 0),          # background
    LCD160CR.rgb(255, 70, 70),      # brick row 1
    LCD160CR.rgb(255, 150, 40),     # brick row 2
    LCD160CR.rgb(240, 230, 60),     # brick row 3
    LCD160CR.rgb(70, 220, 100),     # brick row 4
    LCD160CR.rgb(90, 160, 255),     # brick row 5
    LCD160CR.rgb(255, 255, 255),    # paddle
    LCD160CR.rgb(255, 255, 255),    # ball
    LCD160CR.rgb(180, 220, 255),    # text
    LCD160CR.rgb(110, 110, 110),    # menu frame
]


# ------------------------------------------------------------------- launch --

def play(connect="X", pot="Y12", touch=False, brightness=31):
    """connect -- LCD skin position: 'X', 'Y', 'XY' or 'YX'
    pot     -- ADC pin for the paddle; ignored when touch=True
    touch   -- use the screen instead of a pot and switch
    """
    lcd = LCD160CR(connect)
    lcd.set_orient(lcd160cr.LANDSCAPE)          # 160 wide x 128 high
    lcd.set_brightness(brightness)
    lcd.set_pen(0, 0)
    lcd.erase()

    display = LCDDisplay(lcd)

    if touch:
        paddle = TouchPaddle(lcd)
        button = TouchButton(lcd)
    else:
        paddle = pyb.ADC(pyb.Pin(pot))          # 12-bit; Brickles detects that
        button = SwitchButton()

    # 128px tall would derive speed=1, which crawls. 2px/frame at 20ms is
    # about 100px/sec vertically -- roughly the feel of the original.
    game = Brickles(display, paddle, button, PALETTE, frame_ms=20, speed=2)
    game.run()


if __name__ == "__main__":
    play(touch=True)