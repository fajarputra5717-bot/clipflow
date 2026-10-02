# QA review · a51b86f (lane-b) · brief parser AI fallback; payouts: non-IDR → Unknown
Reviewer: Lane C · 2026-10-02 · brief_parser + payouts tests on a51b86f (with docs/campaigns): **OK / OK**. The AI
(`task="brief"`, via the router) only fills fields the patterns missed, every AI field is marked `unsure` (source "ai")
for confirmation in the Campaign screen, and an AI failure keeps the pattern result (+ an `unsure` entry). Payouts:
non-IDR currency → `Unknown`, matching the roadmap's IDR rule. Findings: none.
