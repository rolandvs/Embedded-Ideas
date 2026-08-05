# Improved Lower Case On LCDs

From Electronic Design, August 5, 1996
by Jay Sarno, San Diego

Many small alphanumeric liquid-crystal displays are controlled by Hitachi's HD44780 integrated circuit. This display controller chip has a built-in character generator that includes lower-case letters.
Unfortunately, the font is implemented in a 5-by-7 pixel cell with no place for descenders. As a result, the letters `g`, `j`, `p`, `q` and `y` have an awkward apperance. Designers thus are left with either using all upper-case letters for messages (which affects readability and implies "shouting"), accepting  the clumsy built-in lower-case letters, or using the method described here.

There's usually an eight row of pixels beneath the character cell that's employed for an underline cursor. In many applications, the cursor is unused. The HD44780 supports eight user-definable characters that can utilize all eight rows, permitting improved versions of the above five characters.

An application software routine written in **68HC11** assembly language is presented that loads the improved chracters into the first five user-definable locations (_see the listing_).

The second routine is called to send a character to the display. It checks for a lower-case descender character and maps it into the improved version. The routines that write bytes to the display are referred to, but not shown, because they depend on the specific hardware implementation.

# Code

```mc68hc11
            nam         DESCENDERS
*
*****************************************************************
* LOAD_CG - call this routine as part of system initialisation
*
*   It load the first 5 programmable characters in the
*   LCD display with improvd versions of "gjpqy".
*****************************************************************

load_cg:    jsr         set_lcd_write           display R/W bit low
            ldab        #$40                    receive CG data
            jsr         send_lcd_cntl           set CG register = 0
            ldx         #lc_char_gen            beginning of table
            ldy         #$40                    init loop counter

lcg_loop:   ldab        0,x                     copy data into display
            jsr         send_lcd_data
            inx
            dey
            bne         lcg_loop
            rts
*
* 'g', 'j', 'p', 'q', 'y'
*
lc_char_gen:
            fcb         $00,$00,$0f,$11,$11,$0f,$01,$0e
            fcb         $02,$00,$06,$02,$02,$02,$12,$0c
            fcb         $00,$00,$1e,$11,$11,$1e,$10,$10
            fcb         $00,$00,$0d,$13,$11,$0f,$01,$01
            fcb         $00,$00,$11,$11,$11,$0f,$01,$0e

*****************************************************************
* DISPLAY_CHAR - the char in B is sent to the display
*
*   Any lower-case character with a descender is translated
*   to the "improved" character code.
*****************************************************************

display_char:
            jsr         set_lcd_write
            clra       
            ldx         #chars_to_fix           point to table of LC chars

lc_hunt_loop:
            cmpb        0,x                     match with descender?
            beq         lc_translate            replace
            inx
            inca
            cmpa        #$05                    all possible
            blo         lc_hunt_loop
            bra         char_ok_as_is           no translation
lc_translate:
            tab                                 copy position
char_ok_as_is:
            jsr         send_lcd_data
            rts

chars_to_fix:
            fcb         'g', 'j', 'p', 'q', 'y'

            end

```
