# a781ffb (160) Get another hook clears time-based edits — QA 2026-10-07
Code: new-hook UPDATE removes cuts, keywords, zoom.markers, audio.silence_ranges, hook_title.text and keeps style/switches.
Bugs:
1. Low: audio.silence_trim (the Remove silences switch) stays true while its silence_ranges are cleared, so the new
   moment shows the switch on with no pauses removed. Clear silence_trim with the ranges, or re-detect pauses.
Prod deploy: worker/notifier/sender 07:35Z, backend 07:43Z. 6/6 riftstorm-* running, 0 restarts, 0 tracebacks.
