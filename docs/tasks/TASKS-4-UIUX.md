# ClipFlow — stream: UI/UX & FUNCTION

Segmented task stream. Companion streams: `TASKS-4-VIDEO.md`,
`TASKS-4-SECURITY.md`.

Read `CLAUDE.md`, `docs/changes/INDEX.md`, and — if it exists —
`docs/changes/ui-audit.md` from the QA pass. **Check what already
landed before starting anything here**; several items below were
specified in `TASKS-UI-QA.md` and may be done.

Ground rules unchanged: one task = one commit, `docs/changes/NNN` +
INDEX line, compile checks, honest verification notes.

---

## Standing rule for this stream

Everything here is presentation and interaction. **No behaviour
changes, no new render capability, no schema changes** except where a
task explicitly says so. If a change alters what gets submitted or
rendered, it belongs in the VIDEO stream instead.

---

## Task 1 — Carry-over check (do this first, it's cheap)

Open `docs/changes/INDEX.md` and confirm the status of each of these.
Report which are done, which are partial, which never landed. Don't
redo finished work.

- Pill motion (layout-property animation, `backdrop-filter` stutter,
  hysteresis) — `TASKS-UI-QA.md` task 2
- Job island split back onto its own bar — task 3
- Job-card thumbnails instead of grey placeholders — task 4
- One consistent collapse/expand affordance — task 5
- Status badge semantics + contrast — task 6
- Accessibility sweep — task 7

Anything still open stays in this stream at its original priority.

---

## Task 2 — Real-browser verification harness

Multiple UI changes have shipped verified only by jsdom and code
tracing, and at least one motion problem got through that way. That's
a process gap, not a one-off.

- Check whether Playwright/Chromium is actually available in the dev
  environment. If it is, add a minimal smoke test: load the page, click
  each tab, expand each disclosure, open a candidate's edit drawer,
  assert no console errors.
- If it genuinely isn't available, say so plainly and instead produce
  `docs/ui-harness.html` — a standalone page that mounts the motion-
  critical components in isolation so a human can judge them in one
  click.
- **Do not describe motion work as verified when it was only read.**

---

## Task 3 — Edit drawer information architecture

The drawer now holds: subtitle text, style, font, size, animation,
description, thumbnails, version history, Submagic, watermark size,
burn-in toggle, and (from the VIDEO stream) position controls. That is
too much for one flat scroll.

- Group into **Content** (text, title, description) / **Style** (font,
  size, animation, preset) / **Layout** (watermark + subtitle position,
  burn-in) / **Output** (thumbnail, render, Submagic).
- Tabs or a sectioned accordion — pick one and justify it in the
  changelog against the alternative.
- **Apply changes stays persistently visible.** It is the primary
  action; it must never scroll out of reach.
- Remember which section was last open, per session.

---

## Task 4 — Feedback and error states

Most failure paths still call `alert()`. That's a modal interrupt for
something that should be inline and recoverable.

- Replace `alert()` with inline, dismissible messaging attached to the
  thing that failed, saying what to do next.
- Consistent loading states — several buttons currently swap their own
  label text ad hoc.
- Optimistic UI where it's safe (rating, thumbnail pick); never for
  anything that spends money or triggers a render.
- A toast/undo affordance for destructive actions. Version history
  already exists — surface it as undo rather than building a second
  mechanism.

---

## Task 5 — Keyboard workflow

This app is used repetitively on a queue of candidates. That's exactly
what shortcuts are for.

- `J`/`K` or arrows to move between candidates; `E` edit; `⌘/Ctrl+S`
  apply changes; `Esc` close drawer/drawer-overlay.
- A `?` shortcut sheet.
- Verify tab order follows visual order after the sidebar move.
- Every custom `div`-as-button responds to Enter/Space.

---

## Task 6 — Batch operations

From `TASKS-2.md` task 9, if it hasn't landed. Real channel operation
is batch, not one clip at a time.

- Multi-select candidates → render all / approve all.
- Queue multiple source URLs in one action.
- A visible queue view showing what's pending, in order, with the
  ability to reorder or cancel individual items.

---

## Order

Task 1 (carry-over audit) → 2 (verification harness) → 3 (IA) →
4 (feedback) → 5 (keyboard) → 6 (batch).

Task 2 before the rest: without it, every subsequent UI change ships
on the same unverified basis as the ones being fixed.
