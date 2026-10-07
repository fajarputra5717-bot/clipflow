"""ClipFlow notifier: outbound-only Telegram alerts (change 066).

Polls Postgres (read-only session), the backend /health endpoint and free
space on DATA_ROOT, and sends a Telegram message for each new event:
review ready, final render done, job/candidate failed, hooks produced by
the fallback provider, backend down/recovered, disk low/recovered, and
one daily summary at SUMMARY_HOUR (WIB, UTC+7).

No inbound surface: it never calls getUpdates and listens on no port.
Sent events are remembered in STATE_PATH so a restart doesn't resend.
The first run with no state file records everything already in the DB
as seen (baseline) instead of alerting about history.

`python notifier.py --send-summary` sends one summary now and exits.

P2 part 6b (142): plus one personal digest per user at DIGEST_HOUR (09:00 WIB) to
that user's OWN chat (user_settings TELEGRAM_CHAT_ID; an admin without one gets it
in TELEGRAM_CHAT_ID; a member never does), built by shared/digest.py from
read-only queries. `--preview-digest` prints every user's digest and sends nothing.
"""

import json
import os
import re
import shutil
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import psycopg
import requests

from shared import campaigns, digest  # 142: copied into the image; campaign rules mounted at /app/campaigns

WIB = timezone(timedelta(hours=7))  # Asia/Jakarta, no DST


def env_int(name, default):
    try:
        return int(os.getenv(name) or default)
    except ValueError:
        return default


def database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    # Same composition as docker-compose's x-app-env, for a bare `docker run --env-file .env`.
    user, pw, db = (os.getenv(k) for k in ("POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB"))
    if user and pw and db:
        host = os.getenv("POSTGRES_HOST") or "postgres"
        return f"postgresql://{user}:{pw}@{host}:5432/{db}"
    return None


TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or ""
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or ""
HEALTH_URL = os.getenv("BACKEND_HEALTH_URL") or "http://backend:8000/health"
DATA_ROOT = Path(os.getenv("DATA_ROOT") or "/data")
STATE_PATH = Path(os.getenv("STATE_PATH") or "/data/notifier/state.json")
POLL_SECONDS = env_int("POLL_SECONDS", 30)
DISK_ALERT_PCT = env_int("DISK_ALERT_PCT", 15)
MAX_PER_HOUR = env_int("MAX_PER_HOUR", 20)
SUMMARY_HOUR = env_int("SUMMARY_HOUR", 8)
DIGEST_HOUR = env_int("DIGEST_HOUR", 9)
HEALTH_FAILS_TO_ALERT = 2
LOOKBACK = "48 hours"  # events older than this are never alerted
TAG = os.getenv("NOTIFIER_TAG") or ""  # e.g. "[TEST] " for a trial run


def log(msg):
    print(f"[notifier] {datetime.now(WIB):%Y-%m-%d %H:%M:%S} {scrub(msg, 1000)}", flush=True)


# ------------------------------------------------------------------
# Scrubbing: error text comes from yt-dlp/ffmpeg/AI SDKs and can carry
# keys, signed URLs or credentials. Redact before it leaves the box.
# ------------------------------------------------------------------

_SCRUB = [
    (re.compile(r"\bbot\d{6,}:[A-Za-z0-9_-]{20,}"), "bot[redacted]"),
    (re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{30,}\b"), "[redacted-token]"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{20,}"), "[redacted-key]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"), "[redacted-key]"),
    (re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{8,}"), r"\1 [redacted]"),
    (re.compile(r"(?i)\b([\w-]*(?:key|token|secret|password|passwd|pwd|signature|sig|auth)[\w-]*)"
                r"(\"?\s*[:=]\s*\"?)[^\s\"',;&]+"), r"\1\2[redacted]"),
    (re.compile(r"(\b[a-z][a-z0-9+.-]*://)[^/\s:@]+:[^/\s@]+@", re.I), r"\1[redacted]@"),
    (re.compile(r"(\bhttps?://[^\s?#]+)[?#][^\s]*", re.I), r"\1?[…]"),
    (re.compile(r"\b[A-Za-z0-9_\-+/=]{40,}\b"), "[redacted]"),
]


def scrub(text, limit=300):
    s = str(text or "")
    for pattern, repl in _SCRUB:
        s = pattern.sub(repl, s)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


# ------------------------------------------------------------------
# State
# ------------------------------------------------------------------

def load_state():
    try:
        state = json.loads(STATE_PATH.read_text())
        state.setdefault("sent", {})
        state.setdefault("sent_times", [])
        state.setdefault("health_fails", 0)
        state.setdefault("backend_down", False)
        state.setdefault("disk_low", False)
        state.setdefault("summary_date", "")
        state.setdefault("digest_dates", {})
        state["fresh"] = False
        return state
    except FileNotFoundError:
        return {"sent": {}, "sent_times": [], "health_fails": 0, "backend_down": False,
                "disk_low": False, "summary_date": "", "fresh": True}
    except (OSError, ValueError) as exc:
        # A corrupt file must not turn into a resend storm: treat as fresh (baseline).
        log(f"state unreadable ({type(exc).__name__}); re-baselining")
        return {"sent": {}, "sent_times": [], "health_fails": 0, "backend_down": False,
                "disk_low": False, "summary_date": "", "fresh": True}


def save_state(state):
    cutoff = time.time() - 30 * 86400
    state["sent"] = {k: t for k, t in state["sent"].items() if t >= cutoff}
    data = {k: v for k, v in state.items() if k != "fresh"}
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True))
    os.replace(tmp, STATE_PATH)


# ------------------------------------------------------------------
# Telegram (outbound only)
# ------------------------------------------------------------------

def budget_left(state):
    hour_ago = time.time() - 3600
    state["sent_times"] = [t for t in state["sent_times"] if t > hour_ago]
    return MAX_PER_HOUR - len(state["sent_times"])


def send(state, text, chat_id=None):
    """True if Telegram accepted the message. Never logs the token. chat_id None = the ops chat."""
    if budget_left(state) <= 0:
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            json={"chat_id": chat_id or CHAT_ID, "text": TAG + text, "disable_web_page_preview": True},
            timeout=15,
        )
    except requests.RequestException as exc:
        log(f"telegram send failed: {type(exc).__name__}")  # str(exc) would contain the URL + token
        return False
    if r.status_code == 429:
        retry = (r.json().get("parameters") or {}).get("retry_after", 30) if r.content else 30
        log(f"telegram rate-limited, retry_after={retry}s")
        time.sleep(min(int(retry), 60))
        return False
    if not r.ok:
        log(f"telegram HTTP {r.status_code}: {scrub(r.text, 200)}")
        return False
    state["sent_times"].append(time.time())
    log(f"sent message_id={r.json().get('result', {}).get('message_id')}: {text.splitlines()[0]}")
    return True


# ------------------------------------------------------------------
# Event collection (read-only DB session)
# ------------------------------------------------------------------

def connect():
    return psycopg.connect(
        database_url(),
        autocommit=True,
        connect_timeout=10,
        options="-c default_transaction_read_only=on -c statement_timeout=15000",
    )


def load_campaign_rows():
    """157: campaigns come from the DB (shared/campaigns.py falls back to the mounted files on error)."""
    with connect() as conn:
        cur = conn.execute("SELECT slug, name, rules, brief_text, created_by, visibility, paused, created_at, updated_at FROM campaigns")
        keys = [d.name for d in cur.description]
        return [dict(zip(keys, r)) for r in cur.fetchall()]


campaigns.set_db_loader(load_campaign_rows)

TITLE = "COALESCE(NULLIF(j.custom_title, ''), NULLIF(sv.title, ''), 'Job ' || LEFT(j.id, 8))"
CAND_TITLE = "COALESCE(NULLIF(c.manual_title, ''), NULLIF(c.title, ''), NULLIF(c.ai_title, ''), 'Clip ' || (c.clip_index + 1))"


def fallback_is_configured(cur):
    cur.execute("SELECT value FROM app_settings WHERE key = 'CLIP_ANALYSIS_PROVIDER'")
    row = cur.fetchone()
    return bool(row) and (row[0] or "").strip().lower() == "claude"


def collect_events(conn):
    """[(key, text)] in alert order. Keys include a timestamp so a job that
    fails again later (after a retry) alerts again."""
    events = []
    with conn.cursor() as cur:
        cur.execute(f"""
            SELECT j.id, {TITLE}, COALESCE(j.review_ready_at, j.updated_at),
                   (SELECT COUNT(*) FROM clip_candidates c WHERE c.job_id = j.id)
            FROM jobs j LEFT JOIN source_videos sv ON sv.id = j.source_video_id
            WHERE j.status = 'review' AND j.updated_at > NOW() - INTERVAL '{LOOKBACK}'
            ORDER BY j.updated_at""")
        for jid, title, ts, n in cur.fetchall():
            events.append((f"review:{jid}:{ts.isoformat()}",
                           f"🎬 Ready for review: {title}\n{n} clip{'s' if n != 1 else ''} to check."))

        cur.execute(f"""
            SELECT j.id, j.status, {TITLE}, j.error_stage, j.error_message, j.updated_at
            FROM jobs j LEFT JOIN source_videos sv ON sv.id = j.source_video_id
            WHERE j.status IN ('failed', 'partial_failure')
              AND j.updated_at > NOW() - INTERVAL '{LOOKBACK}'
            ORDER BY j.updated_at""")
        for jid, status, title, stage, err, ts in cur.fetchall():
            label = "Job partially failed" if status == "partial_failure" else "Job failed"
            events.append((f"jobfail:{jid}:{ts.isoformat()}",
                           f"❌ {label}: {title}\nStage: {scrub(stage, 60) or 'unknown'}\n{scrub(err) or 'No error message.'}"))

        cur.execute(f"""
            SELECT c.id, c.status, {TITLE}, {CAND_TITLE}, c.error_stage, c.error_message,
                   COALESCE(c.rendered_at, c.updated_at)
            FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
            LEFT JOIN source_videos sv ON sv.id = j.source_video_id
            WHERE ((c.status = 'completed' AND c.final_path IS NOT NULL) OR c.status = 'failed')
              AND c.updated_at > NOW() - INTERVAL '{LOOKBACK}'
            ORDER BY c.updated_at""")
        for cid, status, jtitle, ctitle, stage, err, ts in cur.fetchall():
            if status == "completed":
                events.append((f"final:{cid}:{ts.isoformat()}",
                               f"✅ Final render done: {ctitle}\nJob: {jtitle}"))
            else:
                events.append((f"candfail:{cid}:{ts.isoformat()}",
                               f"❌ Clip failed: {ctitle}\nJob: {jtitle}\nStage: {scrub(stage, 60) or 'unknown'}\n"
                               f"{scrub(err) or 'No error message.'}"))

        if not fallback_is_configured(cur):
            cur.execute(f"""
                SELECT j.id, {TITLE}, COUNT(*)
                FROM clip_candidates c JOIN jobs j ON j.id = c.job_id
                LEFT JOIN source_videos sv ON sv.id = j.source_video_id
                WHERE c.hook_provider = 'claude' AND c.created_at > NOW() - INTERVAL '{LOOKBACK}'
                GROUP BY j.id, 2""")
            for jid, title, n in cur.fetchall():
                events.append((f"fallback:{jid}",
                               f"⚠️ Gemini overloaded, Claude used: {n} hook{'s' if n != 1 else ''} in {title}"))
    return events


def summary_text(conn):
    with conn.cursor() as cur:
        cur.execute("""
            SELECT
              (SELECT COUNT(*) FROM jobs WHERE status IN ('review', 'completed')
                 AND COALESCE(completed_at, review_ready_at, updated_at) > NOW() - INTERVAL '24 hours'),
              (SELECT COUNT(*) FROM jobs WHERE status IN ('failed', 'partial_failure')
                 AND updated_at > NOW() - INTERVAL '24 hours'),
              (SELECT COUNT(*) FROM clip_candidates WHERE rendered_at > NOW() - INTERVAL '24 hours'),
              (SELECT COUNT(*) FROM clip_candidates WHERE status = 'failed'
                 AND updated_at > NOW() - INTERVAL '24 hours')""")
        done, failed, rendered, cfailed = cur.fetchone()
    pct, free_gb = disk_free()
    return (f"☀️ ClipFlow daily summary ({datetime.now(WIB):%a %d %b})\n"
            f"Jobs done: {done} · failed: {failed}\n"
            f"Clips rendered: {rendered} · clip failures: {cfailed}\n"
            f"Disk free: {pct:.0f}% ({free_gb:.0f} GB)")


def digest_targets(conn):
    """[(user_id, username, chat_id)] for active users with a chat (own, or the ops chat for admins)."""
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.role, NULLIF(TRIM(us.value), '')
            FROM users u
            LEFT JOIN user_settings us ON us.user_id = u.id AND us.key = 'TELEGRAM_CHAT_ID'
            WHERE u.active ORDER BY u.created_at
            """
        )
        rows = cur.fetchall()
    out = []
    for uid, name, role, own in rows:
        chat = own or (CHAT_ID if role == "admin" else None)
        if chat:
            out.append((uid, name, chat))
    return out


def digest_for(conn, user_id, now):
    with conn.cursor() as cur:
        return digest.build(cur, user_id, now)


def disk_free():
    u = shutil.disk_usage(DATA_ROOT)
    return 100.0 * u.free / u.total, u.free / 1e9


def backend_healthy():
    try:
        return requests.get(HEALTH_URL, timeout=5).status_code == 200
    except requests.RequestException:
        return False


# ------------------------------------------------------------------
# One poll
# ------------------------------------------------------------------

def poll(state):
    now = time.time()
    outbox = []  # (key or None, text, on_sent callback)

    # Backend health: alert once after N consecutive failures, once on recovery.
    if backend_healthy():
        if state["backend_down"]:
            outbox.append(("health:up", "✅ Backend recovered: /health is OK again.",
                           lambda: state.update(backend_down=False)))
        state["health_fails"] = 0
    else:
        state["health_fails"] += 1
        if state["health_fails"] >= HEALTH_FAILS_TO_ALERT and not state["backend_down"]:
            outbox.append(("health:down", f"🔴 Backend /health failing ({state['health_fails']} checks in a row).",
                           lambda: state.update(backend_down=True)))

    # Disk: alert on crossing below the threshold, re-arm 2 points above it.
    pct, free_gb = disk_free()
    if pct < DISK_ALERT_PCT and not state["disk_low"]:
        outbox.append(("disk:low", f"💾 Disk low on {DATA_ROOT}: {pct:.1f}% free ({free_gb:.0f} GB).",
                       lambda: state.update(disk_low=True)))
    elif pct >= DISK_ALERT_PCT + 2 and state["disk_low"]:
        outbox.append(("disk:ok", f"💾 Disk OK again: {pct:.1f}% free.", lambda: state.update(disk_low=False)))

    try:
        with connect() as conn:
            for key, text in collect_events(conn):
                if key not in state["sent"]:
                    outbox.append((key, text, None))

            today = datetime.now(WIB).date().isoformat()
            if datetime.now(WIB).hour >= SUMMARY_HOUR and state["summary_date"] != today:
                outbox.append((None, summary_text(conn), lambda: state.update(summary_date=today)))

            # 142: one personal digest per user per day, at/after DIGEST_HOUR (catches up after a restart).
            if datetime.now(WIB).hour >= DIGEST_HOUR:
                for uid, name, chat in digest_targets(conn):
                    if state["digest_dates"].get(uid) == today:
                        continue
                    mark = (lambda u=uid: state["digest_dates"].__setitem__(u, today))
                    try:
                        text = digest_for(conn, uid, datetime.now(timezone.utc))
                    except Exception as exc:  # one user's bad data must not stop the others
                        log(f"digest for {name} failed: {type(exc).__name__}: {exc}")
                        continue
                    if text:
                        outbox.append((None, text, mark, chat))
                    else:
                        mark()  # nothing to say today
    except psycopg.Error as exc:
        log(f"db error: {type(exc).__name__}: {exc}")

    if state["fresh"]:
        # First run: history is not news. Mark it seen, send nothing.
        for key, _, on_sent, *_ in outbox:
            if key and not key.startswith(("health:", "disk:")):
                state["sent"][key] = now
            elif key is None and on_sent:
                on_sent()
        log(f"baseline: {len(state['sent'])} existing events marked as seen")
        state["fresh"] = False
        outbox = [o for o in outbox if o[0] and o[0].startswith(("health:", "disk:"))]

    for i, (key, text, on_sent, *chat) in enumerate(outbox):
        if budget_left(state) <= 0:
            log(f"hourly cap {MAX_PER_HOUR} reached; {len(outbox) - i} pending, retried next poll")
            break
        if send(state, text, chat[0] if chat else None):
            if key and not key.startswith(("health:", "disk:")):
                state["sent"][key] = now
            if on_sent:
                on_sent()
    save_state(state)


def main():
    if not TOKEN or not CHAT_ID:
        log("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set; idling (no alerts will be sent)")
        while True:
            time.sleep(3600)
    if not database_url():
        log("DATABASE_URL not set; idling")
        while True:
            time.sleep(3600)

    if "--preview-digest" in sys.argv:  # 142: print, never send
        with connect() as conn:
            for uid, name, chat in digest_targets(conn):
                text = digest_for(conn, uid, datetime.now(timezone.utc))
                print(f"--- {name} → chat …{str(chat)[-3:]} ---\n{text or '(nothing today: no message)'}")
        return
    state = load_state()
    if "--send-summary" in sys.argv:
        with connect() as conn:
            send(state, summary_text(conn))
        save_state(state)
        return

    log(f"started: poll {POLL_SECONDS}s, disk alert <{DISK_ALERT_PCT}%, cap {MAX_PER_HOUR}/h, "
        f"summary {SUMMARY_HOUR:02d}:00 WIB, digests {DIGEST_HOUR:02d}:00 WIB, state {STATE_PATH}")
    while True:
        try:
            poll(state)
        except Exception as exc:  # keep the loop alive; never print a traceback with env in it
            log(f"poll error: {type(exc).__name__}: {exc}")
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
