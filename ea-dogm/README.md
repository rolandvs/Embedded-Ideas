# EA-DOGM16x LCD Display

![EA](/ea-dogm/assets/img/dogm_descenders.png)

As can be seen from the picture the characters `gjpqy` all descend which is good for readability and style (neat).

Implementation is rather simple as can be seen from the **HD44780** example and this **EA-DOGM** example.

# my4TH

The test hardware is a custom CPU and executes native Forth code.

![my4TH](/ea-dogm/assets/img/dogm_my4TH.png)

One of the bugs in the code were the millisecond delays as the base is hexedecimal 500 ms is not 500ms. So I added some constants to the code
to make it work. Also how to figure out the current base?

## 10 equals 10
If you want to find out which base you are using `base @ .` is useless as it prints `10`. So a way to fix this is:

```
: .base  ( -- )   base @ dup decimal . base ! ; 
```

## DOGM Display

![DOGM-SCH](/ea-dogm/hardware/ea-dogm16x.png)

For the connection between the display and the my4TH checkout the [wiring diagram](/ea-dogm/hardware/connect_my4TH.png)

### Using "SPI" 
The schematics were fine. However, in the latest incarnation of the program a few pins moved. See connector below:

| FUNC        | LABEL| PIN| PIN| LABEL| FUNC    | 
|-------------|------|----|----|------|---------|
|             | GND  | 20 | 19 | GND  |         |
| MOSI/SO     | OUT7 | 18 | 17 | IN7  | SI/MISO |
| SCLK        | OUT6 | 16 | 15 | IN6  |         |
| SS_N        | OUT5 | 14 | 13 | IN5  |         |
| BACKLIGHT_N | OUT4 | 12 | 11 | IN4  |         |
| RS          | OUT3 | 10 |  9 | IN3  |         |
|             | OUT2 |  8 |  7 | IN2  |         |
|             | OUT1 |  6 |  5 | IN1  |         |
| TRIGGER_N   | OUT0 |  4 |  3 | IN0  |         |
|             | +5V  |  2 |  1 | RSTN |         |

First a bit-bang function was used to drive the display. It has been replaced by an assembly coded function implementing a SPI like function.

For the purpose of timing a `trigger` output pin is defined that will be activated (low active) during writing to the screen (see `myhello` function).

The measured time where the `trigger` start until it ends is `350ms`. It measures the of three strings written to the display. The debug code added were two fragments:

```
\ define a GPIO bit for the scope
1 constant trigger-bit  \ IO PORT bit 0 used to trigger the scope

: trigger-hi  trigger-bit bit-hi ;   
: trigger-lo  trigger-bit bit-lo ;
trigger-hi              \ set the output high
```

```
\ insert trigger-lo/hi around the block to measure time
trigger-lo 
0 0 lcd-goto  S" Welcome"      lcd-type
0 1 lcd-goto  S" dogm163 5v"   lcd-type
0 2 lcd-goto  S" My4TH rocks"  lcd-type
trigger-hi 
``` 

Using the SPI is roughly 5.5 times faster than the bit-bang version, which takes 1916ms to accomplish the same task.

# Forth

The descenders are loaded in CGRAM. The Forth way to do it, is in the listing below. Refer to the complete program [dogm163_descenders.fth](src/4th/dogm163_descenders.fth) characters on it.

```forth
\ way to access the CGRAM
: cg!  ( n -- )  38 lcd-cmd  8 * 40 or lcd-cmd ;
\ fill all custom characters directly
: g-desc  0 cg!  00 lcd-data 00 lcd-data 0F lcd-data 11 lcd-data
                 11 lcd-data 0F lcd-data 01 lcd-data 0E lcd-data ;
: j-desc  1 cg!  02 lcd-data 00 lcd-data 06 lcd-data 02 lcd-data
                 02 lcd-data 02 lcd-data 12 lcd-data 0C lcd-data ;
: p-desc  2 cg!  00 lcd-data 00 lcd-data 1E lcd-data 11 lcd-data
                 11 lcd-data 1E lcd-data 10 lcd-data 10 lcd-data ;
: q-desc  3 cg!  00 lcd-data 00 lcd-data 0F lcd-data 11 lcd-data
                 11 lcd-data 0F lcd-data 01 lcd-data 01 lcd-data ;
: y-desc  4 cg!  00 lcd-data 00 lcd-data 11 lcd-data 11 lcd-data 
                 11 lcd-data 0F lcd-data 01 lcd-data 0E lcd-data ;

\ load all custom characters - call once after lcd-init
\ cgram survives lcd-cls, but not power-off
: lcd-descenders
    g-desc j-desc p-desc q-desc y-desc
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

```


