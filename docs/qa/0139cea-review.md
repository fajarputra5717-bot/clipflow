# QA review · 0139cea · 097 job-card and Publish-row progress as island-style capsules (P0, ui-progress-audit)

Reviewer: Lane C · 2026-10-02 · static check (Playwright cases for capsules not written yet)

`.mini-bar*` and `miniProgressBar()` are gone (0 occurrences on main); rows use `.mini-island` (black capsule,
ring fill, ready/failed states, same motion tokens; only `.is-running` animates). CLAUDE.md states the rule.
Matches the owner's capsule rule → ui-progress-audit findings 1–2 **FIXED**.

## Findings
- None. **Not verified:** visual parity with the island in a browser (QA will add a Playwright case).
