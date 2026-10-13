# lane-b: Noto Emoji + vision per pack (owner decisions 2026-10-13)

- Emoji PNGs (`worker/assets/emoji/*.png`, same 8 codepoints, 256 px) are now Google Noto Emoji, Apache 2.0, rendered
  from the pinned tag's `2D/svg` by `scripts/make_emoji.sh`. Twemoji (CC-BY 4.0) removed: no on-video credit needed.
  `worker/assets/LICENSES.md` updated; test checks the notice.
- Vision: `style_packs.PACKS[*].vision` (Gaming Hype, Funny / Meme on; Podcast Clean, Drama / Tension off).
  `routes_editor._vision_on()` = pack flag AND `EDIT_DIRECTOR_VISION`. Editor state `director.vision_on`; the plan hint
  no longer suggests "Regenerate to include frames" for packs without vision.
- Laugh SFX still pending (owner sends a CC0 file); Funny / Meme keeps ding.
