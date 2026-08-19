/* ------------------------------------------------------------------
 * sh1106_vu.c  --  128x64 I2C OLED as a stereo VU meter
 *
 * Targets the "132x64" SH1106 (1.3" modules) and optionally the
 * SSD1306 (0.96"). Page-addressed, framebuffer-free, dirty-span
 * partial redraw so a 400 kHz bus can sustain 50+ fps.
 *
 * Ballistics (VU envelope, peak hold/fall) come from hd44780_vu.c --
 * only the rendering layer changes. Levels here are in PIXELS (0..127)
 * instead of 80 segments.
 * ------------------------------------------------------------------ */

#include <stdint.h>

/* ==== pick your controller ======================================== */
#define CTRL_SH1106   1          /* set to 0 for SSD1306             */

#if CTRL_SH1106
  #define XOFF        2          /* 132 col RAM, 128 col glass,
                                    panel wired to the middle         */
#else
  #define XOFF        0
#endif

#define OLED_ADDR   0x3C         /* 0x3D if SA0 is strapped high      */
#define W            128
#define H             64

/* ==== you must provide these ====================================== */
extern void i2c_start(uint8_t addr7, uint8_t write);
extern void i2c_write(uint8_t b);
extern void i2c_stop(void);

/* control byte: 0x00 = command stream, 0x40 = data stream */
static void oled_cmd(uint8_t c)
{
    i2c_start(OLED_ADDR, 1); i2c_write(0x00); i2c_write(c); i2c_stop();
}

static void oled_cmd2(uint8_t a, uint8_t b)
{
    i2c_start(OLED_ADDR, 1); i2c_write(0x00);
    i2c_write(a); i2c_write(b); i2c_stop();
}

/* SH1106 has NO horizontal addressing mode -- page + column must be
   re-issued for every page row. Doing this wrong is why SSD1306
   libraries render garbage on an SH1106.                             */
static void oled_goto(uint8_t page, uint8_t col)
{
    col += XOFF;
    i2c_start(OLED_ADDR, 1); i2c_write(0x00);
    i2c_write(0xB0 | (page & 0x07));      /* page address             */
    i2c_write(0x00 | (col & 0x0F));       /* column low nibble        */
    i2c_write(0x10 | (col >> 4));         /* column high nibble       */
    i2c_stop();
}

void oled_init(void)
{
    oled_cmd (0xAE);              /* display off                      */
    oled_cmd2(0xD5, 0x80);        /* clock divide / osc freq          */
    oled_cmd2(0xA8, 0x3F);        /* multiplex = 64                   */
    oled_cmd2(0xD3, 0x00);        /* display offset                   */
    oled_cmd (0x40);              /* start line 0                     */
#if CTRL_SH1106
    oled_cmd2(0xAD, 0x8B);        /* DC-DC on   (SH1106 spelling)     */
    oled_cmd (0x32);              /* pump voltage 8.0 V (SH1106 only) */
#else
    oled_cmd2(0x8D, 0x14);        /* charge pump on (SSD1306)         */
#endif
    oled_cmd (0xA1);              /* segment remap                    */
    oled_cmd (0xC8);              /* COM scan direction reversed      */
    oled_cmd2(0xDA, 0x12);        /* COM pin config                   */
    oled_cmd2(0x81, 0x9F);        /* contrast                         */
    oled_cmd2(0xD9, 0x22);        /* pre-charge                       */
    oled_cmd2(0xDB, 0x35);        /* VCOMH deselect                   */
    oled_cmd (0xA4);              /* resume from RAM                  */
    oled_cmd (0xA6);              /* normal (not inverted)            */
    oled_cmd (0xAF);              /* display on                       */
}

void oled_clear(void)
{
    for (uint8_t p = 0; p < 8; p++) {
        oled_goto(p, 0);
        i2c_start(OLED_ADDR, 1); i2c_write(0x40);
        for (uint8_t x = 0; x < W; x++) i2c_write(0x00);
        i2c_stop();
    }
}

/* ------------------------------------------------------------------
 * bar object
 *   Geometry in pixels. Levels in pixels, 0..w.
 *   Remembers its last state so it can redraw only what moved.
 * ---------------------------------------------------------------- */
typedef struct {
    uint8_t  x, w, y, h;      /* bar rectangle                        */
    uint8_t  segmented;       /* 1 = LED-ladder look (4 on, 1 off)    */
    uint8_t  plevel, ppeak;   /* previous frame, for dirty span       */
    uint8_t  first;           /* force full redraw once               */
} bar_t;

void bar_init(bar_t *b, uint8_t x, uint8_t w, uint8_t y, uint8_t h,
              uint8_t segmented)
{
    b->x = x; b->w = w; b->y = y; b->h = h;
    b->segmented = segmented;
    b->plevel = 0; b->ppeak = 0; b->first = 1;
}

/* rows of page p that fall inside [y0,y1] -> bitmask, LSB = top row  */
static uint8_t page_mask(uint8_t p, uint8_t y0, uint8_t y1)
{
    uint8_t top = p * 8, bot = top + 7;
    if (y1 < top || y0 > bot) return 0x00;
    uint8_t lo = (y0 > top ? y0 : top) - top;
    uint8_t hi = (y1 < bot ? y1 : bot) - top;
    return (uint8_t)((0xFFu << lo) & (0xFFu >> (7 - hi)));
}

void bar_draw(bar_t *b, uint8_t level, uint8_t peak)
{
    if (level > b->w) level = b->w;
    if (peak  > b->w) peak  = b->w;

    /* --- dirty span: only columns touched by either frame --------- */
    uint8_t xs, xe;
    if (b->first) {
        xs = 0; xe = b->w - 1; b->first = 0;
    } else {
        uint8_t a1 = level < b->plevel ? level : b->plevel;
        uint8_t a2 = level > b->plevel ? level : b->plevel;
        uint8_t p1 = peak  < b->ppeak  ? peak  : b->ppeak;
        uint8_t p2 = peak  > b->ppeak  ? peak  : b->ppeak;
        xs = a1 < p1 ? a1 : p1;
        xe = a2 > p2 ? a2 : p2;
        if (xs >= 3) xs -= 3; else xs = 0;          /* marker width   */
        if (xe + 1 < b->w) xe += 1; else xe = b->w - 1;
        if (xs > xe) { b->plevel = level; b->ppeak = peak; return; }
    }

    uint8_t y0 = b->y, y1 = b->y + b->h - 1;
    uint8_t p0 = y0 >> 3, p1p = y1 >> 3;

    for (uint8_t p = p0; p <= p1p; p++) {
        uint8_t mask = page_mask(p, y0, y1);
        if (!mask) continue;

        oled_goto(p, b->x + xs);
        i2c_start(OLED_ADDR, 1); i2c_write(0x40);

        for (uint8_t xi = xs; xi <= xe; xi++) {
            uint8_t byte = 0x00;

            if (xi < level && !(b->segmented && (xi & 3) == 3))
                byte = mask;

            /* 2 px peak marker; XOR so it stays visible inside the bar */
            if (peak && (xi == peak - 1 || (peak >= 2 && xi == peak - 2)))
                byte ^= mask;

            i2c_write(byte);
        }
        i2c_stop();
    }

    b->plevel = level;
    b->ppeak  = peak;
}

/* ------------------------------------------------------------------
 * static scale: tick marks along the bottom, drawn once
 *   Ticks at the dB values you actually read: -40 -20 -10 -5 0 +3
 * ---------------------------------------------------------------- */
#define DB_MIN  (-40.0f)
#define DB_MAX  (  3.0f)

static uint8_t db_to_px(float db)
{
    if (db <= DB_MIN) return 0;
    if (db >= DB_MAX) return W - 1;
    return (uint8_t)((db - DB_MIN) / (DB_MAX - DB_MIN) * (float)(W - 1) + 0.5f);
}

void oled_draw_scale(uint8_t y)          /* y must be page-aligned    */
{
    static const float ticks[]  = { -40, -30, -20, -10, -5, 0, 3 };
    static const uint8_t major[] = {  1,   0,   1,   1,  0, 1, 1 };
    uint8_t page = y >> 3;
    uint8_t col[W];

    for (uint8_t x = 0; x < W; x++) col[x] = 0x00;
    for (uint8_t i = 0; i < sizeof(ticks)/sizeof(ticks[0]); i++) {
        uint8_t x = db_to_px(ticks[i]);
        col[x] = major[i] ? 0x0F : 0x03;      /* 4 px vs 2 px tick    */
    }

    oled_goto(page, 0);
    i2c_start(OLED_ADDR, 1); i2c_write(0x40);
    for (uint8_t x = 0; x < W; x++) i2c_write(col[x]);
    i2c_stop();
}

/* ------------------------------------------------------------------
 * amplitude -> pixels (log). Build once at startup, same idea as the
 * HD44780 version but 128 steps instead of 80: 0.336 dB per pixel.
 * ---------------------------------------------------------------- */
extern float log10f(float);
extern float powf(float, float);

static uint16_t thr[W];

void vu_scale_init(float full_scale)
{
    for (uint16_t i = 0; i < W; i++) {
        float db = DB_MIN + (DB_MAX - DB_MIN) * (float)(i + 1) / (float)W;
        float a  = full_scale * powf(10.0f, db / 20.0f);
        thr[i] = (uint16_t)(a > 65535.0f ? 65535.0f : (a < 0.0f ? 0.0f : a));
    }
}

uint8_t amp_to_px(uint16_t a)
{
    uint8_t n = 0;
    while (n < W && a >= thr[n]) n++;
    return n;
}

/* ------------------------------------------------------------------
 * layout + usage
 * ------------------------------------------------------------------
 *   static bar_t L, R;
 *
 *   oled_init(); oled_clear(); vu_scale_init(511.0f);
 *   bar_init(&L, 0, 128,  0, 22, 1);      // left  bar,  y  0..21
 *   bar_init(&R, 0, 128, 24, 22, 1);      // right bar,  y 24..45
 *   oled_draw_scale(48);                  // ticks, page 6
 *
 *   // every 1/30 s, with lvl/pk from the ballistics in hd44780_vu.c:
 *   bar_draw(&L, lvlL, pkL);
 *   bar_draw(&R, lvlR, pkR);
 *
 * Timing
 *   Full frame        1024 B + overhead ~= 23 ms @400 kHz  (43 fps max)
 *   Two 22 px bars     3 pages x 128 B x 2 = 768 B ~= 17 ms
 *   Dirty span only    typically 10-40 B  ~= under 1 ms
 *
 * Gotchas
 *   - I2C must run at 400 kHz. At 100 kHz a full frame is 92 ms.
 *   - Keep the whole page write inside one I2C transaction; a
 *     start/stop per byte triples the overhead.
 *   - h should be a multiple of 8 and y page-aligned if you want the
 *     cheapest possible writes; page_mask() handles the general case
 *     but costs you an extra page row when the bar straddles one.
 *   - Cheap modules often lack the 0x3D pull-up option. If nothing
 *     appears, scan the bus before blaming the init sequence.
 * ---------------------------------------------------------------- */
