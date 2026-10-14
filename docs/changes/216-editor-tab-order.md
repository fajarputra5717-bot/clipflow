# 216 — Editor Tab order (owner 2026-10-14, after 215)

The timeline (`.ed-tlwrap`) moved in the DOM from after the inspector to between the player and the inspector
(`.ed-grid`: player → timeline → inspector), so Tab goes play controls → timeline → inspector → action bar. Visual
layout is unchanged: the fit layout places it by grid area, phones by flex `order`, and short desktop windows
(≥ 900 wide, < 768 tall) by explicit grid rows (full-width row under player + inspector). Measured from the play
button: timeline = 11th Tab stop (was after every inspector control), first inspector tab = 97th (after ~85 word chips
in the timeline), Render preview = 152nd.
