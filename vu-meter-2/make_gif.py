"""Render vu032's display to an animated GIF, dot by dot.

Drives the ported VuMeter with a synthetic DC envelope, captures the DDRAM
every 50 ms, and paints the real 5x8 CGRAM patterns with an STN-style fade.
"""
import math
from PIL import Image, ImageDraw
import vu032 as v

# ---- geometry -------------------------------------------------------------
DOT, GAP = 5, 2          # dot size and inter-dot gap, pixels
CGAP, RGAP = 5, 8        # gap between character cells / between the two rows
PAD, BEZEL = 12, 9
COLS, ROWS, DW, DH = 16, 2, 5, 8

CELL_W = DW * DOT + (DW - 1) * GAP
CELL_H = DH * DOT + (DH - 1) * GAP
GLASS_W = COLS * CELL_W + (COLS - 1) * CGAP + 2 * PAD
GLASS_H = ROWS * CELL_H + (ROWS - 1) * RGAP + 2 * PAD
W, H = GLASS_W + 2 * BEZEL, GLASS_H + 2 * BEZEL

FIELD = (185, 199, 82)   # yellow-green backlight
OFF = (167, 181, 69)     # unlit dot, barely darker than the field
ON = (37, 45, 14)        # lit dot
CASE = (30, 28, 25)

LEVELS = 8               # fade steps, keeps the GIF palette small
PALETTE = [tuple(round(OFF[i] + (ON[i] - OFF[i]) * s / (LEVELS - 1))
                 for i in range(3)) for s in range(LEVELS)]

# ---- virtual LCD ----------------------------------------------------------
class Ddram:
    def __init__(self):
        self.ram = [bytearray(v.SCALE_ROW), bytearray(b" " * 16)]
        self.pos = [0, 0]

    def move_to(self, col, row):
        self.pos = [col, row]

    def write(self, buf):
        col, row = self.pos
        for b in buf:
            self.ram[row][col] = b
            col += 1
        self.pos[0] = col

    def define_char(self, i, rows):
        pass

    def clear(self):
        self.ram = [bytearray(b" " * 16) for _ in range(2)]


# ---- input envelope: 2 s ramp, then 4 s of drum hits ----------------------
def envelope(t):
    if t < 2.0:
        return (t / 2.0) ** 1.0
    t -= 2.0
    beat = 0.5
    n = int(t / beat)
    phase = t - n * beat
    accent = (1.0, .45, .75, .35, 1.0, .5, .85, .3)[n % 8]
    return accent * math.exp(-phase * 7)


# ---- run the meter --------------------------------------------------------
lcd = Ddram()
code_box = [0]
meter = v.VuMeter(lcd, lambda: code_box[0])

TICK = v.TICK_MS / 1000.0
N = int(6.0 / TICK)
frames_ram = []
for i in range(N):
    volts = max(0.0, min(5.0, envelope(i * TICK) * 5.0))
    code_box[0] = min(255, round(volts / 5.0 * 255))
    meter.tick()
    frames_ram.append((bytes(lcd.ram[0]), bytes(lcd.ram[1])))

# ---- paint ----------------------------------------------------------------
bright = [0.0] * (COLS * ROWS * DW * DH)
K_ON, K_OFF = 1 - math.exp(-TICK / 0.045), 1 - math.exp(-TICK / 0.075)

def render(ram):
    img = Image.new("RGB", (W, H), CASE)
    d = ImageDraw.Draw(img)
    d.rectangle([BEZEL, BEZEL, W - BEZEL - 1, H - BEZEL - 1], fill=FIELD)
    i = 0
    for r in range(ROWS):
        for c in range(COLS):
            ch = ram[r][c]
            glyph = v.CGRAM[ch] if ch < 8 else (0,) * 8
            x0 = BEZEL + PAD + c * (CELL_W + CGAP)
            y0 = BEZEL + PAD + r * (CELL_H + RGAP)
            for y in range(DH):
                bits = glyph[y]
                for x in range(DW):
                    on = (bits >> (4 - x)) & 1
                    b = bright[i]
                    bright[i] = b + (on - b) * (K_ON if on else K_OFF)
                    lvl = min(LEVELS - 1, int(bright[i] * LEVELS))
                    i += 1
                    px = x0 + x * (DOT + GAP)
                    py = y0 + y * (DOT + GAP)
                    d.rectangle([px, py, px + DOT - 1, py + DOT - 1],
                                fill=PALETTE[lvl])
    return img

for _ in range(3):                       # settle the fade state before capture
    for ram in frames_ram:
        render(ram)

images = [render(ram) for ram in frames_ram]
flat = []
for col in PALETTE + [FIELD, CASE]:
    flat += list(col)
pal = Image.new("P", (1, 1))
pal.putpalette(flat + [0] * (768 - len(flat)))
images = [im.quantize(palette=pal, dither=Image.Dither.NONE) for im in images]

out = "/mnt/user-data/outputs/vu032_display.gif"
images[0].save(out, save_all=True, append_images=images[1:],
               duration=int(v.TICK_MS), loop=0, optimize=True, disposal=1)
print(out, W, "x", H, len(images), "frames")
