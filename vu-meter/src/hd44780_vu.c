/* ------------------------------------------------------------------
 * hd44780_vu.c  --  16x2 HD44780 character LCD as a stereo VU meter
 *
 * Resolution: 16 chars x 5 dot columns = 80 segments per row.
 * Glyphs:     CGRAM 1..4 = partial fills, ROM 0xFF = full block,
 *             CGRAM 5    = rewritten every frame = peak marker.
 *             CGRAM 0,6,7 left free for your own use.
 *
 * You supply lcd_cmd() and lcd_data(). Everything else is portable C99.
 * ------------------------------------------------------------------ */

#include <stdint.h>
#include <string.h>
#include <math.h>

/* ==== you must provide these two ================================== */
extern void lcd_cmd (uint8_t c);   /* RS=0, waits >=37us (1.52ms for 0x01/0x02) */
extern void lcd_data(uint8_t d);   /* RS=1, waits >=37us                        */

/* ==== geometry ==================================================== */
#define COLS          16
#define SEG_PER_CHAR   5
#define SEGS          (COLS * SEG_PER_CHAR)     /* 80 */

#define CG_PART1       1   /* CGRAM slots 1..4 hold 1..4 filled columns */
#define CG_PEAK        5   /* CGRAM slot rewritten each frame           */
#define CH_FULL     0xFF   /* ROM A00/A02 solid block                   */

/* column bitmasks: bit4 = leftmost dot of the 5-wide cell */
static const uint8_t fill_mask[6] = { 0x00, 0x10, 0x18, 0x1C, 0x1E, 0x1F };

/* ==== scale ======================================================= */
#define DB_MIN     (-40.0f)     /* bottom of scale                     */
#define DB_MAX      (  3.0f)    /* top of scale (0 VU = +4 dBu ref)    */
/* -> (DB_MAX-DB_MIN)/SEGS = 0.5375 dB per segment                     */

/* ==== ballistics ================================================== */
#define FRAME_HZ      30
#define VU_TAU_MS     65        /* 1st-order lag: 99% at 4.6*tau = 300ms
                                   matches ANSI C16.5 rise time         */
#define PEAK_HOLD_MS 1200
#define PEAK_FALL_DB_PER_S 12.0f

/* ------------------------------------------------------------------
 * one-time setup
 * ---------------------------------------------------------------- */
static uint16_t thr[SEGS];      /* amplitude threshold per segment    */
static float    vu_alpha;
static uint8_t  peak_hold_frames;
static float    peak_fall_seg_per_frame;

/* full_scale = amplitude that corresponds to DB_MAX
 * (e.g. for a 10-bit ADC with DC at mid-rail, peak swing is ~511)     */
void vu_init(float full_scale)
{
    /* --- load the four partial-fill glyphs ------------------------ */
    for (uint8_t i = 0; i < 4; i++) {
        lcd_cmd(0x40 | ((CG_PART1 + i) << 3));   /* Set CGRAM address  */
        for (uint8_t row = 0; row < 8; row++)
            lcd_data(fill_mask[i + 1]);
    }
    lcd_cmd(0x0C);              /* display on, cursor off, blink off   */
    lcd_cmd(0x80);              /* leave the controller in DDRAM mode  */

    /* --- logarithmic threshold table ------------------------------ */
    for (uint16_t i = 0; i < SEGS; i++) {
        float db = DB_MIN + (DB_MAX - DB_MIN) * (float)(i + 1) / (float)SEGS;
        float a  = full_scale * powf(10.0f, db / 20.0f);
        thr[i] = (uint16_t)(a < 0.0f ? 0.0f : (a > 65535.0f ? 65535.0f : a));
    }

    /* --- ballistic constants -------------------------------------- */
    vu_alpha = 1.0f - expf(-(1000.0f / FRAME_HZ) / (float)VU_TAU_MS);
    peak_hold_frames = (uint8_t)((PEAK_HOLD_MS * FRAME_HZ) / 1000);
    peak_fall_seg_per_frame =
        (PEAK_FALL_DB_PER_S / FRAME_HZ) * SEGS / (DB_MAX - DB_MIN);
}

/* amplitude -> segment count (0..80), linear scan is fine at 30 Hz */
static uint8_t amp_to_seg(uint16_t a)
{
    uint8_t n = 0;
    while (n < SEGS && a >= thr[n]) n++;
    return n;
}

/* ------------------------------------------------------------------
 * renderer
 *   level, peak : 0..80 segments. peak == 0 -> no marker drawn.
 *   The marker is a single dot column: drawn as an added column in
 *   empty space, or as a notch when it falls inside the filled bar.
 * ---------------------------------------------------------------- */
void lcd_bar(uint8_t row, uint8_t level, uint8_t peak)
{
    static uint8_t shadow[2][COLS] = {{0},{0}};
    uint8_t line[COLS];

    if (level > SEGS) level = SEGS;
    if (peak  > SEGS) peak  = SEGS;

    uint8_t full = level / SEG_PER_CHAR;
    uint8_t rem  = level % SEG_PER_CHAR;

    for (uint8_t i = 0; i < COLS; i++)
        line[i] = (i <  full)            ? CH_FULL
                : (i == full && rem)     ? (uint8_t)(CG_PART1 + rem - 1)
                :                          ' ';

    if (peak) {
        uint8_t p    = peak - 1;                 /* segment index 0..79 */
        uint8_t cp   = p / SEG_PER_CHAR;
        uint8_t mask = 0x10 >> (p % SEG_PER_CHAR);

        uint8_t base = (line[cp] == CH_FULL) ? 0x1F
                     : (line[cp] >= CG_PART1 && line[cp] <= CG_PART1 + 3)
                       ? fill_mask[line[cp] - CG_PART1 + 1]
                       : 0x00;

        uint8_t pat = (base & mask) ? (uint8_t)(base & ~mask)   /* notch */
                                    : (uint8_t)(base |  mask);  /* dot   */

        lcd_cmd(0x40 | (CG_PEAK << 3));
        for (uint8_t r = 0; r < 8; r++) lcd_data(pat);
        line[cp] = CG_PEAK;
    }

    /* write only what changed; re-address only when the run breaks   */
    uint8_t base_addr = row ? 0x40 : 0x00;
    int8_t  cursor    = -1;
    for (uint8_t i = 0; i < COLS; i++) {
        if (line[i] == shadow[row][i] && cursor == i) { cursor = -1; continue; }
        if (line[i] == shadow[row][i]) continue;
        if (cursor != (int8_t)i) { lcd_cmd(0x80 | (base_addr + i)); }
        lcd_data(line[i]);
        shadow[row][i] = line[i];
        cursor = (int8_t)i + 1;
    }
    if (peak) lcd_cmd(0x80 | base_addr);  /* CGRAM write invalidated AC */
}

/* ------------------------------------------------------------------
 * per-channel state + one frame of processing
 *   Feed rectified, DC-removed samples between frames via vu_feed().
 * ---------------------------------------------------------------- */
typedef struct {
    uint32_t acc;        /* sum of |x| since last frame  */
    uint16_t n;          /* sample count                 */
    float    env;        /* VU envelope, amplitude units */
    float    peak_seg;   /* peak marker position         */
    uint8_t  hold;       /* frames left at hold          */
} vu_ch_t;

void vu_feed(vu_ch_t *c, int16_t sample_dc_removed)
{
    int32_t a = sample_dc_removed < 0 ? -sample_dc_removed : sample_dc_removed;
    c->acc += (uint32_t)a;
    c->n++;
}

void vu_frame(vu_ch_t *c, uint8_t row)
{
    uint16_t mean = c->n ? (uint16_t)(c->acc / c->n) : 0;
    c->acc = 0; c->n = 0;

    /* VU: symmetric first-order lag (the "heavy damped needle") */
    c->env += ((float)mean - c->env) * vu_alpha;

    uint8_t lvl = amp_to_seg((uint16_t)c->env);

    /* Peak: instant attack, hold, then linear-in-dB fall */
    if (lvl >= (uint8_t)c->peak_seg) {
        c->peak_seg = (float)lvl;
        c->hold = peak_hold_frames;
    } else if (c->hold) {
        c->hold--;
    } else {
        c->peak_seg -= peak_fall_seg_per_frame;
        if (c->peak_seg < 0.0f) c->peak_seg = 0.0f;
    }

    lcd_bar(row, lvl, (uint8_t)(c->peak_seg + 0.5f));
}

/* ------------------------------------------------------------------
 * usage
 * ------------------------------------------------------------------
 *   static vu_ch_t L, R;
 *   lcd_init();                 // your 4-bit or 8-bit init sequence
 *   vu_init(511.0f);            // 10-bit ADC, mid-rail biased
 *
 *   // in the sampling ISR (a few kHz):
 *   vu_feed(&L, adc_l - dc_l);
 *   vu_feed(&R, adc_r - dc_r);
 *
 *   // every 1/FRAME_HZ seconds:
 *   vu_frame(&L, 0);
 *   vu_frame(&R, 1);
 *
 * Notes
 *  - Remove DC with a slow running average, not a fixed constant;
 *    a biased ADC input drifts with temperature and supply.
 *  - Mean-of-|x| is what a real VU responds to. For true RMS,
 *    accumulate x*x into a uint64 and sqrt once per frame.
 *  - If you want one 16-dot-tall bar instead of two channels, call
 *    lcd_bar(0, lvl, pk) and lcd_bar(1, lvl, pk) with the same values;
 *    the same glyphs work on both rows.
 * ---------------------------------------------------------------- */
