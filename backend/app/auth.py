"""
P1.5 accounts: users, DB sessions, login rate limit, per-user media tokens.

Principals (resolved once per request by main.py's auth middleware, stored on
request.state.user = {"id", "username", "role"}):
  1. session cookie `clipflow_session` (browser; HttpOnly, SameSite=Lax),
  2. a per-user API token `cf_…` (X-ClipFlow-Key or Authorization: Bearer;
     the shared CLIPFLOW_API_KEY admin key was removed in 127),
  3. ?mt= media token on MEDIA_PATH_RE GETs (signed per user, read-only).

Only hashes are stored: argon2 for passwords, sha256 for session tokens.
A disabled user's sessions stop working immediately (every lookup joins
users.active); a password change/reset deletes the user's other sessions.
"""

import hashlib
import hmac
import os
import secrets
import time
import uuid

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

# 140: cookies are scoped to the host, not the port, so prod (:80) and staging (:8080) on one box would
# overwrite each other's session. CLIPFLOW_ENV=staging (env only) gives staging its own cookie name.
CLIPFLOW_ENV = (os.getenv("CLIPFLOW_ENV") or "production").strip().lower()
SESSION_COOKIE = "clipflow_session" if CLIPFLOW_ENV == "production" else f"clipflow_{CLIPFLOW_ENV}_session"
SESSION_TTL_DAYS = 30
SESSION_TOUCH_SECONDS = 300       # last_seen_at/expiry slide at most every 5 min

LOGIN_WINDOW_MINUTES = 15
# 139: the tight limit is per username + IP, so a stranger's 5 bad guesses no longer lock YOU out
# (was per username alone: a lockout DoS); a looser per-username limit still stops distributed guessing.
LOGIN_MAX_FAILS_USER_IP = 5       # per username + client IP per window
LOGIN_MAX_FAILS_USER = 50         # per username from any IP per window
LOGIN_MAX_FAILS_IP = 20           # per client IP (any usernames) per window

MEDIA_TOKEN_WINDOW = 12 * 3600
PASSWORD_MIN_LEN = 12
USERNAME_RE_TEXT = r"^[a-z0-9][a-z0-9._-]{1,31}$"
ROLES = ("admin", "member")

_hasher = PasswordHasher()

SCHEMA = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('admin','member')),
        active BOOLEAN NOT NULL DEFAULT TRUE,
        bootstrap BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        password_changed_at TIMESTAMPTZ
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_sessions (
        token_hash TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        expires_at TIMESTAMPTZ NOT NULL,
        ip TEXT,
        user_agent TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions (user_id)",
    # Part 5: set by an admin create/reset (temp password); the session can only
    # change its password until it is cleared by POST /api/auth/password.
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE",
    """
    CREATE TABLE IF NOT EXISTS login_failures (
        id BIGSERIAL PRIMARY KEY,
        username TEXT NOT NULL,
        ip TEXT,
        at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_login_failures_at ON login_failures (at)",
    # Part 4: per-user API tokens for scripts. Only the sha256 is stored; `prefix`
    # (first chars) lets the UI tell tokens apart. Deleting the row revokes it.
    """
    CREATE TABLE IF NOT EXISTS api_tokens (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name TEXT NOT NULL,
        token_hash TEXT NOT NULL UNIQUE,
        prefix TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_used_at TIMESTAMPTZ
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_api_tokens_user ON api_tokens (user_id)",
    # Server-side secrets that must never be served (app_settings is): media-token HMAC key.
    """
    CREATE TABLE IF NOT EXISTS server_secrets (
        name TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
]


# ---------- passwords / tokens ----------

def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Spent on unknown usernames so a miss takes as long as a wrong password.
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def password_problem(password: str) -> str | None:
    if not isinstance(password, str) or len(password) < PASSWORD_MIN_LEN:
        return f"Password must be at least {PASSWORD_MIN_LEN} characters"
    if len(password) > 256:
        return "Password is too long"
    return None


def public_user(row) -> dict:
    """(id, username, role, active, created_at) → API shape."""
    uid, username, role, active, created_at = row[:5]
    return {
        "id": uid,
        "username": username,
        "role": role,
        "active": bool(active),
        "created_at": created_at.isoformat() if created_at else None,
    }


# ---------- bootstrap ----------

def ensure_bootstrap_admin(conn) -> str | None:
    """
    First run (no users at all): create the admin from env
    CLIPFLOW_ADMIN_USER / CLIPFLOW_ADMIN_PASSWORD. The env is read only
    while the users table is empty; afterwards the DB is the truth.
    Returns the bootstrap admin's id (None when there is none yet).
    """
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE bootstrap ORDER BY created_at LIMIT 1")
        row = cur.fetchone()
        if row:
            return row[0]
        cur.execute("SELECT COUNT(*) FROM users")
        if cur.fetchone()[0]:
            cur.execute(
                "SELECT id FROM users WHERE role='admin' ORDER BY created_at LIMIT 1"
            )
            row = cur.fetchone()
            return row[0] if row else None

        username = (os.getenv("CLIPFLOW_ADMIN_USER") or "").strip().lower()
        password = os.getenv("CLIPFLOW_ADMIN_PASSWORD") or ""
        if not username or password_problem(password):
            print(
                "[auth] no users yet and CLIPFLOW_ADMIN_USER / CLIPFLOW_ADMIN_PASSWORD "
                f"missing or too short (min {PASSWORD_MIN_LEN}): nobody can log in"
            )
            return None
        uid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO users (id, username, password_hash, role, active, bootstrap,
                               password_changed_at)
            VALUES (%s, %s, %s, 'admin', TRUE, TRUE, NOW())
            """,
            (uid, username, hash_password(password)),
        )
    conn.commit()
    print(f"[auth] bootstrap admin '{username}' created from env")
    return uid


# ---------- sessions ----------

def create_session(conn, user_id: str, ip: str | None, user_agent: str | None) -> str:
    token = secrets.token_urlsafe(32)
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_sessions (token_hash, user_id, expires_at, ip, user_agent)
            VALUES (%s, %s, NOW() + make_interval(days => %s), %s, %s)
            """,
            (token_hash(token), user_id, SESSION_TTL_DAYS, ip, (user_agent or "")[:300]),
        )
        cur.execute("DELETE FROM user_sessions WHERE expires_at < NOW()")
    return token


def session_user(conn, token: str) -> dict | None:
    if not token:
        return None
    th = token_hash(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.role,
                   EXTRACT(EPOCH FROM NOW() - s.last_seen_at), u.must_change_password
            FROM user_sessions s JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = %s AND s.expires_at > NOW() AND u.active
            """,
            (th,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if row[3] is not None and float(row[3]) > SESSION_TOUCH_SECONDS:
            cur.execute(
                """
                UPDATE user_sessions
                SET last_seen_at = NOW(),
                    expires_at = NOW() + make_interval(days => %s)
                WHERE token_hash = %s
                """,
                (SESSION_TTL_DAYS, th),
            )
            conn.commit()
    return {"id": row[0], "username": row[1], "role": row[2], "must_change_password": bool(row[4])}


def delete_session(conn, token: str) -> None:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM user_sessions WHERE token_hash = %s", (token_hash(token),))


def delete_user_sessions(conn, user_id: str, keep_token: str | None = None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "DELETE FROM user_sessions WHERE user_id = %s AND token_hash <> %s",
            (user_id, token_hash(keep_token) if keep_token else ""),
        )


# ---------- login rate limit ----------

def login_blocked(conn, username: str, ip: str | None) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT
              COUNT(*) FILTER (WHERE username = %s AND ip IS NOT DISTINCT FROM %s),
              COUNT(*) FILTER (WHERE username = %s),
              COUNT(*) FILTER (WHERE ip = %s)
            FROM login_failures
            WHERE at > NOW() - make_interval(mins => %s)
            """,
            (username, ip, username, ip or "", LOGIN_WINDOW_MINUTES),
        )
        by_user_ip, by_user, by_ip = cur.fetchone()
    return (by_user_ip >= LOGIN_MAX_FAILS_USER_IP or by_user >= LOGIN_MAX_FAILS_USER
            or by_ip >= LOGIN_MAX_FAILS_IP)


def record_login_failure(conn, username: str, ip: str | None) -> None:
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO login_failures (username, ip) VALUES (%s, %s)",
            (username[:64], ip),
        )
        cur.execute("DELETE FROM login_failures WHERE at < NOW() - INTERVAL '1 day'")


def clear_login_failures(conn, username: str, ip: str | None = None) -> None:
    """After a good login: this user's failures from this IP (all IPs when ip is None, e.g. admin reset)."""
    with conn.cursor() as cur:
        if ip is None:
            cur.execute("DELETE FROM login_failures WHERE username = %s", (username,))
        else:
            cur.execute("DELETE FROM login_failures WHERE username = %s AND ip IS NOT DISTINCT FROM %s", (username, ip))


def authenticate(conn, username: str, password: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, role, password_hash, active, must_change_password"
            " FROM users WHERE username = %s",
            (username,),
        )
        row = cur.fetchone()
    if not row:
        verify_password(_DUMMY_HASH, password)
        return None
    if not verify_password(row[3], password) or not row[4]:
        return None
    if _hasher.check_needs_rehash(row[3]):
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET password_hash=%s WHERE id=%s",
                (hash_password(password), row[0]),
            )
    return {"id": row[0], "username": row[1], "role": row[2], "must_change_password": bool(row[5])}


# ---------- media tokens (per user) ----------

_secret_cache: dict[str, bytes] = {}


def server_secret(conn, name: str) -> bytes:
    if name in _secret_cache:
        return _secret_cache[name]
    with conn.cursor() as cur:
        cur.execute(
            "INSERT INTO server_secrets (name, value) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
            (name, secrets.token_hex(32)),
        )
        cur.execute("SELECT value FROM server_secrets WHERE name = %s", (name,))
        value = cur.fetchone()[0].encode()
    conn.commit()
    _secret_cache[name] = value
    return value


def _media_sig(secret: bytes, user_id: str, exp: int) -> str:
    return hmac.new(secret, f"media:{user_id}:{exp}".encode(), hashlib.sha256).hexdigest()


def issue_media_token(conn, user_id: str) -> dict:
    """Stable per 12 h bucket (media URLs don't change under a playing video), valid 12-24 h."""
    exp = (int(time.time()) // MEDIA_TOKEN_WINDOW + 2) * MEDIA_TOKEN_WINDOW
    sig = _media_sig(server_secret(conn, "media_token"), user_id, exp)
    return {"token": f"{exp}.{user_id}.{sig}", "expires_at": exp}


def media_token_user_id(conn, token: str) -> str | None:
    parts = token.split(".")
    if len(parts) != 3:
        return None
    exp_raw, user_id, sig = parts
    try:
        exp = int(exp_raw)
    except ValueError:
        return None
    if exp <= time.time():
        return None
    expected = _media_sig(server_secret(conn, "media_token"), user_id, exp)
    return user_id if secrets.compare_digest(sig, expected) else None


def active_user(conn, user_id: str) -> dict | None:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, username, role FROM users WHERE id = %s AND active", (user_id,)
        )
        row = cur.fetchone()
    return {"id": row[0], "username": row[1], "role": row[2]} if row else None


# ---------- API tokens (part 4) ----------

API_TOKEN_PREFIX = "cf_"
API_TOKEN_MAX_PER_USER = 20
API_TOKEN_TOUCH_SECONDS = 300


def create_api_token(conn, user_id: str, name: str) -> dict:
    """Returns the plaintext token ONCE; only its sha256 is stored."""
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM api_tokens WHERE user_id = %s", (user_id,))
        if cur.fetchone()[0] >= API_TOKEN_MAX_PER_USER:
            raise ValueError(f"At most {API_TOKEN_MAX_PER_USER} tokens per user; revoke one first")
        token = API_TOKEN_PREFIX + secrets.token_urlsafe(32)
        tid = str(uuid.uuid4())
        cur.execute(
            """
            INSERT INTO api_tokens (id, user_id, name, token_hash, prefix)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING created_at
            """,
            (tid, user_id, name, token_hash(token), token[:10]),
        )
        created = cur.fetchone()[0]
    return {"id": tid, "name": name, "prefix": token[:10], "token": token,
            "created_at": created.isoformat(), "last_used_at": None}


def list_api_tokens(conn, user_id: str) -> list:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, prefix, created_at, last_used_at FROM api_tokens
            WHERE user_id = %s ORDER BY created_at DESC
            """,
            (user_id,),
        )
        return [
            {"id": r[0], "name": r[1], "prefix": r[2],
             "created_at": r[3].isoformat() if r[3] else None,
             "last_used_at": r[4].isoformat() if r[4] else None}
            for r in cur.fetchall()
        ]


def delete_api_token(conn, user_id: str, token_id: str) -> bool:
    with conn.cursor() as cur:
        cur.execute("DELETE FROM api_tokens WHERE id = %s AND user_id = %s", (token_id, user_id))
        return cur.rowcount > 0


def api_token_user(conn, token: str) -> dict | None:
    if not token.startswith(API_TOKEN_PREFIX):
        return None
    th = token_hash(token)
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.role,
                   EXTRACT(EPOCH FROM NOW() - COALESCE(t.last_used_at, 'epoch'))
            FROM api_tokens t JOIN users u ON u.id = t.user_id
            WHERE t.token_hash = %s AND u.active
            """,
            (th,),
        )
        row = cur.fetchone()
        if not row:
            return None
        if float(row[3]) > API_TOKEN_TOUCH_SECONDS:
            cur.execute("UPDATE api_tokens SET last_used_at = NOW() WHERE token_hash = %s", (th,))
            conn.commit()
    return {"id": row[0], "username": row[1], "role": row[2]}


# ---------- user admin (part 5) ----------

import re as _re

USERNAME_RE = _re.compile(USERNAME_RE_TEXT)


def username_problem(username: str) -> str | None:
    if not USERNAME_RE.match(username or ""):
        return "Username: 2-32 characters, lower-case letters, digits, '.', '_' or '-', starting with a letter or digit"
    return None


def list_users(conn) -> list:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.role, u.active, u.created_at, u.must_change_password,
                   (SELECT MAX(last_seen_at) FROM user_sessions s WHERE s.user_id = u.id),
                   (SELECT COUNT(*) FROM jobs j WHERE j.user_id = u.id),
                   (SELECT COUNT(*) FROM api_tokens t WHERE t.user_id = u.id)
            FROM users u ORDER BY u.created_at
            """
        )
        return [
            {**public_user(r), "must_change_password": bool(r[5]),
             "last_seen_at": r[6].isoformat() if r[6] else None,
             "jobs": r[7], "tokens": r[8]}
            for r in cur.fetchall()
        ]


def locked_user_and_admins(cur, user_id: str):
    """Lock every active admin row (+ the target) so two concurrent changes can't
    both remove 'the other' last admin. Returns (target row, active admin ids)."""
    cur.execute("SELECT id FROM users WHERE role = 'admin' AND active ORDER BY id FOR UPDATE")
    admins = [r[0] for r in cur.fetchall()]
    cur.execute(
        "SELECT id, username, role, active FROM users WHERE id = %s FOR UPDATE", (user_id,)
    )
    return cur.fetchone(), admins


def end_user_access(cur, user_id: str, tokens: bool) -> None:
    cur.execute("DELETE FROM user_sessions WHERE user_id = %s", (user_id,))
    if tokens:
        cur.execute("DELETE FROM api_tokens WHERE user_id = %s", (user_id,))
