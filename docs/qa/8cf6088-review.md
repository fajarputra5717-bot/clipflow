# 8cf6088 (lane-b) P4 task 4: zoom punch-ins (+ e636b24 docs) — QA 2026-10-07

Staging = exactly lane-b 8cf6088 (committed, clean tree, per Lane B).
Live on lane-c-a clip 884938b3 (it has cuts): PUT …/editor/zoom {on, intensity 100, markers [3, 12]} → 200, intensity 150 → 400,
lane-c-b PUT on A's clip → 404. Preview re-render: worker logs "Zoom: 2 punch-in(s), peak 1.30". 3 frames (1 s / 3 s / 11 s,
frames/lane-b-8cf6088-zoom.jpg): the picture is punched in at 3 s; watermark and captions keep the same size and position;
karaoke highlight still runs. Duration 31.467 s, unchanged by zoom; cuts still applied.
Playwright on staging: lane-b suite 147 passed, 0 failed; qa-multiuser.spec.js (QA_MULTIUSER=1) 16 passed, 2 skipped
(the admin-token settings check).
Bugs:
1. Low: worker/render_steps.py `_render_ctx` is module-global and one-shot. In worker.py ~5064, ensure_disk_space("render")
   inside render_vertical can raise after begin_render() and before zoom_stage(). That leaves the context set, and the next
   render_vertical without begin_render (render_clean_plate, worker.py:5312) would apply the previous clip's zoom. Rare
   (needs a disk-low failure first). Clear it in a try/finally around render_vertical, or pass the candidate explicitly.
Not verified: a final render with zoom (Lane B reports −14.2 LUFS; zoom touches video only); a zoom marker inside a cut
(this clip has one at 3 s inside cut 2.58–3.16 and rendered fine, but I didn't measure the ramp).
Merge: OK.
