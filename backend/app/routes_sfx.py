"""Sound effects library (217). Mounted by one line in main.py; rules in shared/sfx_library.py.

Ownership (P1.5): rows are `sfx_assets` with user_id NOT NULL; every query filters by the caller's id and another
user's sound answers 404 (main's guard SFX_PATH_RE also 404s /api/sfx/<uuid>… for rows that aren't the caller's).
Files: DATA_ROOT/sfx/<user_id>/<id>.wav (relative path in the DB), served only through /api/sfx/<id>/file
(MEDIA_PATH_RE). Freesound: key from env FREESOUND_API_KEY (Authorization header only, never a URL/log/response);
previews stream through /api/sfx/freesound/<id>/preview so the browser never talks to Freesound.

Routes (all /api, behind the auth middleware):
  GET    /api/sfx                          categories (assigned sound, used by) + my sounds + freesound on/off
  POST   /api/sfx                          multipart file [+ name, category] → checked, levelled, saved
  PATCH  /api/sfx/{id}                     {name?, category?} (category null = unassign; one sound per category)
  DELETE /api/sfx/{id}
  GET    /api/sfx/{id}/file                the levelled WAV
  GET    /api/sfx/freesound/search         ?category=laugh[&q=…] → top CC0 0.5–4 s results
  GET    /api/sfx/freesound/{fsid}/preview the HQ mp3 preview (proxied)
  POST   /api/sfx/freesound/{fsid}         {name?, category?} → download preview, re-check CC0 + length, save
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Optional

import requests
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, Response

from shared import sfx_library as lib

router = APIRouter(prefix="/api/sfx", tags=["sfx"])

FFMPEG_TIMEOUT = 15
FS_TIMEOUT = 10
CACHE_S = 600
_cache: dict = {}            # ("search", query) / ("sound", id) → (time, value)
_previews: dict = {}         # freesound id → (time, mp3 bytes), at most PREVIEW_CACHE entries
PREVIEW_CACHE = 40
_rate: dict = {}             # (user, kind) → [timestamps]
_lock = threading.Lock()
RATE = {"search": (20, 600), "preview": (80, 600), "save": (20, 600)}


def _core():
    from app import main as core  # lazy: main imports this module
    return core


def _user(request: Request) -> dict:
    return _core().current_user(request)


def _sound_id(raw: str) -> str:
    try:
        return str(uuid.UUID(raw))
    except (ValueError, TypeError):
        raise HTTPException(status_code=404, detail="Sound not found")


def _limit(user_id: str, kind: str) -> None:
    n, window = RATE[kind]
    now = time.time()
    with _lock:
        hits = [t for t in _rate.get((user_id, kind), []) if now - t < window]
        if len(hits) >= n:
            raise HTTPException(status_code=429, detail="Too many Freesound requests, try again in a few minutes")
        hits.append(now)
        _rate[(user_id, kind)] = hits


def _cached(key, fn, store=None, cap=500):
    store = _cache if store is None else store
    now = time.time()
    with _lock:
        hit = store.get(key)
        if hit and now - hit[0] < CACHE_S:
            return hit[1]
    value = fn()
    with _lock:
        if len(store) >= cap:
            store.pop(min(store, key=lambda k: store[k][0]))
        store[key] = (now, value)
    return value


def _preview_bytes(fsid: int, s: dict) -> bytes:
    return _cached(fsid, lambda: _fetch_preview(lib.preview_url(s)), _previews, PREVIEW_CACHE)


def _row(r) -> dict:
    return {"id": str(r[0]), "name": r[1], "duration": round(float(r[2] or 0), 2), "category": r[3],
            "category_label": lib.category_label(r[3]), "source": r[4], "source_url": r[5], "author": r[6],
            "license": r[7], "created_at": r[8].isoformat() if r[8] else None}


COLS = "id, name, duration, category, source, source_url, author, license, created_at"


# --------------------------------------------------------------------------- library

@router.get("")
def list_sfx(request: Request):
    user = _user(request)
    with _core().get_db() as conn:
        rows = conn.execute(f"SELECT {COLS} FROM sfx_assets WHERE user_id = %s ORDER BY created_at DESC",
                            (user["id"],)).fetchall()
    sounds = [_row(r) for r in rows]
    by_cat = {s["category"]: s for s in sounds if s["category"]}
    cats = []
    for key, c in lib.CATEGORIES.items():
        mine = by_cat.get(key)
        fb = lib.FALLBACK.get(key)
        cats.append({"key": key, "label": c["label"], "query": c["query"], "used_by": lib.used_by(key),
                     "assigned": {"id": mine["id"], "name": mine["name"]} if mine else None,
                     "default": None if mine else (f"Built-in {lib.category_label(fb).lower()}" if fb else "Built-in")})
    return {"categories": cats, "sounds": sounds, "freesound": bool(_fs_key()),
            "limits": {"max_bytes": lib.MAX_UPLOAD_BYTES, "max_seconds": lib.MAX_SECONDS, "min_seconds": lib.MIN_SECONDS,
                       "max_sounds": lib.MAX_SOUNDS}}


def _run(argv: list, what: str) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=FFMPEG_TIMEOUT)
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=400, detail=f"Couldn't {what} this file in time")


def _process(src: Path, dst: Path) -> float:
    """Sniff → probe (forced demuxer) → measure → trim + level to WAV. Returns the saved duration."""
    with open(src, "rb") as f:
        fmt = lib.sniff(f.read(16))
    if not fmt:
        raise HTTPException(status_code=400, detail="Not an mp3, wav or ogg file")
    p = _run(lib.probe_cmd(str(src), fmt), "read")
    try:
        data = json.loads(p.stdout or "{}")
    except ValueError:
        data = {}
    if p.returncode != 0 or not data:
        raise HTTPException(status_code=400, detail="Couldn't read this audio file")
    _dur, why = lib.check_probe(data)
    if why:
        raise HTTPException(status_code=400, detail=why)
    channels = next((s.get("channels") for s in data.get("streams") or [] if s.get("codec_type") == "audio"), 1)
    m = _run(lib.measure_cmd(str(src), fmt), "measure")
    mean, peak = lib.parse_volumedetect(m.stderr)
    if peak is None:
        raise HTTPException(status_code=400, detail="This sound is silent")
    c = _run(lib.convert_cmd(str(src), fmt, str(dst), lib.gain_db(mean, peak), channels), "convert")
    if c.returncode != 0 or not dst.is_file():
        raise HTTPException(status_code=400, detail="Couldn't convert this audio file")
    out = _run(lib.probe_cmd(str(dst), "wav"), "read")
    dur, why = lib.check_probe(json.loads(out.stdout or "{}") if out.returncode == 0 else {})
    if why:   # e.g. trimming the silence left too little
        raise HTTPException(status_code=400, detail=why if "short" not in why else "Too short once the silence is trimmed")
    return dur


def _save(user: dict, raw: bytes, *, name: str, category: Optional[str], source: str, source_url=None, author=None,
          license_=None, freesound_id=None) -> dict:
    if category is not None and category not in lib.CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    core = _core()
    with core.get_db() as conn:
        n = conn.execute("SELECT COUNT(*) FROM sfx_assets WHERE user_id = %s", (user["id"],)).fetchone()[0]
    if n >= lib.MAX_SOUNDS:
        raise HTTPException(status_code=409, detail=f"Your library is full ({lib.MAX_SOUNDS} sounds); delete one first")
    sid = str(uuid.uuid4())
    rel = Path("sfx") / str(user["id"]) / f"{sid}.wav"
    dst = core.DATA_ROOT / rel
    tmp = Path(tempfile.mkdtemp(prefix="sfx-"))
    try:
        src = tmp / "in"
        src.write_bytes(raw)
        work = tmp / "out.wav"
        dur = _process(src, work)
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(work), dst)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    try:
        with core.get_db() as conn:
            if category:
                conn.execute("UPDATE sfx_assets SET category = NULL WHERE user_id = %s AND category = %s", (user["id"], category))
            row = conn.execute(
                f"INSERT INTO sfx_assets (id, user_id, name, path, duration, category, source, source_url, author, license, "
                f"freesound_id) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING {COLS}",
                (sid, user["id"], name, str(rel), dur, category, source, source_url, author, license_, freesound_id),
            ).fetchone()
            conn.commit()
    except Exception:
        dst.unlink(missing_ok=True)
        raise
    return _row(row)


@router.post("")
async def upload_sfx(request: Request, file: UploadFile = File(...), name: str = Form(""), category: str = Form("")):
    user = _user(request)
    raw = await file.read(lib.MAX_UPLOAD_BYTES + 1)
    if not raw:
        raise HTTPException(status_code=400, detail="The file is empty")
    if len(raw) > lib.MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=400, detail="File too large (max 2 MB)")
    return await run_in_threadpool(_save, user, raw, name=lib.clean_name(name or file.filename),
                                   category=category or None, source="upload")


@router.patch("/{sound_id}")
async def update_sfx(sound_id: str, request: Request):
    user = _user(request)
    sid = _sound_id(sound_id)
    try:
        body = await request.json()
    except ValueError:
        body = None
    if not isinstance(body, dict) or not (set(body) & {"name", "category"}):
        raise HTTPException(status_code=400, detail="Send name and/or category")
    with _core().get_db() as conn:
        if not conn.execute("SELECT 1 FROM sfx_assets WHERE id = %s AND user_id = %s FOR UPDATE", (sid, user["id"])).fetchone():
            raise HTTPException(status_code=404, detail="Sound not found")
        if "name" in body:
            name = lib.clean_name(body.get("name"), "")
            if not name:
                raise HTTPException(status_code=400, detail="Give the sound a name")
            conn.execute("UPDATE sfx_assets SET name = %s WHERE id = %s AND user_id = %s", (name, sid, user["id"]))
        if "category" in body:
            cat = body.get("category") or None
            if cat is not None and cat not in lib.CATEGORIES:
                raise HTTPException(status_code=400, detail="Unknown category")
            if cat:   # one sound per category: the previous one is unassigned in the same transaction
                conn.execute("UPDATE sfx_assets SET category = NULL WHERE user_id = %s AND category = %s AND id <> %s",
                             (user["id"], cat, sid))
            conn.execute("UPDATE sfx_assets SET category = %s WHERE id = %s AND user_id = %s", (cat, sid, user["id"]))
        row = conn.execute(f"SELECT {COLS} FROM sfx_assets WHERE id = %s AND user_id = %s", (sid, user["id"])).fetchone()
        conn.commit()
    return _row(row)


@router.delete("/{sound_id}")
def delete_sfx(sound_id: str, request: Request):
    user = _user(request)
    sid = _sound_id(sound_id)
    with _core().get_db() as conn:
        row = conn.execute("DELETE FROM sfx_assets WHERE id = %s AND user_id = %s RETURNING path", (sid, user["id"])).fetchone()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Sound not found")
    try:
        (_core().DATA_ROOT / row[0]).unlink(missing_ok=True)
    except OSError:
        pass
    return {"status": "ok"}


@router.get("/{sound_id}/file")
def sfx_file(sound_id: str, request: Request):
    user = _user(request)
    sid = _sound_id(sound_id)
    with _core().get_db() as conn:
        row = conn.execute("SELECT path FROM sfx_assets WHERE id = %s AND user_id = %s", (sid, user["id"])).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Sound not found")
    path = _core().DATA_ROOT / row[0]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Sound file missing")
    return FileResponse(path, media_type="audio/wav")


# --------------------------------------------------------------------------- Freesound

def _fs_key() -> str:
    return (os.environ.get("FREESOUND_API_KEY") or "").strip()


def _fs_get(path: str, params: Optional[dict] = None) -> dict:
    key = _fs_key()
    if not key:
        raise HTTPException(status_code=503, detail="Freesound isn't set up yet (FREESOUND_API_KEY)")
    try:
        r = requests.get(f"{lib.FREESOUND_API}{path}", params=params, timeout=FS_TIMEOUT,
                         headers={"Authorization": f"Token {key}"})
    except requests.RequestException as exc:
        print(f"[sfx] Freesound {path}: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail="Freesound didn't answer, try again")
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail="Sound not found on Freesound")
    if r.status_code in (401, 403):
        print(f"[sfx] Freesound refused the API key ({r.status_code})")
        raise HTTPException(status_code=503, detail="Freesound refused the API key")
    if r.status_code == 429:
        raise HTTPException(status_code=429, detail="Freesound's limit is reached, try again later")
    if r.status_code != 200:
        print(f"[sfx] Freesound {path}: HTTP {r.status_code}")
        raise HTTPException(status_code=502, detail="Freesound had a problem, try again")
    try:
        return r.json()
    except ValueError:
        raise HTTPException(status_code=502, detail="Freesound sent an unreadable answer")


def _fs_sound(fsid: int) -> dict:
    return _cached(("sound", fsid), lambda: _fs_get(f"/sounds/{fsid}/", {"fields": lib.FS_FIELDS}))


@router.get("/freesound/search")
def freesound_search(request: Request, category: str = "", q: str = ""):
    user = _user(request)
    if category and category not in lib.CATEGORIES:
        raise HTTPException(status_code=400, detail="Unknown category")
    query = lib.clean_name(q or (lib.CATEGORIES[category]["query"] if category else ""), "")
    if not query:
        raise HTTPException(status_code=400, detail="Type what to look for")
    params = lib.search_params(query)
    key = ("search", params["query"].lower())
    with _lock:
        fresh = key in _cache and time.time() - _cache[key][0] < CACHE_S
    if not fresh:
        _limit(user["id"], "search")
    data = _cached(key, lambda: _fs_get("/search/text/", params))
    results = lib.rank((data or {}).get("results") or [])
    with _lock:
        for r in (data or {}).get("results") or []:
            if isinstance(r, dict) and str(r.get("id", "")).isdigit():
                _cache[("sound", int(r["id"]))] = (time.time(), r)
    return {"query": params["query"], "category": category or None, "results": results}


def _fs_eligible(fsid: int) -> dict:
    s = _fs_sound(fsid)
    if not lib.eligible(s):
        raise HTTPException(status_code=400, detail="Only CC0 sounds of 0.5–4 s can be used")
    return s


def _fetch_preview(url: str) -> bytes:
    try:
        r = requests.get(url, timeout=FS_TIMEOUT, stream=True)
        r.raise_for_status()
        buf = b""
        for chunk in r.iter_content(65536):
            buf += chunk
            if len(buf) > lib.PREVIEW_MAX_BYTES:
                raise HTTPException(status_code=502, detail="Freesound preview is too large")
        return buf
    except requests.RequestException as exc:
        print(f"[sfx] preview fetch: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail="Couldn't load the preview, try again")


@router.get("/freesound/{fsid}/preview")
def freesound_preview(fsid: int, request: Request):
    user = _user(request)
    _limit(user["id"], "preview")
    s = _fs_eligible(fsid)
    body = _preview_bytes(fsid, s)
    return Response(body, media_type="audio/mpeg", headers={"Cache-Control": "private, max-age=600"})


@router.post("/freesound/{fsid}")
async def freesound_save(fsid: int, request: Request):
    user = _user(request)
    try:
        body = await request.json()
    except ValueError:
        body = {}
    body = body if isinstance(body, dict) else {}
    _limit(user["id"], "save")
    return await run_in_threadpool(_freesound_save, user, fsid, body)


def _freesound_save(user: dict, fsid: int, body: dict) -> dict:
    s = _fs_eligible(fsid)
    raw = _preview_bytes(fsid, s)
    c = lib.card(s)
    return _save(user, raw, name=lib.clean_name(body.get("name") or c["name"]), category=body.get("category") or None,
                 source="freesound", source_url=c["url"] or f"https://freesound.org/s/{fsid}/", author=c["author"],
                 license_=lib.FREESOUND_CC0, freesound_id=fsid)
