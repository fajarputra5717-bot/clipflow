# (number assigned by Lane A at merge) · P4 task 7b — Editor Thumbnail tab (lane B)

- New Editor tab "Thumbnail" (between Watermark and Export): AI options and uploaded images in one 9:16 grid,
  tap to pick. Generate with AI (`POST …/generate-thumbnails-ai`; progress = island via /api/activity, the tab
  refreshes when the candidate leaves thumbnail_queued/rendering), Upload image (`…/thumbnail-upload` via
  authFetch, then picked), pick = candidate PATCH `selected_thumbnail_index` (sets thumbnail_path +
  thumbnail_locked, so later preview/final renders keep it). Without options: the current auto frame + a note.
- Editor state gains `thumbnail` {options [{index,url}], picked, locked, current_url, generating}; image URLs go
  through mediaUrl() (routes already in MEDIA_PATH_RE).
- Six tabs: the segmented bar scrolls horizontally instead of truncating labels; the selected tab is kept in view.
- Drawer pieces covered: thumbnails (Generate thumbnails (AI), Upload thumbnail, pick: data-gen-thumbs,
  data-upload-thumb, data-pick-thumb, the thumb slider).
