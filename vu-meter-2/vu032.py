"""
vu032.py - MicroPython port of VU_032.bas v1.02
           Target Raspi pico (RP2040)

Original : Ger Langezaal, Badhoevedorp (NL) - BASCOM-8051, 80C535 @ 12 MHz
Port     : same behaviour, same log table, same peak-hold rules.

32-element bar-graph VU meter with peak hold on a 16x2 HD44780 LCD.
Each LCD character holds two bar elements (left half / right half), so
16 characters = 32 elements = 32 dB, 1.00 dB per element.

Scale: element 32 = full scale = +5 dB, element 1 = -26 dB.

See notes at the end of this program
"""

from micropython import const


VU_BARS   = const(32)      # bar elements over the whole scale
TICK_MS   = const(50)      # display refresh period (was 200 x 250 us)
PEAK_HOLD = const(30)      # 30 ticks x 50 ms = 1.5 s

CH_DIGIT_0 = const(0)      # scale glyphs, stored in CGRAM 0..4
CH_DIGIT_1 = const(1)
CH_DIGIT_2 = const(2)
CH_MINUS   = const(3)
CH_TICK    = const(4)
CH_BAR     = const(5)      # bar glyphs, CGRAM 5..7
CH_HALF_L  = const(6)
CH_HALF_R  = const(7)

# 5x8 dot patterns, one byte per row, bit4 = leftmost dot.
# Identical to the Deflcdchar statements in the original.
CGRAM = (
    (12, 18, 18, 18, 12, 0, 8, 8),          # 0  "0" + tall scale tick
    (2, 6, 2, 2, 7, 0, 0, 8),               # 1  "1"
    (6, 9, 2, 4, 15, 0, 0, 8),              # 2  "2"
    (0, 0, 7, 0, 0, 0, 0, 8),               # 3  "-"
    (0, 0, 0, 0, 0, 0, 0, 8),               # 4  bare scale tick
    (27, 27, 27, 27, 27, 27, 27, 0),        # 5  full bar  = 2 elements
    (24, 24, 24, 24, 24, 24, 24, 0),        # 6  left half = 1 element
    (3, 3, 3, 3, 3, 3, 3, 0),               # 7  right half
)

# Top line: dotted ruler with "-20", "-10" and "0" over the labelled points.
SCALE_ROW = bytes((
    CH_TICK, CH_MINUS, CH_DIGIT_2, CH_DIGIT_0, CH_TICK, CH_TICK,
    CH_MINUS, CH_DIGIT_1, CH_DIGIT_0, CH_TICK, CH_TICK, CH_TICK,
    CH_TICK, CH_DIGIT_0, CH_TICK, CH_TICK,
))

# Upper ADC code of each of the 32 elements. This is exactly the DATA
# block of the original, and exactly round(255 / 1.122**(32-n)) for n=1..32.
# 1.122 per step = 20*log10(1.122) = 0.9997 dB, i.e. 1 dB per element.
LOG_STEPS = ( 7, 8, 9, 10, 11, 13, 14, 16, 18, 20, 23, 26, 29, 32, 36, 40, 45, 
             51, 57, 64, 72, 81, 90, 102, 114, 128, 143, 161, 181, 203, 227, 255)


def build_log_table():
    """256-entry lookup: ADC code -> bar element 1..32.
    Code 0 maps to element 1, as in the original. Keep it: the peak-hold
    code uses the element count as a 1-based LCD column, and element 0
    would address column 0.
    """
    table = bytearray(256)
    table[0] = 1
    code = 0
    for i, top in enumerate(LOG_STEPS):
        while code < top:
            code += 1
            table[code] = i + 1
    return table


def element_db(element):
    """dB of a bar element, element 32 = full scale = +5 dB."""
    return element - 27


class Lcd4Bit:
    """Minimal HD44780 driver, 4-bit bus - the Config Lcdbus = 4 equivalent.

    One byte costs two nibbles ~= 100 us, so a full 16-character row takes
    about 1.6 ms. That fits inside the 50 ms refresh with room to spare.
    """

    def __init__(self, rs, en, d4, d5, d6, d7):
        from machine import Pin
        import time
        self._time = time
        self.rs = Pin(rs, Pin.OUT, value=0)
        self.en = Pin(en, Pin.OUT, value=0)
        self.data = [Pin(p, Pin.OUT, value=0) for p in (d4, d5, d6, d7)]

        time.sleep_ms(50)                    # power-up settle
        for _ in range(3):
            self._nibble(0x03)
            time.sleep_ms(5)
        self._nibble(0x02)                   # enter 4-bit mode
        self.cmd(0x28)                       # 4-bit, 2 lines, 5x8 font
        self.cmd(0x0C)                       # display on, cursor off
        self.cmd(0x06)                       # increment, no shift
        self.clear()

    def _nibble(self, value):
        for i in range(4):
            self.data[i].value((value >> i) & 1)
        self.en.value(1)
        self._time.sleep_us(1)
        self.en.value(0)
        self._time.sleep_us(50)

    def _write(self, value, rs):
        self.rs.value(rs)
        self._nibble(value >> 4)
        self._nibble(value & 0x0F)

    def cmd(self, value):
        self._write(value, 0)

    def clear(self):
        self.cmd(0x01)
        self._time.sleep_ms(2)

    def move_to(self, col, row):
        self.cmd(0x80 | (0x40 * row) + col)

    def write(self, buf):
        for byte in buf:
            self._write(byte, 1)

    def define_char(self, index, rows):
        self.cmd(0x40 | (index << 3))
        for row in rows:
            self._write(row, 1)
        self.move_to(0, 0)


class VuMeter:
    """The Vu_meter and Peak_hold subroutines, one tick = one call."""

    def __init__(self, lcd, read_code, peak_hold=True):
        self.lcd = lcd
        self.read_code = read_code          # callable -> 0..255
        self.peak_hold = peak_hold
        self.table = build_log_table()
        self.row = bytearray(16)
        # peak state (Temp_byte4/5, Odd_flag, Temp_count1)
        self.peak_code = 0
        self.peak_col = 0
        self.peak_odd = False
        self.hold = 0
        # last reading, for the readout
        self.code = 0
        self.element = 0

    def install(self):
        for i, rows in enumerate(CGRAM):
            self.lcd.define_char(i, rows)
        self.lcd.clear()
        self.lcd.move_to(0, 0)
        self.lcd.write(SCALE_ROW)

    def tick(self):
        code = self.read_code()
        element = self.table[code]
        self.code, self.element = code, element

        full = element >> 1                  # whole characters
        odd = element & 1                    # trailing half character
        pad = (VU_BARS - element) >> 1        # blanks to the right

        row = self.row
        for i in range(full):
            row[i] = CH_BAR
        if odd:
            row[full] = CH_HALF_L
        for i in range(full + odd, full + odd + pad):
            row[i] = 32
        self.lcd.move_to(0, 1)
        self.lcd.write(row)

        if not self.peak_hold:
            return

        if self.hold > PEAK_HOLD - 1:        # 1.5 s since the last peak
            self.hold = 0
            self.peak_code = 0

        if code >= self.peak_code:
            self.peak_code = code
            self.peak_col = full + odd       # 1-based column of the peak
            self.peak_odd = bool(odd)
            self.hold = 0
        elif self.peak_col > full:           # peak sits clear of the bar
            self.lcd.move_to(self.peak_col - 1, 1)
            self.lcd.write(bytes((CH_HALF_L if self.peak_odd else CH_HALF_R,)))

        self.hold += 1


# Raspberry Pi Pico defaults. Change to suit your board.
PIN_RS, PIN_EN = 16, 17
PIN_D4, PIN_D5, PIN_D6, PIN_D7 = 18, 19, 20, 21
PIN_ADC = 26                                 # GP26 = ADC0

# The original ran an 8-bit ADC with VAREF = 5 V, so code 255 = 5.00 V.
# The Pico ADC is 12-bit (read_u16 left-aligns it) with a 3.3 V reference,
# so scale a 5 V input down to 3.3 V and convert back to a 0..255 code.
V_FULL_SCALE = 5.0                           # input volts that must read 255
V_ADC_REF = 3.3
DIVIDER = V_ADC_REF / V_FULL_SCALE           # e.g. 22k over 33k
_CODE_PER_LSB = 255.0 / 65535.0 * (V_ADC_REF / (DIVIDER * V_FULL_SCALE))


def main():
    from machine import ADC, Pin, Timer

    lcd = Lcd4Bit(PIN_RS, PIN_EN, PIN_D4, PIN_D5, PIN_D6, PIN_D7)
    adc = ADC(Pin(PIN_ADC))

    def read_code():
        code = int(adc.read_u16() * _CODE_PER_LSB)
        return 255 if code > 255 else code

    lcd.move_to(0, 0)
    lcd.write(b"VU-meter")
    import time
    time.sleep_ms(500)

    meter = VuMeter(lcd, read_code)
    meter.install()

    # The 8051 called the whole meter from the Timer0 ISR. Don't do that here:
    # a MicroPython ISR must not allocate, and the LCD writes take ~1.6 ms.
    # The timer only raises a flag; the main loop does the work.
    flag = bytearray(1)

    def on_tick(_):
        flag[0] = 1

    Timer().init(period=TICK_MS, mode=Timer.PERIODIC, callback=on_tick)

    while True:
        if flag[0]:
            flag[0] = 0
            meter.tick()
        # application code goes here


if __name__ == "__main__":
    main()

# ---------------------------------------------------------------------------
# What changed, and why
#
# 1. Timer0 mode 2 @ 250 us with a /200 software divider becomes one 50 ms
#    periodic timer. Same cadence, no counter needed.
# 2. The meter runs in the main loop, not in the ISR. MicroPython forbids
#    heap allocation inside an interrupt handler.
# 3. Vu_flag / Peak_hold_flag become the peak_hold argument and simply not
#    calling tick(). Same effect, no globals.
# 4. Xram string building becomes a preallocated bytearray, so tick() does
#    not allocate on the heap.
# 5. Getad(0,0) becomes an ADC read plus rescaling, because the Pico ADC is
#    12-bit at 3.3 V and the 80C535 was 8-bit at 5 V.
# 6. Integer \ 2 becomes >> 1 and Mod 2 becomes & 1. Same result, cheaper.
# ---------------------------------------------------------------------------
