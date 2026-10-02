# QA review · 03ed581 · 084 guards (claims first-summary #4 window hang, #5 API language default, #9 rank parsing)

Reviewer: Lane C · 2026-10-02 · deployed backend + worker confirmed to contain it

## Re-check of the claimed fixes
- **Window hang: FIXED.** Ran the committed `transcript_windows()` source on a 2 h transcript with
  (window, overlap) = (1800,120) (120,120) (60,300) (0,0) (1800,−5): all terminate (5 / 119 / 239 / 120 / 4
  windows), with a log line for each clamp. Settings PUT now rejects overlap ≥ window and window < 1 min
  (`validate_hooks_windows`, code-read; not exercised live to avoid writing settings).
- **API language default: FIXED.** `language` omitted → `WHISPER_LANGUAGE` (here `id`); UI still sends it.
- **Rank parsing: FIXED.** Negative ids are rejected; a non-numeric score skips that item with a log line
  instead of failing the job.

## Findings
1. **Low · no ceiling on window count.** Window 1 min is accepted: a 2 h video then means ~120–240 hook
   calls per job. Suggest a minimum window (e.g. 10 min) or a max-calls cap.
2. **Low · bad score drops the candidate.** A non-numeric score skips the candidate entirely; keeping it with its
   window score would be kinder to a short ranking.

## Not verified
- A >400k-char transcript end to end; the settings PUT rejection over HTTP.
