# QA review · cdf1b40 · 074 keyed in-place job cards (v2.1115)

Reviewer: Lane C · 2026-10-02 · scope: invariant scan of the diff, not a full UI test

Checked: no bare `fetch()` added; `innerHTML` only on one-time card creation, keyed icon swaps
(`dataset.key`) and the error/empty states, never on per-poll patching (matches its own rule);
no new per-element listeners. Version badge bumped.

## Findings
- None blocking. **Low:** the actions row is rebuilt via `innerHTML` when its key changes
  (Cancel/Retry), which drops focus if the user was tabbed onto Cancel at that moment.

## Not verified
- Live behaviour in a browser (no Playwright run by QA yet; harness owned by Lane B in tests/ui/).
