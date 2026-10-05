# QA review · 0cea7b2 · 122 P1.5 part 2: ownership on jobs + watermark assets, 404 guard, scoped lists
Reviewer: Lane C · 2026-10-06 · deployed on production
Design: middleware 404s any `/api/jobs/{id}[/candidates/{cid}]…` and `/api/assets/watermarks/{id}…` path not owned by
the caller (so no handler can forget); no ID-taking route exists outside these prefixes on main; `list_jobs` scoped
`AND j.user_id = %s`; activity + watermark lists scoped; legacy rows assigned to the bootstrap admin
(`UPDATE … WHERE user_id IS NULL`); campaign watermarks = admin catalogue (intended). Live (admin key, read-only):
malformed/foreign ids → 404 (no 500s).
Findings: 1. **HIGH (open, part 3?)** settings still global for members (incident 2026-10-05). 2. Campaigns not scoped
yet (shared catalogue: confirm intended). 3. **Lane-b editor API bypasses this guard** (a67d58c #1).
Not verified: two-user isolation live (staging lacks P1.5; production has one user) → qa-multiuser.spec.js pending.
