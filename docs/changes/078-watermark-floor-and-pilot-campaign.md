# 078 · Watermark never above 16 % + three pilot campaign fixtures (MotionKlip, IME Roleplay, Fandra Octo) · worker.py, docs/campaigns

**Watermark floor (global).** The MotionKlip placement guide (https://youtube.com/shorts/fgQXQW0XgJM,
measured on its 1080×1920 frames) marks a safe zone of x 18.3–81.5 %, y 15.9–83.9 % of the screen and
avoid zones: top UI band above 15.9 %, right icon column from x 83.9 %, bottom caption band from y 87.4 %.
Current defaults (centred, 320 px = 29.6 % wide, centre 25 % → y 21.6–28.4 %) already sit inside it.
The one gap: R-16's caption push-up could raise the mark to the 4 % edge margin, i.e. into the top
UI band. Now `WATERMARK_MIN_Y_FRAC = 0.16` bounds both `get_watermark_rect()` and the push-up in
`make_ass()`; if captions still collide at 16 % the mark stays there and a `WARNING` line is logged
(captions win the overlap rather than the mark going under the platform UI).

Verified (new worker.py loaded from /tmp in the container): default stays y=414 (21.6 %); centre 5 %
→ 16.0 % on 1080×1920 and 540×960; 400 px captions → push-up stops at y=307 (16.0 %) + warning
(was 77 px / 4 %).

**Pilot campaign** (first Campaigns test fixture): `docs/campaigns/motionklip-windah.md` (brief text
pending: placeholder note) and `motionklip-windah.rules.json` (watermark required = asset 8f7158d7 "instgrm :
@motion.klip", full opacity, the guide's zones; hashtag prefix in exact order; 6 platforms; 2 source
channels; 4 content rules; title tone examples; period/budget TBD).

**Second pilot** (`ime-roleplay.md` brief verbatim + `ime-roleplay.rules.json`): brand campaign, flat
Rp 200.000 per video at ≥ 40.000 views, max 2 eligible videos per month per platform account (admin, 2026-10-02; ≤ Rp 2.400.000/creator with one account per platform), Rp 20.000.000/month
in 4 weekly refills (W1–W4, WIB 00:00, a video counts only in its upload week), 5-hashtag prefix, 6
forbidden-content rules, the shared "Motion Klip" watermark (16 % floor, full
opacity). Discord tag "MKLP" is a manual claim step, not app work.

**Third pilot** (`fandra-octo.md`, brief text pending + `fandra-octo.rules.json`): TikTok/Instagram/
YouTube, Rp 4 per view (min 3.000, paid views capped at 500.000 = Rp 2.000.000/video), views counted at
submit time, one claim per video, from 30 Sep until the budget runs out, source = @FandraOcto
livestreams, 4-hashtag prefix, content must stay public. Open: total budget, 3.000-view rounding,
per-account limit.

**Shared watermark.** The IME and Fandra briefs link the same Drive template; it is pixel-identical to
the library's watermark.png (asset 8f7158d7, "instgrm : @motion.klip"), so all three pilots use that
asset ("Motion Klip") and no upload is needed.
