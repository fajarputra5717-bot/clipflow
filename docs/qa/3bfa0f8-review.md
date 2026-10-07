# 3bfa0f8 (157) P3 part 1: campaigns in the DB, shared catalogue with visibility + paused — QA 2026-10-07
Code: list filters campaigns.visible_to; GET → _visible_campaign (404 if not visible); PUT is admin-only (member 403 on a
visible campaign, 404 otherwise); job creation checks visible_to (main.py:1347), so a member can't import into another
user's private campaign. Live staging: lane-c-a/b list 3 shared campaigns; member PUT ime-roleplay → 403; unknown slug → 404.
Not verified: a private campaign across members (needs an admin write to shared staging data; not done per the data rule).
No bugs found.
