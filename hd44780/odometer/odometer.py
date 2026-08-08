"""
odometer.py

CG-RAM odometer for an HD44780 character LCD.
Target: STM32 + MicroPython, LCD on I2C1 via a PCF8574 backpack.

The units digit rolls upward like an odometer wheel. The leading digits
are ordinary ROM characters and simply jump.

The trick: an HD44780 rescans CG-RAM continuously to refresh the panel,
so rewriting the eight bytes of one CG-RAM slot changes what is already
on screen. You never touch DDRAM during a roll. Eight bytes per frame is
the entire cost of the animation.

Needs lcd_api.py and pyb_i2c_lcd.py / machine_i2c_lcd.py from
github.com/dhylands/python_lcd on the board.
"""

from machine import I2C
from time import ticks_ms, ticks_add, ticks_diff, sleep_ms
from machine_i2c_lcd import I2cLcd

# ---- 5x7 digit table: 7 rows of glyph + 1 blank spacer row ----
# Bits 4..0 are the five columns, MSB leftmost. Row 8 is the cursor line
# on a real HD44780, which is exactly why it makes a free wheel gap.
DIGITS = (
    (0b01110, 0b10001, 0b10011, 0b10101, 0b11001, 0b10001, 0b01110, 0),
    (0b00100, 0b01100, 0b00100, 0b00100, 0b00100, 0b00100, 0b01110, 0),
    (0b01110, 0b10001, 0b00001, 0b00010, 0b00100, 0b01000, 0b11111, 0),
    (0b11111, 0b00010, 0b00100, 0b00010, 0b00001, 0b10001, 0b01110, 0),
    (0b00010, 0b00110, 0b01010, 0b10010, 0b11111, 0b00010, 0b00010, 0),
    (0b11111, 0b10000, 0b11110, 0b00001, 0b00001, 0b10001, 0b01110, 0),
    (0b00110, 0b01000, 0b10000, 0b11110, 0b10001, 0b10001, 0b01110, 0),
    (0b11111, 0b00001, 0b00010, 0b00100, 0b01000, 0b01000, 0b01000, 0),
    (0b01110, 0b10001, 0b10001, 0b01110, 0b10001, 0b10001, 0b01110, 0),
    (0b01110, 0b10001, 0b10001, 0b01111, 0b00001, 0b00010, 0b01100, 0),
)

I2C_ADDR = 0x27          # 0x3F on many backpacks
LCD_ROWS, LCD_COLS = 2, 16
NDIGITS = 6
ROW, COL = 0, 5          # where the readout starts

SLOT = 1                 # CG-RAM slot for the wheel. Not 0: in C, char
                         # code 0 terminates a string, so slot 0 cannot be
                         # printed with lcd_puts(). Python does not care,
                         # but staying off 0 keeps the trick portable.
STEPS = 8                # eight pixel rows of travel per count
STEP_MS = 45             # 360 ms per digit, about right for a wheel


def wheel(cur, nxt, k):
    """Composite glyph: digit `cur` scrolled up k rows, `nxt` following it.

    Cell row r shows source row r+k. Once r+k runs past the bottom of the
    outgoing glyph the pixels come from the incoming one, so the two
    digits behave like adjacent faces of one physical wheel.
    k=0 is a plain `cur`; k=8 would be a plain `nxt`, which is where the
    next count begins.
    """
    out = bytearray(8)
    for r in range(8):
        s = r + k
        out[r] = DIGITS[cur][s] if s < 8 else DIGITS[nxt][s - 8]
    return out


def main():
    i2c = I2C(1, freq=400_000)       # I2C1: SCL = PB6, SDA = PB7
    if I2C_ADDR not in i2c.scan():
        raise OSError("no LCD backpack at 0x%02X on I2C1" % I2C_ADDR)

    lcd = I2cLcd(i2c, I2C_ADDR, LCD_ROWS, LCD_COLS)
    lcd.clear()
    lcd.hide_cursor()                # else the cursor line fills the wheel gap

    count = 0
    head = ""

    # Paint the fixed part once, plus the wheel character in the last cell.
    lcd.move_to(COL, ROW)
    lcd.putstr("%0*d" % (NDIGITS - 1, 0))
    lcd.move_to(COL + NDIGITS - 1, ROW)
    lcd.putchar(chr(SLOT))

    next_frame = ticks_add(ticks_ms(), STEP_MS)
    while True:
        cur = count % 10
        nxt = (count + 1) % 10
        new_head = "%0*d" % (NDIGITS - 1, count // 10)

        # Leading digits are ROM characters and cost nothing to leave alone.
        # Rewrite them only on a carry, which is when they actually change.
        if new_head != head:
            head = new_head
            lcd.move_to(COL, ROW)
            lcd.putstr(head)

        for k in range(STEPS):
            lcd.custom_char(SLOT, wheel(cur, nxt, k))
            late = ticks_diff(ticks_ms(), next_frame)
            if late < 0:
                sleep_ms(-late)
            next_frame = ticks_add(next_frame, STEP_MS)

        count += 1


if __name__ == "__main__":
    main()
