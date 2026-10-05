# 119 · Lows: one score per clip card; keywords skip flagged, exclamation and religious words · index.html, worker.py, shared/languages.py

- **One score per card:** the "★ n/10" rating badge on the preview shows only when the clip has no AI estimate
  (110); otherwise the AI estimate chip is the one score.
- **Keyword picker:** the content-safety pass now runs BEFORE the keyword pick (both before the first ASS) and
  keeps its result in memory; every word in a flagged quote joins the stoplist for that pick. Stoplists gain
  exclamations and religious words (id: astaghfirullah…, allah, masyaallah, subhanallah, alhamdulillah,
  insyaallah, bismillah, anjir, anjay, buset, waduh, wkwk…; en: omg, wow, god, jesus, lord, damn, lol…).

**Verified:** IME clip 1a9833d4 (flags quote "Kebakar Lagi…" and "Astaghfirullahaladzim … sihir") keywords
cleared and re-picked → [bili, molotofan] (kebakar, sihir, astaghfirullahaladzim excluded; 5 suggested);
harness 36/36.
