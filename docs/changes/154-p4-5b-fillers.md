# 154 · P4 task 5b — Filler-word suggestions (lane B)

`shared/languages.FILLERS` (id: eh, em, anu, kayak, gitu, apa namanya; en: um, uh, like, you know, I mean) as
token regexes (stretched "eeeh"/"ummm" match; multi-word fillers; longest match first) →
`filler_spans(words, language)`. `GET …/editor/timeline` adds `fillers` (+ `language`, the job's resolved one)
per request. Editor: filler words show pre-struck with a dashed amber outline as SUGGESTIONS; nothing is cut
until the user clicks "Cut N fillers" (all) or clicks one in ✂ Cut mode (a multi-word filler is cut whole);
"Restore all" restores. Accepted fillers are ordinary `edit_spec.cuts`, so captions are handled like any cut.
Verified on staging: real Indonesian transcripts → "Eh", "eh, eh"; accepting the 2 on clip 93ae8661 → readout
34.88 s, preview 34.883 s (a 10 ms "eh" is below the 40 ms minimum cut and correctly ignored). Tests:
`tests/test_fillers.py` (4), 3 UI specs × 2 viewports; UI suite on staging 119 passed; unit 109 OK.
