'---[ Title ]-------------------------------------------------------------------
'
' File    : VU_032.bas
' Version : 1.02
' Author  : Ger Langezaal, Uiverstraat 13, 1171GX Badhoevedorp, The Netherlands
'
'---[ Program Description ]-----------------------------------------------------
'
' This program shows a bar dispay peak-hold VU meter on a LCD 16 * 2.
' Resolution is 32 elements for a 32 dB range based on the internal 8 bit
' A/D converter.
' The scale range is -26dB - +5dB for 0.125 to 5.00 Volt DC input.
' The display will be updated every 50mS on Timer0 interrupt base.
' Log conversion is done with a log table. At initialization a log table
' will be created and stored in the array Vu(256).
' VU meter can be disabled by Vu_flag = 0.
' Peak Hold can be disabled by Peak_hold_flag = 0.
' Setup for 80C535 at 12 Mhz, VAREF = 5Volt, A/D input = P6.0 (channal # 0).
' Compiler is BASCOM-8051 from MCS Electronics.
'
' note: Use a 47K resistor from the input to P6.0 for input protectection.
'
'---[ Compiler and Hardware related statements ]--------------------------------
'
$ramstart = &H8000
$ramsize = &H7FFF
$large

Config Lcdbus = 4
Config Lcd = 16 * 2
Config Timer0 = Timer , Gate = Internal , Mode = 2

'---[ Variables ]---------------------------------------------------------------
'
Dim Vu_flag As Bit                                  ' VU meter on/off flag
Dim Peak_hold_flag As Bit                           ' Peak Hold on/off flag
Dim Odd_flag As Bit                                 ' Odd/even flag
Dim Ad_value As Byte                                ' A/D converter output
Dim Vu_value As Byte                                ' Log conv. to bar elements
Dim Count0 As Byte                                  ' Interrupt counter
Dim Temp_byte1 As Byte
Dim Temp_byte2 As Byte
Dim Temp_byte3 As Byte
Dim Temp_byte4 As Byte
Dim Temp_byte5 As Byte
Dim Temp_count1 As Byte
Dim Vu(256) As Xram Byte                            ' Log tabel array
Dim Vu_bar As Xram String * 16                      ' LCD row characters

'---[ Constants ]---------------------------------------------------------------
'
Dim Vu_bars As Const 32                             ' Number of bar elements
Dim Int_counts As Const 199                         ' 200 * 250uS = 50mS
Dim Peak_hold As Const 29                           ' 30 * 50mS = 1.5 Sec

'---[ Interrupt settings ]------------------------------------------------------
'
On Timer0 Timer0_int                                ' Execute subroutine
Load Timer0 , 250                                   ' Auto reload value 250 (uS)
Priority Set Timer0                                 ' Set highest priority
Enable Interrupts
Enable Timer0

'---[ Initialization ]----------------------------------------------------------
'
Cls
Cursor Off
Locate 1 , 1 : Lcd "VU-meter"                       ' Intro text
Waitms 250 : Waitms 250                             ' Show intro message

Temp_byte1 = 0                                      ' 1 - 32 bar element
Temp_byte2 = 0                                      ' Data value
Temp_byte3 = 0                                      ' 0 - 255
Vu(temp_byte3) = 1                                  ' First array element = 1
Restore Log_table
                                                    ' Create Log Array Tabel
For Temp_byte1 = 1 To 32                            ' 32 bar elements
  Read Temp_byte2                                   ' Read data
  Do
    Incr Temp_byte3                                 ' Next array element
    Vu(temp_byte3) = Temp_byte1                     ' assign element to array
  Loop Until Temp_byte3 = Temp_byte2                ' Read next data
Next

'---[ Character Generator RAM ]-------------------------------------------------
'
Deflcdchar 0 , 12 , 18 , 18 , 18 , 12 , 00 , 08 , 08       ' 0
Deflcdchar 1 , 02 , 06 , 02 , 02 , 07 , 00 , 00 , 08       ' 1
Deflcdchar 2 , 06 , 09 , 02 , 04 , 15 , 00 , 00 , 08       ' 2
Deflcdchar 3 , 00 , 00 , 07 , 00 , 00 , 00 , 00 , 08       ' -
Deflcdchar 4 , 00 , 00 , 00 , 00 , 00 , 00 , 00 , 08       ' Marker
Deflcdchar 5 , 27 , 27 , 27 , 27 , 27 , 27 , 27 , 00       ' Vu bar
Deflcdchar 6 , 24 , 24 , 24 , 24 , 24 , 24 , 24 , 00       ' Vu bar Left
Deflcdchar 7 , 03 , 03 , 03 , 03 , 03 , 03 , 03 , 00       ' Vu bar Right

'---[ Draw scale: -26dB - +5dB ]------------------------------------------------
'
Cls
Locate 1 , 1 : Lcd Chr(4) ; Chr(3) ; Chr(2) ; Chr(0) ; Chr(4) ; Chr(4)
Locate 1 , 7 : Lcd Chr(3) ; Chr(1) ; Chr(0) ; Chr(4) ; Chr(4) ; Chr(4)
Locate 1 , 13 : Lcd Chr(4) ; Chr(0) ; Chr(4) ; Chr(4)

Temp_byte1 = 0
Temp_byte2 = 0
Temp_byte3 = 0
Temp_byte4 = 0
Temp_byte5 = 0
Ad_value = 0
Vu_value = 0
Vu_flag = 1                                         ' Enable Vu_meter Interrupt
Peak_hold_flag = 1                                  ' Enable Peak Hold
Start Timer0

'---[ Main loop ]---------------------------------------------------------------
'
Do
'   Application program
Loop

End

'---[ Vu meter Subroutine ]-----------------------------------------------------
'
Vu_meter:
  Vu_bar = ""
  Ad_value = Getad(0 , 0)                           ' A/D Ch#1 ,range 0-5Volt
  Vu_value = Vu(ad_value)                           ' Get log value
  Temp_byte1 = Vu_bars - Vu_value
  Temp_byte1 = Temp_byte1 \ 2                       ' Number of fill spaces
  Temp_byte2 = Vu_value \ 2                         ' Number of Vu bars
  Temp_byte3 = Vu_value Mod 2                       ' Bar position odd or even
  If Temp_byte2 > 0 Then Vu_bar = String(temp_byte2 , 5)       ' Assemble Vu bar
  If Temp_byte3 = 1 Then Vu_bar = Vu_bar + Chr(6)   ' Odd then add 1/2 Vu bar
  If Temp_byte1 > 0 Then Vu_bar = Vu_bar + String(temp_byte1 , 32)
  Locate 2 , 1 : Lcd Vu_bar                         ' Show Vu bar

'---[ Peak Hold ]---------------------------------------------------------------
'
  If Peak_hold_flag = 0 Then Return
  If Temp_count1 > Peak_hold Then                   ' Reset after 50mS * 30
    Temp_count1 = 0                                 ' Reset peak hold timer
    Temp_byte4 = 0                                  ' Reset peak value
  End If

  If Ad_value >= Temp_byte4 Then                    ' New peak value
    Temp_byte4 = Ad_value                           ' Update peak value
    Temp_byte5 = Temp_byte2                         ' Save peak bar position
    Temp_count1 = 0                                 ' Reset peak hold timer
    If Temp_byte3 = 1 Then                          ' Peak position odd
      Odd_flag = 1                                  ' Set odd flag
      Incr Temp_byte5                               ' Position single bar element
    Else
      Odd_flag = 0                                  ' Reset odd flag
    End If
  Else
    If Temp_byte5 > Temp_byte2 Then
      Locate 2 , Temp_byte5                         ' Set peak char position
      If Odd_flag = 1 Then
        Lcd Chr(6)                                  ' Odd = left bar element
      Else
        Lcd Chr(7)                                  ' Even = right bar element
      End If
    End If
  End If
  Incr Temp_count1                                  ' Increment Peak hold timer
Return

'---[ Interrupt counter ]-------------------------------------------------------
'
Timer0_int:
  Incr Count0                                       ' Count interrupts
  If Count0 > Int_counts Then                       '
    Count0 = 0                                      ' At 200, reset counter
    If Vu_flag = 1 Then Gosub Vu_meter              ' Every 50mS (250uS * 200)
  End If
Return

'---[ Log tabel 1.00 dB/step   Step factor 1.122 ]------------------------------
'
Log_table:
Data 7 , 8 , 9 , 10 , 11 , 13 , 14 , 16 , 18 , 20 , 23 , 26 , 29 , 32 , 36 , 40
Data 45 , 51 , 57 , 64 , 72 , 81 , 90 , 102 , 114 , 128 , 143 , 161 , 181 , 203
Data 227 , 255

'-------------------------------------------------------------------------------
