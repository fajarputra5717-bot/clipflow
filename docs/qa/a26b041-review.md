# lane-b ab7d18b + a26b041 — Noto Emoji (Apache 2.0) + vision per style pack (staging :8080)

Staging = a26b041 (backend/worker restarted 6 min before the check; up and healthy).

## ab7d18b — Noto Emoji
- `tests/qa/check_asset_licenses.py` on the a26b041 tree: "all assets have a license entry". The LICENSES.md emoji row names Noto Emoji, tag v2026-09-24-unicode18_0, Apache 2.0, source URL and `scripts/make_emoji.sh`; the pinned tag's `2D/svg/LICENSE` fetched and it is Apache 2.0 (© 2013 Google). Twemoji / CC-BY text is gone, so the open CC-BY credit question is closed (owner: no on-video credit; Apache 2.0 needs the notice kept with the files, which LICENSES.md does).
- Render (fresh preview, lane-c-a clip 0a5548a8, 1 frame): the 😂 pop at output 4.5 s is the Noto face, clean alpha, upper-right, clear of watermark, caption area and bottom UI. Log "Emoji: 2 pop(s) from the edit plan".
- The second pop (💀) did not show because my test time (source 10.0 s) fell inside a removed range (8.42–10.26): the pop is dropped when its moment is cut, as designed (`to_output` → None). Only 💀's PNG was therefore not seen on video; lane-b's synthetic frame check covers it.
- `tests.test_overlays_sfx` 7/7, `test_edit_director` 13/13 OK.

## a26b041 — vision per pack
- `vision_on` from the editor state on staging (lane-c-a clip, pack set via POST editor/pack): podcast_clean False, gaming_hype True, funny_meme True, drama_tension False (matches the owner decision). `_vision_on` = pack flag AND EDIT_DIRECTOR_VISION (global off still wins); the plan hint drops "Regenerate to include frames" when vision is off. `tests.test_style_packs` OK.

## Findings
- None (no Low). Note: a pack switch clears the plan items (existing behaviour, my plan had to be re-PUT).

## Not verified
- Real AI plan call with frames per pack (no vision call made: it would use the staging AI key); Funny/Meme laugh SFX is still the stand-in until the owner's CC0 file lands.
- The 💀 asset on a real render; UI view of the hint text (lane-b UI specs 223 passed).

Merge: OK
