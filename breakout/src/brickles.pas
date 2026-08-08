{                                                             }
{ From the course, Learn to Program Pascal.                   }
{ Compiled with ORCA/Pascal 1.2                               }
{                                                             }
{ Copyright 1990, Byte Works, Inc.                            }
{                                                             }
{ This program plays the game of break-out, a classic arcade  }
{ game.                                                       }

program Paddle (output);

uses Common, QuickDrawII, EventMgr, MemoryMgr;

const
   eventMask = $0F6E;                   {GetNextEvent event mask}
   letterY = 200;                       {height of letters for score, ball count}
   pause = 1;                           {60ths of a sec. to pause}

                                        {the paddle}
                                        {----------}
   area1 = 7;                           {sensitive areas of the paddle}
   area2 = 14;
   area3 = 21;
   area4 = 28;
   easy = 2;                            {x velocity for easy spin}
   hard = 3;                            {x velocity for hard spin}
   paddleColor = 15;                    {paddle color}
   paddleHeight = 3;                    {paddle height}
   paddleWidth = 35;                    {paddle width}
   paddleY = 184;                       {y position of the paddle}

                                        {the bricks}
                                        {-----------}
   columns = 16;                        {# of bricks in a row}
   columns1 = 17;                       {columns + 1}
   rows = 6;                            {# of rows of bricks}
   spacing = 8;                         {spacing of the rows}
   startHeight = 56;                    {initial space above the top row of bricks}
   thickness = 6;                       {thickness of a brick}
   width = 20;                          {width of a brick}

                                        {the ball}
                                        {--------}
   ballColor = 15;                      {ball color}
   ballHeight = 3;                      {ball height; should be odd}
   ballWidth = 3;                       {ball width; should be odd}
   balldx = 1;                          {(ballWidth - 1) div 2}
   balldy = 1;                          {(ballHeight - 1) div 2}
   speed = 2;                           {vertical ball speed}

var
   event: boolean;                      {event flag; returned by GetNextEvent}
   lastWhen: longint;                   {event timer}
   myEvent: eventRecord;                {current event record}
   score: integer;                      {current score}
   screen: rect;                        {port rectangle}

                                        {the paddle}
                                        {----------}
   maxX: integer;                       {max X distance the paddle can travel}
   paddlePosition: integer;             {current X position of the paddle}

                                        {the bricks}
                                        {----------}
   brickY: integer;                     {disp to the bottom row of bricks}
   level: integer;                      {playing level}
   numBricks: integer;                  {# of bricks visible}
   stillThere: array[1..rows,0..columns1] of boolean; {brick array}

                                        {the ball}
                                        {--------}
   balls: integer;                      {# of balls left}
   dx,dy: integer;                      {speed of the ball}
   x,y: integer;                        {position of the ball}

procedure StartTools;

{ Start the tools                                             }

const
   size = 320;                          {graphics mode}

var
   memory: handle;                      {memory returned by NewHandle}

begin {StartTools}
StartGraph(size);                       {initialize QuickDraw}
memory := NewHandle(256,UserID,$C015,nil); {start up the event mgr}
EMStartUp(ord(memory^),0,0,size,0,200,UserID);
end; {StartTools}

procedure ShutDownTools;

{ Shut down the tools                                         }

begin {ShutDownTools}
EMShutDown;
EndGraph;
end; {ShutDownTools}

procedure DrawPaddle (position,color: integer);

{ Draw the paddle                                             }
{                                                             }
{ Parameters:                                                 }
{    position - position to draw the paddle                   }
{    color - color of the paddle                              }

begin {DrawPaddle}
                                        {set the pen to draw the entire paddle}
SetPenSize(paddleWidth,paddleHeight);
SetSolidPenPat(color);                  {set the paddle color}
SetPenMode(0);                          {use copy mode}
MoveTo(position,paddleY);               {draw the paddle}
LineTo(position,paddleY);
end; {DrawPaddle}

procedure MovePaddle;

{ Track and move the paddle                                   }

begin {MovePaddle}
                                        {convert the point to our window}
GlobalToLocal(myevent.eventWhere);
                                        {make sure we don't go off of the screen}
if myevent.eventWhere.h+paddleWidth > maxX then
   myevent.eventWhere.h := maxX-paddleWidth;
                                        {if the mouse moved, move the paddle}
if myevent.eventWhere.h <> paddlePosition then begin
   DrawPaddle(paddlePosition,0);
   paddlePosition := myevent.eventWhere.h;
   DrawPaddle(paddlePosition,paddleColor);
   end; {if}
end; {MovePaddle}

function PlayAGame: boolean;

{ See if the player wants to play a game or quit.             }
{                                                             }
{ Returns: True to play a game, else false.                   }

const
   left = 110;                          {dimensions of the buttons}
   right = 210;
   top1 = 90;
   bottom1 = 101;
   top2 = 105;
   bottom2 = 116;

var
   r: rect;                             {rect inclosing the buttons}

   function WhichButton: integer;

   { See which button the mouse is in                         }
   {                                                          }
   { Variables:                                               }
   {    myEvent.eventWhere - location of mouse at mouseup     }
   {    myEvent.eventWhat - kind of event                     }

   begin {WhichButton}
   WhichButton := 0;
   if myEvent.eventWhat = mouseUpEvt then
      with myEvent.eventWhere do
         if h >= left then
            if h <= right then
               if v >= top1 then
                  if v <= bottom2 then
                     if v <= bottom1 then
                        WhichButton := 1
                     else if v >= top2 then
                        WhichButton := 2;
   end; {WhichButton}

begin {PlayAGame}
MoveTo(left+10,bottom1-2);              {draw the messages}
write('Play a Game');
MoveTo(left+30,bottom2-2);
write('Quit');
SetSolidPenPat(14);                     {draw the button outlines}
SetPenMode(0);
SetPenSize(3,1);
MoveTo(left,top1);
LineTo(right,top1);
LineTo(right,bottom1);
LineTo(left,bottom1);
LineTo(left,top1);
MoveTo(left,top2);
LineTo(right,top2);
LineTo(right,bottom2);
LineTo(left,bottom2);
LineTo(left,top2);
ShowCursor;                             {wait for a click in a button}
repeat
   event := GetNextEvent(eventMask,myEvent);
   GlobalToLocal(myEvent.eventWhere);
   MovePaddle;
until WhichButton <> 0;
HideCursor;
r.h1 := left;                           {erase the messages}
r.h2 := right;
r.v1 := top1;
r.v2 := bottom2;
SetSolidPenPat(0);
PlayAGame := WhichButton = 1;           {set the return value}
end; {PlayAGame}

procedure DrawBrick (row,column,color: integer);

{ Draw a brick on the screen                                  }
{                                                             }
{ Parameters:                                                 }
{    row,column - brick to draw                               }
{    color - color of the brick                               }
{                                                             }
{ Variables:                                                  }
{    brickY - distance to the bottom of the bricks            }

var
   r: rect;                             {brick's rectangle}

begin {DrawBrick}
SetPenMode(0);                          {get ready to draw}
SetSolidPenPat(color);
SetPenSize(1,1);
r.h1 := (column-1)*width;               {set up the brick's rectangle}
r.h2 := r.h1+width-1;
r.v2 := brickY - row*spacing + spacing;
r.v1 := r.v2-thickness;
PaintRect(r);                           {draw the brick}
SetSolidPenPat(0);                      {draw a line to separate the bricks}
MoveTo(r.h2+1, r.v1);
LineTo(r.h2+1, r.v2);
end; {DrawBrick}

procedure DrawBricks;

{ Draw a set of bricks                                        }

var
   colors: array[1..rows] of integer;   {brick colors}
   column: 1..columns;                  {loop variable}
   row: 1..rows;                        {loop variable}
   r: rect;                             {brick rectangle}

begin {DrawBricks}
numBricks := rows*columns;              {set the brick count}
colors[1] := 7;                         {fill in the brick color array}
colors[2] := 6;
colors[3] := 9;
colors[4] := 10;
colors[5] := 13;
colors[6] := 12;
for row := 1 to rows do                 {draw the bricks}
   for column := 1 to columns do
      DrawBrick(row,column,colors[row]);
for column := 1 to columns do           {all bricks are still there}
   stillThere[1,column] := true;
stillThere[1,0] := false;
stillThere[1,columns1] := false;
for row := 2 to rows do
   stillThere[row] := stillThere[1];
end; {DrawBricks}

procedure WriteBalls;

{ Draw the number of balls left                               }
{                                                             }
{ Variables:                                                  }
{    balls - number of balls left                             }

const
   ballX = 290;

begin {WriteBalls}
MoveTo(ballX,letterY);
write(balls:1, ' ':10);
end; {WriteBalls}

procedure WriteScore;

{ Draw the current score                                      }
{                                                             }
{ Variables:                                                  }
{    score - score to draw                                    }

const
   scoreX = 50;

begin {WriteScore}
MoveTo(scoreX,letterY);
write(score:1, ' ':10);
end; {WriteScore}

procedure DrawBall;

{ Draw a ball at the current position                         }
{                                                             }
{ Variables:                                                  }
{    x,y: ball position                                       }
{                                                             }
{ Note: This procedure is used to draw an initial ball or     }
{       to erase one after a ball is missed.  MoveBall uses   }
{       its own method, which is faster when the ball is      }
{       being animated.                                       }

begin {DrawBall}
SetSolidPenPat(ballColor);
SetPenMode(2);
SetPenSize(ballWidth,ballHeight);
MoveTo(x-balldx,y-balldy);
LineTo(x-balldx,y-balldy);
end; {DrawBall}

procedure StartBall;

{ Start a ball                                                }
{                                                             }
{ Variables:                                                  }
{    x,y - position of the ball                               }
{    dx,dy - speed of the ball                                }

begin {StartBall}
if odd(myEvent.eventWhen) then          {set the speed, position}
   dx := -easy
else
   dx := easy;
x := ord(myEvent.eventWhen mod screen.h2);
dy := speed;
y := startHeight+spacing*rows+4;

DrawBall;                               {draw the ball}

event := GetNextEvent(eventMask, myevent); {set the timer}
lastWhen := myEvent.eventWhen;
end; {StartBall}

procedure WaitForClick;

{ Pause until the player is ready for a ball                  }

var
   r: rect;                             {used to erase the message}

begin {WaitForClick}
MoveTo(65,100);                         {write the message}
write('Click for the next ball');
repeat                                  {wait for the click}
   event := GetNextEvent(eventMask,myEvent);
   MovePaddle;
until myEvent.eventWhat = mouseUpEvt;
r.h1 := 0;                              {erase the message}
r.h2 := 320;
r.v1 := 90;
r.v2 := 100;
SetSolidPenPat(0);
SetPenMode(0);
PaintRect(r);
end; {WaitForClick}

procedure CheckBricks;

{ Move the ball.                                              }
{                                                             }
{ Variables:                                                  }
{    x,y - position of the ball                               }
{    numBricks - # of bricks left                             }

var
   ball: rect;                          {used to erase the ball}
   row,column: integer;                 {brick row,column}
   dispX,dispY: integer;                {position along the brick}

   procedure HitBrick (row,column: integer);

   { Handle a hit brick                                       }
   {                                                          }
   { Parameters:                                              }
   {    row,column - brick that was hit                       }

   begin {HitBrick}
   stillThere[row,column] := false;     {remove the brick}
   ball.h1 := x-balldx;                 {erase the ball}
   ball.h2 := ball.h1+ballWidth;
   ball.v1 := y-balldy;
   ball.v2 := ball.v1+ballHeight;
   SetPenMode(2);
   SetSolidPenPat(ballColor);
   PaintRect(ball);
   DrawBrick(row,column,0);             {erase the brick}
   SetPenMode(2);                       {redraw the ball}
   SetSolidPenPat(ballColor);
   PaintRect(ball);
   score := score+(row+level)*5;        {add in the score}
   WriteScore;
   numBricks := numBricks-1;            {see if they are all gone}
   if numBricks = 0 then begin
      DrawBall;
      balls := balls+1;
      WriteBalls;
      brickY := brickY+spacing;
      level := level+1;
      DrawBricks;
      WaitForClick;
      StartBall;
      end; {if}
   event := GetNextEvent(eventMask, myevent); {reset the timer}
   lastWhen := myEvent.eventWhen;
   end; {HitBrick}

begin {CheckBricks}
row := (brickY-y+spacing) div spacing;  {find the vertical brick values}
dispY := (brickY-y) mod spacing;
if (row in [1..rows]) and (dispY <= thickness) then begin
   column := x div width + 1;           {find the horizontal brick values}
   dispX := x mod width;
   if stillThere[row,column] then begin {check for a hit}
      HitBrick(row,column);
      if dispY in [0,thickness] then
         dy := -dy
      else
         dx := -dx;
      end {if}
   else if dispY in [0,thickness] then
      if dispX = 0 then begin
         if stillThere[row,column-1] then begin
            HitBrick(row,column-1);
            dy := -dy;
            end; {if}
         end {if}
      else if dispX = width then
         if stillThere[row,column+1] then begin
            HitBrick(row,column+1);
            dy := -dy;
            end; {if}
   end; {if}
end; {CheckBricks}

procedure MoveBall;

{ Move the ball.                                              }
{                                                             }
{ Variables:                                                  }
{    x,y - position of the ball                               }
{    dx,dy - speed of the ball                                }

var
   oldBall,newBall: rect;               {ball rectangles}
   px: integer;                         {disp of ball on paddle surface}

   procedure GetANewBall;

   { Missed; get a new ball                                   }

   begin {GetANewBall}
   balls := balls-1;                    {reduce the number of balls}
   WriteBalls;
   if balls <> 0 then begin
      PaintRect(oldBall);               {erase the old ball}
      WaitForClick;                     {wait until the player is ready}
      StartBall;                        {start a new ball}
      oldBall.h1 := x-balldx;           {form its rectangle}
      oldBall.h2 := oldBall.h1+ballWidth;
      oldBall.v1 := y-balldy;
      oldBall.v2 := oldBall.v1+ballHeight;
      end; {if}
   end; {GetANewBall}

begin {MoveBall}
SetPenMode(2);                          {get ready to draw}
SetSolidPenPat(ballColor);
oldBall.h1 := x-balldx;                 {form the old ball rectangle}
oldBall.h2 := oldBall.h1+ballWidth;
oldBall.v1 := y-balldy;
oldBall.v2 := oldBall.v1+ballHeight;
x := x+dx;                              {move the ball}
if x < 0 then begin
   x := 0;
   dx := -dx;
   end {if}
else if x > screen.h2 then begin
   x := screen.h2;
   dx := -dx;
   end; {else if}
y := y+dy;
if y < 0 then begin
   y := 0;
   dy := -dy;
   end {if}
else if y >= paddleY then begin
   if (x < paddlePosition) or (x > paddlePosition+paddleWidth) then
      GetANewBall
   else begin
      px := x-paddlePosition;
      if px < area1 then
         dx := -hard
      else if px < area2 then
         dx := -easy
      else if px < area3 then
         dx := 0
      else if px < area4 then
         dx := easy
      else
         dx := hard;
      dy := -dy;
      y := paddleY;
      end; {else}
   end; {else if}
newBall.h1 := x-balldx;                 {form the new ball rectangle}
newBall.h2 := newBall.h1+ballWidth;
newBall.v1 := y-balldy;
newBall.v2 := newBall.v1+ballHeight;
PaintRect(newBall);                     {draw the ball in the new spot}
PaintRect(oldBall);                     {erase the old ball}
end; {MoveBall}

procedure InitScreen;

{ Draw the initial screen                                     }

var
   column: 1..columns;                  {loop variable}
   row: 1..rows;                        {loop variable}

begin {InitScreen}
SetSolidPenPat(0);                      {erase the old screen contents}
SetPenMode(0);
PaintRect(screen);
brickY := startHeight;                  {draw the initial set of bricks}
DrawBricks;
paddlePosition := 0;                    {draw the initial paddle}
DrawPaddle(0,paddleColor);
SetForeColor(11);                       {draw the initial score, ball count}
SetBackColor(0);
MoveTo(0,letterY);
writeln('Score:');
MoveTo(240,letterY);
writeln('Balls:');
score := 0;
WriteScore;
balls := 3;
WriteBalls;
end; {InitScreen}

begin
StartTools;                             {start the tools}
InitCursor;                             {set up the cursor}
HideCursor;
GetPortRect(screen);                    {set the limit on the paddle}
maxX := screen.h2;
level := 1;                             {play level starts at 1}
InitScreen;                             {give them something to look at}

while PlayAGame do begin
   InitScreen;                          {set up the screen}
   StartBall;                           {start a ball}
   repeat                               {event loop}
      event := GetNextEvent(eventMask, myevent);
      if (myEvent.eventWhen-lastWhen) > pause then begin
         MoveBall;
         CheckBricks;
         lastWhen := lastWhen+pause;
         end; {if}
      MovePaddle;
   until balls = 0;
   DrawBall;                            {erase the last ball}
   end; {while}

ShutDownTools;                          {shut down the tools}
end.
