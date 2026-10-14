# prod 5aee650 (merge of ui-phase1 0d6dc45, UI phase 1) — post-deploy shell check, read-only, no login

- Containers: all riftstorm-* running with restarts=0 (frontend since 05:50 UTC unchanged: frontend files are a bind mount, so phase 1 went live without a restart; backend 11:01, worker/sender 12:07, notifier/postgres earlier, all fresh containers, not crash loops).
- `/version.json` = v3.222 with 5 entries (latest 222); `/` 200 (401,573 B) and contains `#flowNav`; `/ui/tokens.css`, `/editor/editor.js`, `/editor/review.js`, `/editor/editor.css` all 200.
- Login screen (the only page without an account) at 1280×800 and 390×844, light and dark: renders, body font 16 px, fields 50 px, sign-in button 44 px, no horizontal overflow, no page errors; the only console message is the expected 401 from the pre-login session probe.
- Not checked on prod (no QA account, owner decision): the dock, menu, version label and what's-new list after login. They were verified on staging (docs/qa/138ecc2-review.md); the files are identical to main 5aee650.

Result: PASS, no findings.
