# 165 · Old drawer: Captions / Effects / Audio tabs removed (lane-b merge follow-up, 2026-10-07)

- Per the drawer removal protocol: 163 (Effects + Audio) and 164 (Captions: style/font/size/animation, presets,
  keywords, position, text + Fix typos, new hook) gave these pieces a home in the Editor page, so the old panel
  (Review card → "All edits") drops them. It keeps Export + Watermark, description, thumbnail; a note links to the Editor.
- `applyEdits()` now sends only description, thumbnail and render options: sending the panel's stale caption inputs
  would overwrite the Editor's choices.
- UI tests: keywords.spec / presets.spec removed (covered by editor.spec's Captions tests); editor.spec picks the first
  "Open editor" link. 167 passed.
- Left for P4 7e: the now-unused caption helpers in index.html (all null-guarded) go with the rest of the drawer.
