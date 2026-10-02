# QA review · adf5964 · 076 campaign flow preview (mock data only)

Reviewer: Lane C · 2026-10-02 · scope: standalone `frontend/html/flow-preview.html`

Checked: no `/api/` calls and no `fetch()` (mock only, so the auth invariant doesn't apply);
localStorage access wrapped in try; delegated document-level listeners; served by the same nginx
bind mount, so it is publicly reachable at `/flow-preview.html` without the API key. Harmless while
it's mock data.

## Findings
- **Low · risk for later:** if this page is ever wired to real data, it must move to `api()`/
  `mediaUrl()` like index.html; today it's a public static page.

## Not verified
- Interaction flow in a browser.
