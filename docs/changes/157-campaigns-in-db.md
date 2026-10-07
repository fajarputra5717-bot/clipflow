# 157 · P3 part 1: campaigns in the DB (shared catalogue, created_by + visibility, paused) · main.py, shared/campaigns.py, worker, notifier

- **Why:** P3 spec part 1 (docs/tasks/P3-campaign-track.md); owner go 2026-10-07 after gate-P2.5 PASS (qa e777002).
- **Table `campaigns`:** slug PK, name, rules JSONB (the docs/campaigns rules.json schema), brief_text (verbatim),
  created_by → users (SET NULL), visibility shared|private, paused, created/updated_at. A shared catalogue (P1.5's
  exception: no user_id). Last schema statement; `/health` readiness now checks it.
- **Seed (first run only):** an empty table gets every `docs/campaigns/*.rules.json` + its brief (`brief_parser.
  extract_brief`) as shared, created by the bootstrap admin. Prod: fandra-octo, ime-roleplay, motionklip-windah
  (no brief yet). File edits no longer sync: the DB is the source; the files stay as seed/backup.
- **`shared/campaigns.py`:** `set_db_loader()` per process (backend `_load_campaign_rows`, worker + sender
  `load_campaign_rows`, notifier read-only), cached 5 s (`invalidate()` on edit); `load_all()/get()` keep their
  shape (+ visibility, created_by, paused), so every caller (rule checks, prompts, Publish, digest, payouts advice)
  is unchanged. DB unreadable or no loader (unit tests) → the files. `visible_to(rules, user)`: shared, or own
  private, or admin. `get(slug)` ignores visibility: a job's campaign always resolves.
- **API:** `GET /api/campaigns` (visible ones + visibility/paused/mine/can_edit), `GET /api/campaigns/{slug}` (full
  rules + brief_text; another user's private one → 404), `PUT /api/campaigns/{slug}` admin-only (members 403 on a
  visible one): name, rules (platforms checked against PLATFORM_LIMITS), brief_text, visibility, paused.
  `POST /api/jobs`: a hidden campaign = "Unknown campaign"; a paused one = 400 "… is paused: no new videos".
  Analyze dropdown shows paused campaigns disabled.

**Verified:** unit 15 files OK (new `test_campaigns_db.py`: rows → rules, visibility, DB-error fallback, cache,
seed rows); UI 149 passed; images import-tested; deployed idle, 6/6 up; prod read-only: backend/worker/notifier
read the DB, rules == files for all 3, admin + member see 3 (member can_edit false). Staging write checks
(member PUT 403, private 404, paused job 400) when lane-b has this.
