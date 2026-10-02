# 114 · "Final outdated · re-render" chip (QA Low on 108) · main.py, worker.py, tests/ui

After "Apply to all", finished clips kept their old final with nothing saying so. `mark_finals_outdated(cur,
job_id, candidate_id=None)` adds a `final_outdated` render warning ("Final outdated · re-render", shown by the
091 chips) to clips that HAVE a final, in the same transaction as the change:
- "Apply to all clips" (every final of the job),
- job subtitle style, only when the values really change (Apply re-sends the unchanged job style),
- job render options (watermark size/opacity, burn-in),
- per-clip "Apply changes" (`regenerate-preview`) and version restore (that clip).
The worker clears it when a new final completes (native render and Submagic apply).

**Verified:** IME job: apply-to-all → 8b974b8e (has a final) marked, 1a9833d4 (no final) not; unchanged
style PATCH → not marked; size 42→48 → marked (then restored); new final render → cleared (render_warnings NULL);
harness spec for the chip text.
