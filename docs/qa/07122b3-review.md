# lane-b c36bbc6 + 07122b3 (Auto Edit E1 fixes, loudness trim v2) · Lane C re-check · 2026-10-12
Staging = 07122b3 (worker image has the new trim code). Own data: lane-c-a clip 0a5548a8 (cuts 8.42-10.26 / 23.66-24.02, manual zoom 5/12/26, compression on). Unit tests/test_edit_director, test_retention, test_fillers OK.
- FIXED (Medium) restraint: new plan has 4 items (shake 1.18, shake 15.72, punch 20.9, shake 30.84; vision True, 6.4 s); output-time gaps including the manual zoom markers: 3.72-5.18 s (min 3.72 ≥ 3). The earlier 0.4 s / 1.2 s neighbours are gone.
- FIXED (Low): PUT /plan toggles by id and keeps the rest (4 items kept); unknown id → 400 "Unknown plan item 'nope'"; plan POST 6.4 s this time (synchronous, 33 s earlier: still the 60 s edge; noted by lane-b).
- ACCEPTED (unreproduced "0 from the edit plan"): lane-b's explanation (render queued before the plan call returned; v4 snapshot has 0 items) fits my sequence; UI now disables Render while a plan generates (not checked visually).
- Preview render with the plan: 30 s (baseline 32 s), worker "Zoom: 4 punch-in(s) (1 from the edit plan)".
- NOT FIXED here (Low, loudness trim v2): on this ordinary clip with compression the preview still logs -27.5 LUFS / -9.6 dBTP → -15.4 LUFS / -1.1 dBTP (pass 1 -14.9 / -0.9, corrective pass) with no "(trim …)" note, so neither the retarget nor the gain try was kept although the code is in the running worker (LOUDNESS_TRIM_TOL, "Up to two trims"). Lane-b's "6 of 7 land -14.0..-14.4" does not hold for this clip; it is not a clipped source. 1.4 LU under target, TP fine. Likely the peak guard (trimmed tp must stay ≤ max(-1.0, after tp) ) rejects it: a very quiet source (-27.5 LUFS) needs +13 dB so the limiter eats the loudness.
Not verified: final render loudness with trim v2, the Render-disabled-while-planning UI, Effects → Auto edit UI visually.
Merge: OK (E1 fixes); loudness trim stays a Low.

## Owner decision (2026-10-12): loudness = option 3
Per-clip "Loud & punchy" toggle, on by default in Gaming Hype only; otherwise peaky sources may undershoot -14 with the chip shown. Not a blocker. The Low (this clip -15.4 / -1.1) stays open until Lane B ships the toggle; close it when a FINAL render with the toggle on measures true peak ≤ -1 dBTP after AAC encoding (ebur128 on the exported file), and the toggle-off path still shows the chip instead of clipping.
