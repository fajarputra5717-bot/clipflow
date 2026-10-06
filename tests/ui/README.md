# ClipFlow UI smoke tests (Playwright)

## Run

```bash
tests/ui/run.sh                              # all smoke tests, desktop (1280) + mobile (390)
tests/ui/run.sh --project=desktop -g island  # any Playwright args pass through
tests/ui/run.sh --headed                     # watch it (needs a display)
npx --prefix tests/ui playwright show-report tests/ui/.report   # HTML report of the last run
```

`run.sh` installs `@playwright/test` (pinned 1.63.0) on first use and reuses the cached Chromium
(`~/.cache/ms-playwright`). Base URL: `CLIPFLOW_UI_BASE` (default `http://localhost`, the nginx
frontend). Takes about 25 s, 2 workers.

## Modes

- **Default (mocked API):** the real `index.html` from nginx, with every `/api/*` call answered by
  `fixtures.js`. No API key, deterministic, and it **never creates a job** (Lane A may be rendering).
  Writes are recorded in `api.calls` so tests can assert what the UI sent.
- **Live, read-only:** `CLIPFLOW_UI_LIVE=1 CLIPFLOW_API_TOKEN=cf_… tests/ui/run.sh specs/live.spec.js`.
  Real backend for GETs; every non-GET `/api` request is aborted and fails the test.

## What's covered (`specs/`)

| Spec | Checks |
|---|---|
| `import.spec.js` | URL validation (hint, `aria-invalid`, Analyze enabled only for YouTube), preview id, Options disclosure, language choice sent in `POST /api/jobs`, new job card appears |
| `jobs.spec.js` | Import list renders running jobs; a poll update patches the SAME card node (074); Publish list opens a job |
| `edit.spec.js` | Edit drawer opens (`.editing`, `aria-expanded`), tab switch, closes; page still clickable |
| `overlays.spec.js` | "Nothing clickable" regression: at rest, after closing Settings/Watermarks via button/Escape/backdrop, the running-jobs overlay, the version popover, and the 390 px sidebar drawer |
| `island.spec.js` | Island hidden when idle, shows title + % while a job runs, auto-expands on finish, then hides |
| `live.spec.js` | Opt-in read-only pass over the real app |

Every test fails on a page error, a console error (other than 404 media) or an unexpected
`alert/confirm/prompt`.

## Adding tests (Lane C)

```js
const { test, expect, job, candidate, nav, blockingProblems } = require("../fixtures");

test("my check", async ({ app, api }) => {   // `app` = loaded page, `api` = mutable mock state
  api.current = [job({ id: "j1", status: "rendering", progress: 50 })];  // next poll (2.2 s) shows it
  api.jobs.j1 = { ...api.current[0], candidates: [candidate("j1", { id: "c1" })] };
  await nav(app, "queue");                     // visible nav item: sidebar or bottom tab bar
  expect(await blockingProblems(app, ["#youtubeUrl"])).toEqual([]);
});
```

- `job()` / `candidate()` build objects with every field the real API returns (shapes captured from
  `/api/jobs` on 2026-10-02); override only what the test is about.
- `blockingProblems(page, probeSelectors)` returns `[]` when no closed layer (`.sheet-layer`,
  `#jobOverlay`, `#sidebarScrim`, `#versionPopover`) catches clicks and every probe control is the
  top element at its centre. Layers fade `visibility` out over ~320 ms, so after closing something
  use `expect.poll(() => blockingProblems(...)).toEqual([])`, not a single sample. Checked against
  two injected regressions (a stuck closed sheet, a stray transparent full-screen layer): both caught.
- Missing fixture endpoints answer 404 `{detail}`; add them in `mockApi()` in `fixtures.js`.
- Desktop-only / mobile-only: `test.skip(info.project.name === "mobile", "why")`.
