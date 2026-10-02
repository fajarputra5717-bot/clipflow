# 103 · Job creation clamps the watermark height to 16–85 % (pre-P1 #5, QA Low #7) · main.py

`POST /api/jobs` snapshotted `WATERMARK_POSITION_Y` clamped to 5–95 % (and the campaign preset unclamped),
while Settings (098) only accepts 16–85 % and the worker never goes above 16 % (078). Both the setting and a
campaign preset's `center_y_pct` are now clamped to 16–85 % at creation.

**Verified:** raw DB value 5 → 16, 95 → 85, 30 → 30 (row removed afterwards).
