# Bundled assets and their licences

| File(s) | Source | Licence |
|---|---|---|
| `watermark.png` | Motion Klip (user-supplied) | Campaign watermark supplied by Motion Klip to participating clippers for use on campaign clips. Not owned by ClipFlow; not for redistribution. Fallback only (CLAUDE.md, Watermark). |
| `emoji/*.png` (1f602 😂, 1f62d 😭, 1f480 💀, 1f525 🔥, 1f631 😱, 1f440 👀, 1f92f 🤯, 1f60e 😎) | Google Noto Emoji, tag `v2026-09-24-unicode18_0`, https://github.com/googlefonts/noto-emoji/tree/v2026-09-24-unicode18_0/2D/svg (SVG rendered to 256 px PNG by `scripts/make_emoji.sh`) | **Apache License 2.0** (`2D/svg/LICENSE`), © 2013 Google, Inc. No on-video credit required (owner 2026-10-13); keep this notice with the files. https://www.apache.org/licenses/LICENSE-2.0 |
| `sfx/whoosh.wav`, `sfx/boom.wav`, `sfx/bass_hit.wav`, `sfx/ding.wav`, `sfx/record_scratch.wav` | Generated in-house by `scripts/make_sfx.sh` (ffmpeg synthesis, no samples) | Original work, released **CC0 1.0** (public domain) |

New SFX: CC0 sources only (owner rule), one row here per file with source URL, author and licence.
A laugh SFX is not bundled: "laugh" plays the user's own sound (217, Settings → Sound effects: uploads or CC0
Freesound picks, source URL + author + licence stored per sound in `sfx_assets`), else `ding.wav`.
