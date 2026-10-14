# sfx-library cd82e80 (217, sound effects library) — staging :8080/:8001 (backend, worker, frontend rebuilt from it)

Tested as lane-c-a / lane-c-b with generated audio (ffmpeg in a throwaway container from the staging backend image), the bundled SFX as realistic input, and Playwright for the UI. All sounds I created are deleted (0 rows left, files gone from disk).

## 1. Cross-user + auth — PASS
- lane-c-b vs lane-c-a's sound: `GET /api/sfx` (own list only, 0 of a's ids), `GET …/file`, `GET …/file?mt=<a's token>`, `GET …/file?mt=<b's token>`, `PATCH` name, `PATCH` category, `DELETE`: **all 404**; a's sound intact afterwards.
- Unauthenticated: list, file, PATCH, DELETE, POST, Freesound search/preview/save → **401**; garbage `?mt=` → 401. (Unauthenticated with a's own valid `?mt=` token serves a's file: the media-token model, same as thumbnails; not a finding.)
- Odd ids (`../../etc/passwd`, `%2e%2e%2f`, `' or 1=1--`, non-UUID, all-zero UUID) on GET/PATCH/DELETE → 404, no 500.

## 2. Uploads — PASS with one Medium
- Accepted: mp3, wav, ogg, and a WAV renamed `.mp3` (content sniffed, not the name).
- Rejected with 400 and a clear message: plain text named .mp3 ("Not an mp3, wav or ogg file"), an HLS playlist (`file:///etc/passwd`, http URL) named .mp3 (same), an mp4 and an mp4 renamed .mp3 (same), 3.4 MB wav ("File too large (max 2 MB)"), 11 s ("Too long (11.0 s; max 10 s)"), 0.2 s ("Too short (0.2 s; at least 0.3 s)"), silence ("This sound is silent"), zero bytes ("The file is empty"). Rejects created no rows.
- Levelled: a 0.9-amplitude sine saved as 48 kHz mono PCM WAV, mean −14.0 dB, peak −11.0 dB; pink noise (mean −20.6) → −15.1 / peak −3.0; tone+noise (−26.7) → −14.0 / −8.5: peaks ≤ −3 dB as stated. The 5 bundled SFX re-uploaded: all accepted.
- Hostile fields: name `<img src=x onerror=alert(1)>` and filename `../../etc/x.wav` → stored under a uuid path; rendered escaped (0 injected nodes, 0 dialogs); a 5000-char name is cut to 60.
- **Medium — good sounds rejected as "This sound is silent":** steady white noise (mean −15.2 dB, peak −10.5), a loud 50 ms noise burst with a quiet tail (mean −18.5, peak −0.9) and a similar spiky sound are refused, while the same kind of material as pink noise or tone+noise passes. Cause: `shared/sfx_library.py:120` `TRIM = "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02"` (used by `measure_cmd` and `convert_cmd`) with ffmpeg 5.1.9 (the backend's Debian build) removes the WHOLE signal for such noise (volumedetect `n_samples: 0`), and `routes_sfx.py` `_process` then answers "silent". Repro: `ffmpeg -i noise.wav -af "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.02,volumedetect" -f null -`. Fix that worked in my test on all three files (n_samples 48000): add `detection=peak` to TRIM (also in the convert filter so the saved file matches). Risk: claps, hits, rain, applause, crowd laughs are exactly this kind of signal; I could not test a real recording (no real CC0 file offline), so the real-world rate is unknown.

## 3. Categories — PASS
Assigning a sound to laugh moves it off the previous sound (the old one's category becomes null, always exactly one holder); `{"category": null}` unassigns; unknown category 400 "Unknown category" (PATCH, POST upload and Freesound search); empty PATCH body 400 "Send name and/or category"; rename works; upload with `category=laugh` assigns.

## 4. Render — PASS
lane-c-a clip, plan item `emoji 😂 {sfx: laugh}` at 4.0 s, 3 kHz test tone assigned to laugh. Preview render ~23 s. Band-pass 3 kHz ±30 Hz, window 4.0–4.9 s: laugh assigned −10.3 dB max; laugh unassigned (ding fallback) −26.8 dB; plan without sfx −27.2 dB: the assigned sound is +17 dB above the others, clearly in the render. Worker logs "SFX: 1 mixed under the speech (laugh)" for both the assigned and the ding fallback render (the name in the line stays "laugh" when ding plays: cosmetic) and nothing without the sfx item.

## 5. UI — PASS (2 Lows)
Settings → "Sound effects · 5 sounds · 0 in use" opens `#sfxSheet` at 1440×900 and 390×844, light and dark: no horizontal overflow; at 390 every control ≥ 44 px (0 small), at 1440 play buttons are 36×44 and "Find sounds" 89×32 (pointer size). Tab ×70 never leaves the sheet and every stop has a focus ring. Rename: input focused, typing then Escape cancels the rename and the sheet stays open; a second Escape closes it. File picker upload works (7 → 8 sounds), delete shows Undo and Undo restores (7 → 8). 0 page errors. Low: at 390 the category rows truncate the pack list ("Used by Funny / …", "Gaming Hype…") so you cannot read which packs use it. Low: category "play" buttons are 36 px wide on desktop (fine).

## 6. Freesound without a key — PASS
"Find sounds" disabled on all 6 category rows with the note "Freesound search isn't set up yet (the admin adds FREESOUND_API_KEY). Uploads work." Search (with and without category/q), preview and save answer **409** "Freesound isn't set up yet (FREESOUND_API_KEY)"; bad category 400. Live search untested (no key).

## Not verified
Real Freesound responses/licence re-check; real laugh recordings through the uploader; admin 404 on another user's sound (doc says admins too); the 50-sounds cap and Freesound per-user rate limits; backend image 1.04 GB on prod disk/deploy time; Funny/Meme end to end with a real laugh moment from the AI (I used a manual plan item).

Merge: OK, with the Medium (false "silent" rejection) to fix before the owner relies on Freesound/real uploads: one-word change (`detection=peak`).
