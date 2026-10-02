# QA review · 076ab7b · 088 pin PyAV < 19

Reviewer: Lane C · 2026-10-02

`worker/requirements.txt` adds `av<19` (PyAV 19 dropped `av.open(metadata_errors=...)`, which
faster-whisper 1.2 `decode_audio` passes). Deployed worker: **av 18.1.0, faster-whisper 1.2.1** (checked
in the container). Transcription is exercised by QA's e2e job (see fd96c63-review).

## Findings
- **Low · only one dependency pinned.** Other worker deps can float on the next rebuild in the same way
  (this break came from an unpinned transitive dep). Suggest a lock/constraints file for the worker image.

## Not verified
- Backend image (doesn't use PyAV).
