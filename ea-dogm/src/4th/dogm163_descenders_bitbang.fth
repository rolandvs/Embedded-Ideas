\ My4TH experimental setup
\ Using the output port to drive a display
\
\ The display is an EA DOGM display, which come as
\ DOGM81, DOGM162 and DOGM163
\
\ The code is a bit-bang SPI serial version which is slow.
\
\ This code is an adaption of the dogm163.fth with custom
\ descenders g j p q y added in CGRAM 0-4
\
\ Copyright (c)2026 by Roland van Straten
\ License: MIT
\ 
\ I/O Connector and PIN usage
\
\             GND • • GND
\         SO OUT7 • • IN7
\        CLK OUT6 • • IN6
\        CSN OUT5 • • IN5
\  BACKLIGHT OUT4 • • IN4
\         RS OUT3 • • IN3
\            OUT2 • • IN2
\            OUT1 • • IN1
\    TRIGGER OUT0 • • IN0
\             +5V • • RSTN
\

hex

\ setting or clearing a bit
: bit-hi ( mask -- )   rout or  wout ;
: bit-lo ( mask -- )   invert  rout and wout ;

\ make sure the delay time values are "decimal"
base @  decimal
    2 constant t2
  200 constant t200
  500 constant t500
base !

\ connections of lcd to output port of My4TH board
80 constant si-bit
40 constant ck-bit
20 constant cs-bit
10 constant bl-bit
08 constant rs-bit

\ setting or clearing a bit
: out!   ( n -- )   dup pout !  wout ;
: bit-hi ( mask -- )   pout @ or  out! ;
: bit-lo ( mask -- )   invert  pout @ and  out! ;

\ individual bit of display set or cleared
: si-hi  si-bit bit-hi ;   : si-lo  si-bit bit-lo ;
: ck-hi  ck-bit bit-hi ;   : ck-lo  ck-bit bit-lo ;
: cs-hi  cs-bit bit-hi ;   : cs-lo  cs-bit bit-lo ;
: rs-hi  rs-bit bit-hi ;   : rs-lo  rs-bit bit-lo ;

: bl-on  bl-bit bit-lo ;   : bl-off bl-bit bit-hi ;

\ spi byte send - msb first, mode 3 (clk idle high)
: spi-byte  ( byte -- )
    8 0 do
        dup 80 and
        if si-hi else si-lo then
        ck-lo
        ck-hi
        1 lshift
    loop drop ;

: lcd-cmd  ( byte -- )
    rs-lo cs-lo spi-byte cs-hi ;

: lcd-data  ( byte -- )
    rs-hi cs-lo spi-byte cs-hi ;

\ contrast word - call anytime after lcd-init
\ contrast is 0-63 (6-bit value)
\   low nibble  -> $70 | c3-c0
\   high 2 bits -> $50 | c5-c4 (with booster off)
: lcd-contrast  ( n -- )
    39 lcd-cmd                       \ function set, table 1
    dup  0F and  70 or  lcd-cmd       \ $7x = contrast [c3-c0]
    04 rshift  03 and  50 or  lcd-cmd  \ $5x = booster + [c5-c4]
    38 lcd-cmd ;                        \ function set, table 0

\ dogm163 init - 3 lines, 5v supply
: lcd-init
    rs-lo
    bl-on
    t200 ms
    39 lcd-cmd             \ function set: 8-bit, table 2 (3-line mode)
    1D lcd-cmd             \ 4-line/3-line display, bias bs=1
    50 lcd-cmd             \ 
    6C lcd-cmd             \ 
    7C lcd-cmd             \ 
    38 lcd-cmd             \ function set: 8-bit, table 0
    0C lcd-cmd             \ display on, cursor off, blink
    01 lcd-cmd             \ clear display
    t2 ms
    06 lcd-cmd  ;          \ entry mode: cursor right

\ position cursor: col 0-15, row 0-2
\ dogm163 ddram row offsets: 0=$00, 1=$10, 2=$20
: lcd-goto  ( col row -- )
    case
        0 of 00 endof
        1 of 10 endof
        2 of 20 endof
        00 swap
    endcase
    + 80 or
    lcd-cmd ;

\ clear screen
: lcd-cls
    38 lcd-cmd             \ function set: 8-bit, table 0
    01 lcd-cmd              \ clear display
    t2 ms ;

: cg!  ( n -- )  38 lcd-cmd  8 *  40 or  lcd-cmd ;

: g-desc  0 cg!  00 lcd-data  00 lcd-data  0F lcd-data  11 lcd-data
                 11 lcd-data  0F lcd-data  01 lcd-data  0E lcd-data ;
: j-desc  1 cg!  02 lcd-data  00 lcd-data  06 lcd-data  02 lcd-data
                 02 lcd-data  02 lcd-data  12 lcd-data  0C lcd-data ;
: p-desc  2 cg!  00 lcd-data  00 lcd-data  1E lcd-data  11 lcd-data
                 11 lcd-data  1E lcd-data  10 lcd-data  10 lcd-data ;
: q-desc  3 cg!  00 lcd-data  00 lcd-data  0F lcd-data  11 lcd-data
                 11 lcd-data  0F lcd-data  01 lcd-data  01 lcd-data ;
: y-desc  4 cg!  00 lcd-data  00 lcd-data  11 lcd-data  11 lcd-data 
                 11 lcd-data  0F lcd-data  01 lcd-data  0E lcd-data ;

\ load all custom characters - call once after lcd-init
\ cgram survives lcd-cls, but reload after power-off
: lcd-descenders
    g-desc  j-desc  p-desc  q-desc  y-desc
    0 0 lcd-goto ;

\ map g j p q y onto cgram codes 0-4, everything else passes
: lcd-emit  ( c -- )
    case
        67 of 0 endof              \ g
        6A of 1 endof              \ j
        70 of 2 endof              \ p
        71 of 3 endof              \ q
        79 of 4 endof              \ y
        dup                        \ default: char passes through
    endcase
    lcd-data ;

\ print string (with descenders)
: lcd-type  ( addr len -- )
    0 do  
        dup  c@ lcd-emit  
        char+  
    loop  drop ;

\ separate init function for display 
: init
    lcd-init
    6 lcd-contrast
    lcd-descenders ;

\ hello world across all 3 lines
: myhello
    8 0 do
        lcd-cls
        0 0 lcd-goto  S" Welcome"      lcd-type
        0 1 lcd-goto  S" dogm163 5v"   lcd-type
        0 2 lcd-goto  S" My4TH rocks"  lcd-type
        t500 ms
        lcd-cls
        0 0 lcd-goto  S" the quick brown" lcd-type
        0 1 lcd-goto  S" fox jumps over"  lcd-type
        0 2 lcd-goto  S" lazy dogs back"  lcd-type 
        t500 ms
    loop ;

init
myhello
