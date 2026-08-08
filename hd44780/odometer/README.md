# Odometer

![counter](cgram_odometer.gif)

CG-RAM odometer: you don't animate by swapping between ten stored glyphs. You rewrite one CG-RAM slot every frame with a composite — the bottom of the outgoing digit sitting above the top of the incoming one.

## The Animation
With 200 frames, 9s, counting 0-24 so the 9-0 carry is included. 45ms per sub-frame, 8 sub-frames per count is 360ms per digit. Rendered with the unlit pixel sites faintly visible, the way a real STN panel looks.

### Why a table of 10 glyphs isn't enough on its own

The 10 entries are the wheel faces. The frames in between don't exist in the table and are synthesised:

```
cell_row[r] = DIGITS[cur][r+k]        if r+k < 8
              DIGITS[next][r+k-8]     otherwise
```

`k` walks `0-7`, then the counter increments and `k` resets. `k=8` and `k=0` of the next count are the same picture, which is why the loop closes with no duplicate frame.

Row 8 is a free gift. HD44780 cells are 5×8 but the fonts are 5×7 — the bottom row is reserved for the underline cursor. Leave it zeroed in your table and it becomes the gap between wheel faces automatically. That's the difference between a roll that reads as a rotating drum and one that reads as two digits smeared together. hide_cursor() matters for the same reason: an enabled cursor paints straight into that gap.

### The part that makes it cheap

The controller rescans CG-RAM on every panel refresh. Rewrite the eight bytes of a slot and whatever is already on screen changes underneath you — no DDRAM write, no cursor repositioning, no reprint. Eight bytes per frame is the entire cost, about 180 bytes/s at this speed. Even 4-bit mode through a PCF8574 at 100 kHz has room to spare.

Set CG-RAM address is command 0x40 | (slot << 3), then eight data writes. lcd_api's custom_char() does exactly that.

# Constraints worth knowing before you scale it up

Eight slots, so at most eight rolling digits. Static digits use ROM codes '0'–'9' and cost nothing. A six-digit readout with one wheel uses one slot; you have seven left for bar graphs or a battery icon.

Avoid slot 0 in C. Character code 0 is the string terminator, so lcd_puts() can't carry it. Slot 1 costs nothing and keeps the code portable back to your Dynamic C world.

Real odometer carry needs the tens wheel turning during the last tenth of the units' travel, not jumping. That's a second slot plus a second k that only advances while cur == 9. Same wheel() function, driven by k_tens = k if cur == 9 else 0.

Direction: this rolls up (values increasing). Count k down from 7 for a decrementing counter, or swap cur/next.