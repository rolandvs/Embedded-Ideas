"""
disppong.py

MicroPython port of Z-World's disppong.c (Rabbit / Dynamic C, 2001).
Target: STM32 (pyboard, Nucleo, WeAct "Black Pill"), SSD1306 OLED on I2C1.

I2C1 default pins on every common STM32 board: SCL = PB6, SDA = PB7.
On a pyboard those are the X9 / X10 header pins.

Requires ssd1306.py on the board's filesystem. It is not built in:
    mpremote mip install ssd1306
or copy it from micropython-lib/micropython/drivers/display/ssd1306.

A 16x12 bitmap "ball" bounces inside a drawn box, pulling a grimace
for one frame each time it meets a wall.
"""

import framebuf
from machine import I2C
from time import ticks_ms, ticks_add, ticks_diff, sleep_ms
import ssd1306

# ---------- display geometry ----------
WIDTH = 128
HEIGHT = 64          # 32 also works; everything below derives from this
ADDR = 0x3C          # a few modules answer on 0x3D
I2C_FREQ = 400_000   # 100 kHz makes show() alone cost ~90 ms

# Box edges as absolute coordinates, not widths.
# (The original named these WIDTH/HEIGHT but used them as edges.)
BOX_L = 0
BOX_T = 0
BOX_R = WIDTH - 1
BOX_B = HEIGHT - 1

BALL_W = 16
BALL_H = 12
FRAME_MS = 50

# ---------- 16x12 bitmaps, MSB first, 2 bytes per row ----------
# Byte layout is identical to the Rabbit original, so these are copied
# verbatim. bytearray, not bytes: FrameBuffer demands a writable buffer.

_SMILEY = bytearray(
    b"\x07\xc0"
    b"\x18\x30"
    b"\x30\x18"
    b"\x26\xc8"
    b"\x46\xc4"
    b"\x40\x04"
    b"\x48\x24"
    b"\x48\x24"
    b"\x24\x48"
    b"\x23\x98"
    b"\x18\x30"
    b"\x07\xc0"
)

_WALL = bytearray(
    b"\x07\xc0"
    b"\x18\x30"
    b"\x30\x18"
    b"\x26\xc8"
    b"\x46\xc4"
    b"\x40\x04"
    b"\x40\x04"
    b"\x4f\xe4"
    b"\x20\x08"
    b"\x30\x18"
    b"\x18\x30"
    b"\x07\xc0"
)

SMILEY = framebuf.FrameBuffer(_SMILEY, BALL_W, BALL_H, framebuf.MONO_HLSB)
WALL = framebuf.FrameBuffer(_WALL, BALL_W, BALL_H, framebuf.MONO_HLSB)

# The original's third bitmap, blank[], is gone: fill_rect() erases the
# same 16x12 window for free.


class Pong:
    """One frame of the animation per call to step()."""

    def __init__(self, oled):
        self.oled = oled
        self.px = BOX_L + 1      # current position
        self.py = BOX_T + 1
        self.dx = 2              # current direction
        self.dy = 2
        self.hold = 0            # grimace frames still owed, 1 per axis hit

        oled.fill(0)
        oled.rect(BOX_L, BOX_T, BOX_R - BOX_L + 1, BOX_B - BOX_T + 1, 1)
        oled.blit(SMILEY, self.px, self.py)
        oled.show()

    def _draw(self, x, y, ball):
        # blit() with no key is replace mode, the exact analogue of
        # glXPutBitmap. It only covers its own 16x12 window, so the
        # previous window still has to be cleared.
        self.oled.fill_rect(self.px, self.py, BALL_W, BALL_H, 0)
        self.oled.blit(ball, x, y)
        self.oled.show()

    def step(self):
        # Owe the wall a grimace frame? Hold position and pull the face.
        if self.hold > 0:
            self.hold -= 1
            self._draw(self.px, self.py, WALL)
            return

        # Probe the next position. This move is discarded either way.
        nx = self.px + self.dx
        ny = self.py + self.dy

        if nx < BOX_L + 1 or nx + BALL_W > BOX_R:
            self.dx = -self.dx
            self.hold += 1
        if ny < BOX_T + 1 or ny + BALL_H > BOX_B:
            self.dy = -self.dy
            self.hold += 1

        if self.hold > 0:
            self.hold -= 1           # a corner hit owes two frames
            self._draw(self.px, self.py, WALL)
            return

        # Commit, using the direction as it now stands.
        nx = self.px + self.dx
        ny = self.py + self.dy
        self._draw(nx, ny, SMILEY)
        self.px = nx
        self.py = ny


def main():
    i2c = I2C(1, freq=I2C_FREQ)          # id=1 selects I2C1 and its default pins
    if ADDR not in i2c.scan():
        raise OSError("no SSD1306 at 0x%02X on I2C1" % ADDR)

    oled = ssd1306.SSD1306_I2C(WIDTH, HEIGHT, i2c, addr=ADDR)
    game = Pong(oled)

    next_frame = ticks_add(ticks_ms(), FRAME_MS)
    try:
        while True:
            # ticks_diff is rollover-safe, the same reason the original
            # compared (long)(MS_TIMER - done_time) instead of the raw values.
            late = ticks_diff(ticks_ms(), next_frame)
            if late < 0:
                sleep_ms(-late)
            next_frame = ticks_add(next_frame, FRAME_MS)
            game.step()
    except KeyboardInterrupt:
        oled.poweroff()


if __name__ == "__main__":
    main()
