# lane-b 4eb1f06 · per-clip "Loud & punchy" (loudness option 3) · Lane C · 2026-10-12
Staging = 4eb1f06 (backend + worker rebuilt). Own data: lane-c-a clip 0a5548a8 (the -15.4 / -1.1 clip), compression on, cuts + zoom + plan as before.
- API: PUT …/editor/audio accepts `loud`; default false (audio before: loud False); stored in edit_spec.audio.loud and returned by GET.
- Preview with loud on: worker "-20.2 LUFS / -6.4 dBTP → -14.4 LUFS / -1.6 dBTP (loud & punchy) (pass 1 -14.3 / -0.6, corrective pass)", 30 s render (baseline 28-32 s).
- FINAL (approve, 64 s): worker "→ -14.4 LUFS / -1.4 dBTP (loud & punchy)"; my independent ebur128 on the exported final file: I -14.4 LUFS, LRA 10.8 LU, true peak -1.4 dBFS (sample peak -1.39): ≤ -1 dBTP after AAC encoding. Closes the owner's condition for the loudness Low.
- With the toggle off the same clip still lands -15.4 / -1.1 (accepted by the owner; the loudness chip is the signal). Every trim decision is logged now ("Loudness trim …").
LOW CLOSED (loudness): condition met on a final render. No findings.
Not verified: the Audio-tab switch visually, the chip text on the Review card for a toggle-off undershoot, listening/pumping check (measured only: LRA 10.8 LU, RMS -19.6 dB), Gaming Hype default (E5 not built).
Merge: OK.
