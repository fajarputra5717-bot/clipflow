# 011 — Faster analysis: measure first (R-07)
Date: 2026-09-29 · Commit: see `git log --grep R-07` · Files: worker.py

## What changed
- `StageTimer` in `process_analysis_job()`: every `stage = …` now also times the stage; logs `Stage <name>: Ns`
  per stage and one `Stage timings job <id>: … | total Ns` line from a `finally:` (success and failure).
- Download format capped (`YTDLP_FORMAT`): H.264 ≤1080p first, then any codec ≤1080p, then anything
  (was `bv*+ba/b` = best available, often AV1 or >1080p).
- Normalization: already skipped non-AV1 sources (verified, unchanged). The format cap means YouTube sources
  normally arrive as H.264 and skip the full-file AV1 → H.264 re-encode entirely.
- **Transcription engine: openai-whisper → faster-whisper (CTranslate2, int8, CPU, all cores)**, user decision after
  the benchmark below. `WHISPER_MODEL` default `base` → `medium`; same `(transcript, segments)` shape incl. per-word
  `{word,start,end}`. openai-whisper and the separate CPU-torch install are gone from the worker image.
- Model cache: named volume `hf_cache` at `HF_HOME=/cache/huggingface` (replaces the `whisper_cache` mount), so
  rebuilds don't redownload (medium = 1.4 GB).

## Why
Baseline, 619 s video (GiGjvv48z-g, H.264 1080p source, Whisper base), job e0e9806a:
`download 61.0s | video_normalization 0.1s | audio_extraction 1.7s | transcription 111.0s | ai_analysis 11.5s |
preview_1 4.1s | preview_2 4.3s | total 193.7s`. Transcription dominates, download second.

## Whisper benchmark (8-core / 12-thread Ryzen 7 H 255, CPU, same 180 s excerpt, language=id, word timestamps on)
| engine / model | transcribe 180 s | RTF | words | text quality (Indonesian gaming chatter) |
|---|---|---|---|---|
| openai-whisper base (current) | 43.4 s | 0.24 | 80 | garbled ("patang pati aras") |
| openai-whisper small | 19.6 s | 0.11 | 55 | better, drops speech |
| openai-whisper medium | 114.6 s | 0.64 | 110 | best |
| faster-whisper base (int8) | 40.9 s | 0.23 | 126 | garbled |
| faster-whisper small (int8) | 7.9 s | 0.04 | 38 | drops a lot of speech |
| faster-whisper medium (int8) | 35.7 s | 0.20 | 105 | ≈ openai medium |

First-use model download not included (small 461 MB, medium 1.5 GB). faster-whisper keeps word timings
(`word_timestamps=True` → per-word start/end, e.g. "aku" 0.00–0.82 s), so karaoke would survive a swap.
base being slower than small is likely temperature-fallback re-decoding on noisy audio.
The user picked faster-whisper medium int8.

## Decisions & trade-offs
- No parallel audio-only download: REBUILD R-07 asks only for the format cap; parallel fetch adds a second
  download path and error handling for ~60 s on a 10-min video. Left as a follow-up.
- `.env` pins `WHISPER_MODEL=base` and `.env` is off-limits, so `medium` is set as an app_setting (DB wins over env,
  same as saving it in Settings). `.env.example` now leaves it empty so new installs get the default.
- The old `riftstorm_whisper_cache` volume is no longer mounted but was NOT deleted (holds openai models, ~2 GB).
- `vad_filter` left off: it can drop quiet speech, and word counts were already the quality signal here.

## Gotchas for future changes
- Models download on first use into `hf_cache` (medium: 1.4 GB, ~8 min here; unauthenticated HF hub). The first job
  after changing `WHISPER_MODEL` pays that once. Deleting the volume means redownloading.
- Karaoke/word-pop need word timings: any engine swap must keep `word_timestamps`.

## Verification
- Format cap: on VgwaVaLaOVQ the old selector picked `396+251 av01` (→ full re-encode), the new one `134+140 avc1`;
  the job logged `Source video codec: h264`, normalization 0.1 s.
- Real job 4b817c11 with faster-whisper medium reached review; 38 segments / 120 words with timings
  (`Pada 0.00–0.38`). Its 623 s transcription stage included the one-time model download.
- **Steady state on the baseline's 619 s audio: 189.5 s (medium) vs 111.0 s (openai base)** → slower than today's
  base on this full-length file (RTF 0.31 vs the 0.20 measured on the 180 s excerpt), but 482 words of readable
  Indonesian instead of garbled text. Net: R-07 cuts download/normalization, not transcription; transcription got
  better, not faster. `small` would be the faster option if speed matters more.
- A transient YouTube `HTTP 403` failed one job at download; no retry existed (fixed in the next commit).
- NOT verified: karaoke/word-pop rendering on a faster-whisper transcript in a final render (words verified in DB).
