# QA review · 38e653d (+4983f83) · 127 shared CLIPFLOW_API_KEY removed; per-user cf_ tokens only
Reviewer: Lane C · 2026-10-06 · Owner decision. **Process:** 127's doc first cited a 'P1.5 gate PASS' that didn't exist; corrected in 4983f83. **Impact on QA:** production checks need a per-user admin cf_ token (requested from the owner); qa-multiuser spec reads QA_ADMIN_TOKEN. No code findings.
