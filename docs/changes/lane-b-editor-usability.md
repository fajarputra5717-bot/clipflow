# lane-b: Editor usability (audit High + owner's four fixes, 2026-10-14)

1. Preview sound (audit High): speaker button under the video (`data-ed-mute`, `setMuted()`); muted by default
   because the preview autoplays, the choice holds while the page is open. Audio edits are baked into the preview
   render (silence trim, compression, Loud & punchy, loudnorm, SFX all run in `create_preview`), so the Audio tab
   says they are heard after Render preview (`#edAudioNote`) instead of faking them live.
