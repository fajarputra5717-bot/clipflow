# (number assigned by Lane A at merge) · P4 task 7a — Editor Captions tab: presets, keywords, text, style, new hook (lane B)

- Captions tab (flow-preview step 5): preset tiles (this clip's own style + animation, 108; equal to the job's =
  cleared) + "Apply to all clips" (`POST …/caption-preset`, two-tap confirm); keyword highlight (word chips +
  colour swatches; sent only once touched, so the worker's AI pick (111) stays free; auto colour = 116 rule);
  hook title card (task 1); caption text (`subtitle_override` only when changed, "" = back to the transcript,
  083) + Fix typos (AI); "Style, font, size and position": style/animation (clip), font/size (job, every clip,
  `PATCH …/subtitle-style`), custom position (`edit_spec.caption_y`, 112; off = Auto); "Get another hook"
  (two-tap; reloads the editor once the new preview is rendered; 160 clears time-based edits).
- Writes reuse main's routes (candidate PATCH, subtitle-style, caption-preset, fix-subtitle-ai, new-hook); the
  editor state gains `captions` (job style, clip override, position, keywords, text, burn flag, options).
- `shared/caption_options.py`: the editor's caption catalogue (style preview table, animations, presets, fonts,
  keyword colours, ranges), served from the backend so editor.js keeps no mirror. tests/test_caption_options.py
  checks it against make_ass() (worker.py) and main's accepted names, same rules as check_caption_mirror.py.
- No native dialogs: actions beyond this clip use a two-tap confirm (`armed()`).
- Drawer pieces covered: caption style/font/size/animation + presets + keywords, caption position (112),
  subtitle text + Fix typos, new hook.
