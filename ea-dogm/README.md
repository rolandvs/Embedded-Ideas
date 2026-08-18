# EA-DOGM16x LCD Display

![EA](/ea-dogm/assets/img/dogm_descenders.png)

As can be seen from the picture the characters `gjpqy` all descend which is good for readability and style (neat).

Implementation is rather simple as can be seen from the **HD44780** example and this **EA-DOGM** example.

# my4TH

The test hardware is a custom CPU and executes native Forth code.

![my4TH](/ea-dogm/assets/img/dogm_my4TH.png)


## DOGM Display

![DOGM-SCH](/ea-dogm/hardware/ea-dogm16x.png)

For the connection between the display and the my4TH checkout the [wiring diagram](/ea-dogm/hardware/connect_my4TH.png)


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


