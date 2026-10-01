# 079 · Per-job language (Auto / English / Indonesian) · worker.py, main.py, index.html, shared/languages.py

**Before.** Everything assumed Indonesian: Whisper ran with `WHISPER_LANGUAGE=id`, the hook prompt, the
AI typo-fix/description prompts and the Submagic upload all said Indonesian.

**Now.**
- `jobs.language` (auto|en|id, default auto from the Import form; NULL = pre-079 job = Indonesian),
  `language_fallback` (the form's last EXPLICIT choice, remembered in localStorage), and what happened:
  `detected_language`, `language_confidence`, `effective_language`. `shared/languages.job_language()`
  resolves 'en'|'id' for any row; every downstream step reads that.
- `transcribe(language="auto")`: Whisper detects first (3 detection segments; the segment generator is
  lazy, so a fallback re-run costs only the detection). Confidence < 0.6 (`MIN_CONFIDENCE`) or a language
  other than en/id → logged and `language_fallback` is used.
- Hook prompt: English jobs get "Write the title in natural English."; Indonesian keeps the exact
  pre-079 line (the TASKS-5 eval measured it). Backend new-hook / subtitle-fix / description prompts and
  the Submagic upload `language` follow the job.
- Stoplists for TASKS-3 T2 keyword highlighting: `shared/languages.STOPWORDS` / `stopwords_for()` (id
  incl. spoken particles, en). Not used yet.
- UI: Language choice-grid in Import options (+ summary), `jobLanguageLine()` in the job card's Details
  and as a tag on the Publish detail ("Auto → English · detected en (1.00)", "· fallback" when used).

**Verified** on the stack (Gemini's free-tier daily quota was exhausted, so hooks failed over to Claude):
- English video gbYYJF0c4VA, Auto + fallback id → detected en 0.997, effective en; titles English
  ("Playing a Japanese Baseball Game I Can't Read at All"); AI description English.
- Indonesian video y2iHEe-vsLc, Auto + fallback en → detected id 0.991, effective id; titles Indonesian
  ("Bangga Game Indonesia Menang Award, Tapi Belinya Aja Belum?").
- Low-confidence path: 20 s pink noise, Auto + fallback en → detected nn (0.70, unsupported) → en, logged.
- `language: "fr"` → 400. UI: choice, remembered last explicit choice, summary and Publish tag (headless).
- Deploy note: on a deploy that adds columns the worker can log one "column … does not exist" loop
  error before the backend's `ensure_schema()` has run; the loop retries.
