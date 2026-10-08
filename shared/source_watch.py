"""Source watch (P4 task 6): new uploads and finished livestreams of a YouTube channel via yt-dlp, no API key.

    items = check_channel("@FandraOcto", setting)      # [{video_id, url, title, duration, published_at, is_live_done}]

How: `yt-dlp --flat-playlist -J` on the channel's /videos and /streams tabs (cheap, one request each; title,
duration, live status), minus what the state file already knows. Upload times come from the channel's public
RSS feed (newest 15, streams included): per-video yt-dlp metadata is bot-blocked on this server. A video older
than the feed window has published_at None. Dedup state: `$SOURCE_WATCH_DIR` (default /data/source_watch) /
<channel_id>.json.
- First check of a channel only records what exists ("baseline") and returns [] so a backlog is never
  imported; pass `backfill=N` to return the latest N instead.
- A live or upcoming stream is skipped and NOT marked seen: it is returned once it has finished.
- yt-dlp goes through shared/ytdlp.py like downloads do (client + PO token, spacing, cookies retry); `setting`
  is the caller's setting(name) (worker `setting`, backend `runtime_setting`).
- Raises SourceWatchError when the channel cannot be listed. A feed failure only leaves published_at None.
Callers own scheduling, ownership and per-user dedupe (jobs by URL); this module only answers "what is new".
"""
import json
import os
import re
import subprocess
import tempfile
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from shared import ytdlp

TABS = ("videos", "streams")
LIST_LIMIT = 15            # newest N per tab: enough for any poll interval, keeps the request cheap
YTDLP_TIMEOUT = 120
SEEN_CAP = 500             # state stays small; older ids can't reappear in the newest LIST_LIMIT entries
_CHANNEL_ID = re.compile(r"^UC[\w-]{22}$")
_HANDLE = re.compile(r"^@[\w.\-]+$")


class SourceWatchError(Exception):
    pass


def state_dir() -> Path:
    return Path(os.getenv("SOURCE_WATCH_DIR") or "/data/source_watch")


def channel_base(channel: str) -> str:
    """@handle, UC… id or a youtube.com channel URL → the channel's base URL (no trailing tab)."""
    c = (channel or "").strip()
    if _HANDLE.match(c):
        return f"https://www.youtube.com/{c}"
    if _CHANNEL_ID.match(c):
        return f"https://www.youtube.com/channel/{c}"
    m = re.match(r"^https?://(?:www\.|m\.)?youtube\.com/((?:@[\w.\-]+)|(?:channel/UC[\w-]{22}))(?:/.*)?$", c)
    if m:
        return f"https://www.youtube.com/{m.group(1)}"
    raise SourceWatchError(f"Not a YouTube channel: {channel!r}")


def _exec(args: list[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(["yt-dlp", "--no-warnings", *args], capture_output=True, text=True, timeout=YTDLP_TIMEOUT)
    except subprocess.TimeoutExpired as exc:
        raise SourceWatchError("yt-dlp timed out") from exc


def make_runner(setting: Callable, check: Optional[Callable] = None) -> Callable[[list[str]], dict]:
    """The same yt-dlp hardening as downloads (167, shared/ytdlp.py): mweb client + PO-token provider, calls spaced
    across all processes, and ONE retry with the cookies file when the bot check hits. `setting` = the caller's
    setting(name) reader; `check` = e.g. the worker's check_cancelled (runs while waiting for a turn)."""
    def run(args: list[str]) -> dict:
        ytdlp.wait_turn(setting, check)
        p = _exec([*ytdlp.base_args(setting), *args])
        if p.returncode != 0 and ytdlp.is_bot_check(p.stderr):
            cookies, tmp = ytdlp.cookies_args(setting)
            if not tmp:
                raise SourceWatchError(ytdlp.BLOCKED_MESSAGE)
            try:
                ytdlp.wait_turn(setting, check)
                p = _exec([*ytdlp.base_args(setting), *cookies, *args])
            finally:
                os.unlink(tmp)
            if p.returncode != 0 and ytdlp.is_bot_check(p.stderr):
                raise SourceWatchError(ytdlp.BLOCKED_MESSAGE)
        if p.returncode != 0:
            raise SourceWatchError((p.stderr or "yt-dlp failed").strip()[-300:])
        try:
            return json.loads(p.stdout)
        except ValueError as exc:
            raise SourceWatchError("yt-dlp returned no JSON") from exc
    return run


_FEED_ENTRY = re.compile(r"<yt:videoId>([^<]+)</yt:videoId>.*?<published>([^<]+)</published>", re.S)


def _feed(channel_id: str) -> dict[str, str]:
    """video id → published ISO time from the public RSS feed; {} on any failure."""
    try:
        with urllib.request.urlopen(f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}", timeout=20) as r:
            return dict(_FEED_ENTRY.findall(r.read().decode("utf-8", "replace")))
    except Exception:
        return {}


def _load(path: Path) -> Optional[dict]:
    try:
        d = json.loads(path.read_text())
        return d if isinstance(d, dict) and isinstance(d.get("seen"), dict) else None
    except (OSError, ValueError):
        return None


def _save(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    with os.fdopen(fd, "w") as f:
        json.dump(state, f)
    os.replace(tmp, path)   # atomic: a crash never leaves half a file


def check_channel(channel: str, setting: Optional[Callable] = None, *, check: Optional[Callable] = None, backfill: int = 0,
                  runner: Optional[Callable[[list[str]], dict]] = None,
                  feed: Callable[[str], dict] = _feed,
                  directory: Optional[Path] = None, now: Optional[datetime] = None) -> list[dict]:
    if runner is None:
        if setting is None:
            raise TypeError("check_channel needs `setting` (the caller's runtime-setting reader)")
        runner = make_runner(setting, check)
    base = channel_base(channel)
    entries: list[dict] = []
    channel_id = None
    for tab in TABS:
        try:
            d = runner(["--flat-playlist", "-J", "--playlist-end", str(LIST_LIMIT), f"{base}/{tab}"])
        except SourceWatchError:
            if tab == "videos":      # no /streams tab (channel never streamed) is fine; no /videos is not
                raise
            continue
        channel_id = channel_id or d.get("channel_id")
        for e in d.get("entries") or []:
            if e.get("id") and not any(x["id"] == e["id"] for x in entries):
                entries.append(e)
    if not channel_id:
        raise SourceWatchError("Channel id not found")
    path = (directory or state_dir()) / f"{channel_id}.json"
    state = _load(path)
    stamp = (now or datetime.now(timezone.utc)).isoformat()
    finished = [e for e in entries if e.get("live_status") not in ("is_live", "is_upcoming")]

    if state is None:                                    # baseline
        newest = finished[:backfill] if backfill > 0 else []
        state = {"channel_id": channel_id, "baselined_at": stamp,
                 "seen": {e["id"]: stamp for e in finished if e not in newest}}
        todo = newest
    else:
        todo = [e for e in finished if e["id"] not in state["seen"]]

    published = feed(channel_id) if todo else {}
    out = []
    for e in todo:
        state["seen"][e["id"]] = stamp
        out.append({
            "video_id": e["id"], "url": f"https://www.youtube.com/watch?v={e['id']}",
            "title": e.get("title") or "", "duration": e.get("duration"),
            "published_at": published.get(e["id"]),
            "is_live_done": e.get("live_status") == "was_live",
        })
    if len(state["seen"]) > SEEN_CAP:
        keep = sorted(state["seen"].items(), key=lambda kv: kv[1], reverse=True)[:SEEN_CAP]
        state["seen"] = dict(keep)
    _save(path, state)
    return out
