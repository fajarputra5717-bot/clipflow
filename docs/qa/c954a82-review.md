# QA review · c954a82 · 082 edit drawer tabs

Reviewer: Lane C · 2026-10-02 · scope: invariant scan of the diff

Checked: tab clicks + arrow keys go through the existing delegated document listeners
(`index.html:2877`, `:2926`), no new per-element listeners, no `fetch()`; inactive panels stay in the
DOM (`hidden`), so `applyEdits()` still reads every input; active tab kept in `editTab[cid]` across
poll re-renders; new tokens defined in both theme blocks (per change doc).

## Findings
- **Note · doesn't touch the karaoke bug.** `applyEdits()` still sends `subtitle_override`
  unconditionally (clips-2026-10-02 #1); the tabs make it easier to Apply from the Watermark/Export
  tab without touching captions, which still strips word timing.
- **Process** · no badge bump (still v2.1116). CLAUDE.md's "no `role=tab` elements any more" line
  refers to navigation; the edit tablist reintroduces `role=tab` deliberately (doc updated).

## Not verified
- Browser behaviour (Lane B's harness; the change doc reports a headless check at 1280/390).
