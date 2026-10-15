# lane-b d6ae3bc (Effects tab: /api/sfx arrival no longer repaints the panel) — staging

Live check as lane-c-a at 1280×800 with my own sound assigned to boom ("My boom"), video paused at 3 s, `/api/sfx` delayed 900 ms by a route and undelayed (22 ms):
- Effects tab, then immediately focus the zoom slider: after the response arrives the slider is still focused; two ArrowRight presses move the slider 50 → 60 and the video stays at 3.00 s (before the fix the keys went to the player). Same with no delay.
- A sound picker focused during the slow load stays focused; ArrowDown changes the picker (not the video).
- The pickers are relabelled in place: "No sound / Whoosh / Boom · My boom / Bass hit / Ding / Record scratch / Laugh (Ding until you add yours)". 0 page errors.
Not verified: the Z-mode test fix (spec timing only), the 15× parallel repeat Lane B ran.

Merge: OK for d6ae3bc.
