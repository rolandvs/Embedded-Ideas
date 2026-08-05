/***********************************************************
      disppong_oled.ino

      Arduino port of Z-World's disppong.c (Rabbit / Dynamic C, 2001)
      Target: SSD1306 OLED over I2C, Adafruit_GFX + Adafruit_SSD1306

      A 16x12 bitmap "ball" bounces inside a drawn box. When it
      reaches a wall it pulls a grimace for one frame, then
      reverses. Non-blocking: loop() never calls delay().

      Wiring (I2C): SDA/SCL to the board's I2C pins, VCC 3V3/5V, GND.
************************************************************/

#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ---------- display geometry ----------
#define SCREEN_WIDTH   128
#define SCREEN_HEIGHT   64      // 32 also works
#define OLED_RESET      -1      // -1 = share the MCU reset pin
#define OLED_ADDR     0x3C      // some modules are 0x3D

Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Box edges as absolute coordinates, not widths.
// (The original named these WIDTH/HEIGHT but used them as edges.)
#define BOX_L  0
#define BOX_T  0
#define BOX_R  (SCREEN_WIDTH  - 1)
#define BOX_B  (SCREEN_HEIGHT - 1)

#define BALL_W  16
#define BALL_H  12
#define FRAME_MS 50UL

// ---------- 16x12 bitmaps, MSB first, 2 bytes per row ----------
// Byte layout is identical to the Rabbit original, so these are
// copied verbatim. PROGMEM keeps them out of RAM on AVR.

static const unsigned char PROGMEM smileyball[] = {
  0x07, 0xC0,
  0x18, 0x30,
  0x30, 0x18,
  0x26, 0xC8,
  0x46, 0xC4,
  0x40, 0x04,
  0x48, 0x24,
  0x48, 0x24,
  0x24, 0x48,
  0x23, 0x98,
  0x18, 0x30,
  0x07, 0xC0
};

static const unsigned char PROGMEM wallball[] = {
  0x07, 0xC0,
  0x18, 0x30,
  0x30, 0x18,
  0x26, 0xC8,
  0x46, 0xC4,
  0x40, 0x04,
  0x40, 0x04,
  0x4F, 0xE4,
  0x20, 0x08,
  0x30, 0x18,
  0x18, 0x30,
  0x07, 0xC0
};

// The original's third bitmap, blank[], is gone: fillRect() erases
// the same 16x12 window for free.

// ---------- state ----------
static int px = BOX_L + 1;    // current position
static int py = BOX_T + 1;
static int dx = 2;            // current direction
static int dy = 2;
static int holdFrames = 0;    // grimace frames still owed (1 per axis hit)
static unsigned long nextFrame = 0;

// ---------- drawing ----------

// Erase the old 16x12 window, stamp the new one, push to the panel.
// Replaces glXPutBitmap()'s replace-mode write plus the blank[] erase.
static void drawBall(int x, int y, const unsigned char *bm) {
  display.fillRect(px, py, BALL_W, BALL_H, SSD1306_BLACK);
  display.drawBitmap(x, y, bm, BALL_W, BALL_H, SSD1306_WHITE);
  display.display();
}

static void drawBox() {
  display.drawRect(BOX_L, BOX_T,
                   BOX_R - BOX_L + 1, BOX_B - BOX_T + 1, SSD1306_WHITE);
}

// ---------- setup ----------
void setup() {
  Wire.begin();
  Wire.setClock(400000);   // 100 kHz makes display() alone cost ~90 ms

  if (!display.begin(SSD1306_SWITCHCAPVCC, OLED_ADDR)) {
    for (;;) {}            // panel not answering: nothing useful left to do
  }

  display.clearDisplay();
  drawBox();
  display.drawBitmap(px, py, smileyball, BALL_W, BALL_H, SSD1306_WHITE);
  display.display();

  nextFrame = millis() + FRAME_MS;
}

// ---------- one frame of pong ----------
void loop() {
  // Signed comparison, so the millis() rollover at ~49.7 days is a
  // non-event. Same trick the original used on MS_TIMER.
  if ((long)(millis() - nextFrame) < 0) return;
  nextFrame += FRAME_MS;

  // Owe the wall a grimace frame? Hold position and pull the face.
  if (holdFrames > 0) {
    holdFrames--;
    drawBall(px, py, wallball);
    return;
  }

  // Probe the next position. This move is discarded either way.
  int nx = px + dx;
  int ny = py + dy;

  if (nx < BOX_L + 1 || nx + BALL_W > BOX_R) { dx = -dx; holdFrames++; }
  if (ny < BOX_T + 1 || ny + BALL_H > BOX_B) { dy = -dy; holdFrames++; }

  if (holdFrames > 0) {
    holdFrames--;                 // a corner hit owes two frames
    drawBall(px, py, wallball);
    return;
  }

  // Commit, using the direction as it now stands.
  nx = px + dx;
  ny = py + dy;
  drawBall(nx, ny, smileyball);
  px = nx;
  py = ny;
}
