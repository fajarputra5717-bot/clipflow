"""yt-dlp hardening against YouTube's "Sign in to confirm you're not a bot" (167).

One place for every yt-dlp call (worker downloads + metadata, Lane B's source_watch):

  base_args(setting)         client + PO-token provider args (mweb + the `pot` bgutil sidecar; tested 2026-10-09:
                             web/tv/android_vr all hit the bot check from this server, mweb + PO token works)
  wait_turn(setting, check)  spaces yt-dlp calls across ALL processes (flock'd timestamp on /data)
  is_bot_check(text)         the bot-check failure, as yt-dlp prints it
  cookies_args(setting)      optional cookies file (read-only mount), used ONLY to retry after a bot check;
                             copied to a temp file because yt-dlp writes the jar back
"""

from __future__ import annotations

import fcntl
import os
import random
import re
import shutil
import tempfile
import time
from pathlib import Path

BOT_CHECK_RE = re.compile(r"confirm you.{0,3}re not a bot", re.IGNORECASE)
BLOCKED_MESSAGE = ("YouTube blocked this download (bot check). Retry in about an hour; if it keeps happening, "
                   "ask the admin to add a YouTube cookies file (YTDLP_COOKIES_FILE).")
LAST_CALL_FILE = Path(os.getenv("YTDLP_LAST_CALL_FILE", "/data/.ytdlp-last-call"))


def is_bot_check(text) -> bool:
    return bool(BOT_CHECK_RE.search(str(text or "")))


def base_args(setting) -> list[str]:
    args = []
    client = (setting("YTDLP_PLAYER_CLIENT") or "").strip()
    if client:
        args += ["--extractor-args", f"youtube:player_client={client}"]
    pot = (setting("YTDLP_POT_URL") or "").strip()
    if pot:
        args += ["--extractor-args", f"youtubepot-bgutilhttp:base_url={pot}"]
    return args


def wait_turn(setting, check=None) -> float:
    """Block until YTDLP_MIN_GAP_SECONDS (+ up to 30 % jitter) passed since the last yt-dlp call in any process.
    `check` (e.g. the worker's check_cancelled) runs every second while waiting. Returns the seconds waited."""
    try:
        gap = float(setting("YTDLP_MIN_GAP_SECONDS") or 0)
    except ValueError:
        gap = 0.0
    if gap <= 0:
        return 0.0
    waited = 0.0
    LAST_CALL_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LAST_CALL_FILE, "a+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            fh.seek(0)
            try:
                last = float(fh.read().strip() or 0)
            except ValueError:
                last = 0.0
            due = last + gap * random.uniform(1.0, 1.3)
            while (left := due - time.time()) > 0:
                if check:
                    check()
                step = min(1.0, left)
                time.sleep(step)
                waited += step
            fh.seek(0)
            fh.truncate()
            fh.write(f"{time.time():.3f}")
            fh.flush()
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)
    return waited


def cookies_file(setting):
    path = (setting("YTDLP_COOKIES_FILE") or "").strip()
    return path if path and os.path.isfile(path) and os.path.getsize(path) > 0 else None


def cookies_args(setting):
    """(["--cookies", tmp_copy], tmp_copy) or ([], None) when no cookies file is mounted. Delete tmp_copy after."""
    src = cookies_file(setting)
    if not src:
        return [], None
    fd, tmp = tempfile.mkstemp(prefix="ytc-", suffix=".txt")
    os.close(fd)
    shutil.copyfile(src, tmp)
    os.chmod(tmp, 0o600)
    return ["--cookies", tmp], tmp
