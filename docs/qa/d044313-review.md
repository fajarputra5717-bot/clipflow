# QA review · d044313 · 106 UI shell: flow-preview stepper as top-level navigation, Review rename, Settings gear (P1 task 0a)

Reviewer: Lane C · 2026-10-02

Checked: `FLOW_STEPS` = mock's 8 steps in order; Campaign/Auto-import/Track "Coming in P3", Schedule/Publish
"Coming in P2" (disabled `<button>`s), Analyze = Import view, Review = renamed Publish view, Editor disabled until a
clip is picked ("Open a clip in Review"); page title follows; wording "moved to Review"; toolbar gear opens the
Settings sheet (`data-nav="settings"`, delegated); `renderFlow()` re-renders only when its HTML changes (keyed by
`dataset.html`); reduced-motion guard; island untouched. Playwright (main's tests/ui incl. new `shell.spec.js`,
plus QA's capsule spec): 27 passed, 4 skipped, 1 failed: `edit.spec` desktop. **Not a committed regression**: it
passes 3/3 against 105, 106 and 107 served from git; it fails only against the live nginx frontend, which serves
Lane A's uncommitted caption-presets work (working tree, bind mount). Re-run when that lands.

## Findings
1. **Low · mobile: disabled steps don't say why** (sub-label hidden ≤ 600 px). See ui-shell-vs-mock-2026-10-02 #6.
2. **Low · two navigations on mobile** (stepper + bottom tab bar with Analyze/Review); mock has one.
3. Visual differences to the mock: ui-shell-vs-mock-2026-10-02.

## Process
- QA's live-UI runs hit uncommitted work because the frontend is a bind mount of the working tree. QA will run the
  Playwright gate against a git-served copy of the gated commit, and the live stack separately.
