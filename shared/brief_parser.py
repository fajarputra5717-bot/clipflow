"""Campaign brief text → rules dict (the docs/campaigns/<slug>.rules.json schema) + `unsure` list.

Patterns first (primary, deterministic): the Indonesian MotionKlip/Whop-style templates have stable
section labels, so regex is exact and repeatable. Anything the text doesn't settle goes into
`unsure` as {"field", "why"} instead of being guessed; a human (or the admin) answers those.

AI fallback (optional, `ai=`): only when the patterns leave a gap (no payout rate, no platforms,
no hashtags, no content rules, or unrecognised rule lines) — e.g. an English CPM-style brief. The
AI fills ONLY fields the patterns didn't; every AI-filled field is listed in `ai_derived` and in
`unsure` (source "ai") so it is confirmed in the Campaign screen. `ai` is any callable
(prompt, schema) -> dict; `router_ai()` wraps shared.ai.router (utility model, task "brief").

  rules = parse_brief(text, today=date(2026, 10, 2))                  # patterns only
  rules = parse_brief(text, today=date(2026, 10, 2), ai=router_ai())  # + fallback
  shared.payouts.model_from_rules(rules)   # FixedThreshold / PerBlock / Unknown
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Callable, Optional

BRIEF_START, BRIEF_END = "--- BRIEF START ---", "--- BRIEF END ---"

PLATFORM_ALIASES = {
    "tiktok": "tiktok", "tik tok": "tiktok", "youtube": "youtube", "yt": "youtube",
    "youtube shorts": "youtube", "instagram": "instagram", "ig": "instagram", "reels": "instagram",
    "facebook": "facebook", "fb": "facebook", "x": "x", "twitter": "x", "threads": "threads",
}
MONTHS_ID = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
             "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
             "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7, "august": 8,
             "october": 10, "december": 12, "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
             "aug": 8, "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12, "okt": 10, "des": 12, "agu": 8}

# Content rules: first matching pattern wins (order matters: SARA before generic "tidak pantas").
CONTENT_RULES = [
    ("no_fake_views", r"view\s*botting|paid views|ads boosting|manipulasi views",
     "No botted, paid or boosted views"),
    ("no_reupload_without_editing", r"reupload", "No reupload without edits"),
    ("no_negative_narrative_about_others", r"narasi negatif",
     "No negative narratives about other parties or other brands"),
    ("no_misleading_context", r"memutar konteks|menyesatkan", "No misleading context"),
    ("no_sara_or_insults", r"\bSARA\b|menghina",
     "No SARA (ethnicity, religion, race, inter-group) or insults"),
    ("no_copying_other_clippers", r"konten milik clipper lain|duplikasi", "No copying other clippers"),
    ("must_follow_brief", r"sesuai dengan brief",
     "Content must follow the brief and stay in the campaign's context"),
    ("no_sensitive_issues", r"isu sensitif", "Don't show or steer the brand toward sensitive issues"),
    ("no_demeaning_third_party_media", r"foto atau video pihak lain",
     "No third-party photos/videos used to demean or attack"),
    ("no_inappropriate_material", r"materi .*tidak pantas", "No inappropriate material"),
    ("stay_public", r"tetap tayang|menghapus|meng-?hide",
     "Submitted content must stay public (no delete, hide or restrict)"),
]
# Rule lines that are captured by other fields (watermark, hashtags, period), not content rules.
COVERED_ELSEWHERE = (r"watermark|hashtag|eligible untuk payout|diupload mulai|periode|Minggu"
                     r"|target\s+[\d.,]+\s*Views|sesuai minggu")  # payout/period/week rules


def _num(s: str) -> int:
    """'12.000' / '12,000' / '500.000' → int (Indonesian thousands separators)."""
    return int(re.sub(r"[.,\s]", "", s))


def _line(text: str, label: str) -> Optional[str]:
    m = re.search(rf"^\s*(?:{label})\s*:\s*(.+?)\s*$", text, re.I | re.M)
    return m.group(1) if m else None


def _section(text: str, head: str, until: str) -> str:
    m = re.search(rf"^\s*{head}.*?$(.*?)(?=^\s*(?:{until})|\Z)", text, re.I | re.M | re.S)
    return m.group(1) if m else ""


def _bullets(block: str) -> list[str]:
    return [m.group(1).strip() for m in re.finditer(r"^\s*[*\-•]\s+(.+)$", block, re.M)]


def _platforms(s: str) -> list[str]:
    out = []
    for part in re.split(r"\s*(?:-|,|/|\bdan\b|&)\s*", s.lower()):
        p = PLATFORM_ALIASES.get(part.strip())
        if p and p not in out:
            out.append(p)
    return out


def _date(day: str, month: str, year: int) -> Optional[date]:
    mo = MONTHS_ID.get(month.lower())
    return date(year, mo, int(day)) if mo else None


def extract_brief(md_text: str) -> Optional[str]:
    """Verbatim brief between the markers of a docs/campaigns/<slug>.md, or None if pending."""
    if BRIEF_START not in md_text:
        return None
    return md_text.split(BRIEF_START, 1)[1].split(BRIEF_END, 1)[0].strip()


def parse_brief(text: Optional[str], *, today: Optional[date] = None, slug: Optional[str] = None,
                ai: Optional[Callable[[str, dict], dict]] = None) -> dict:
    """Rules dict in the docs/campaigns schema, plus `unsure: [{field, why}]`.

    today  anchors years the brief leaves out (briefs say '30 September', '1 Oktober').
    ai     optional fallback for gaps the patterns leave (see module docstring).
    """
    rules = _parse_patterns(text, today=today or date.today(), slug=slug)
    if ai and text and text.strip():
        reasons = ai_gaps(rules)
        if reasons:
            try:
                rules["_text"] = text
                merge_ai(rules, ai(build_ai_prompt(text, rules, reasons), AI_SCHEMA))
            except Exception as e:  # AI is a helper: a failure must never lose the pattern result
                rules["unsure"].append({"field": "ai", "why": f"AI fallback failed: {e}"[:200]})
            rules["ai_reasons"] = reasons
            rules.pop("_text", None)
    return rules


def _currency_in(text: str) -> Optional[str]:
    """Currency from symbols in the brief text (a fact in the text, not an AI guess)."""
    if re.search(r"\bRp\.?\s?\d", text):
        return "IDR"
    if re.search(r"(?:US)?\$\s?\d", text):
        return "USD"
    if re.search(r"€\s?\d", text):
        return "EUR"
    return None


def _parse_patterns(text: Optional[str], *, today: date, slug: Optional[str]) -> dict:
    unsure: list[dict] = []
    ask = lambda field, why: None if {"field": field, "why": why} in unsure else unsure.append({"field": field, "why": why})
    rules: dict = {"campaign": slug, "source": "brief_parser"}
    if not text or not text.strip():
        rules.update(brief_pending=True, payout={}, platforms=[], unsure=[
            {"field": "*", "why": "brief text missing (pending): nothing can be extracted"}])
        return rules

    first = next((l.strip() for l in text.splitlines() if l.strip()), "")
    rules["name"] = first
    if cat := _line(text, "Kategori|Category"):
        rules["category"] = cat.strip().lower()

    # Platforms: the 'Platform:' line, else the 'boleh upload di platform …' sentence
    plat = _line(text, "Platform")
    if not plat:
        m = re.search(r"upload di platform\s+(.+?)\.?\s*$", text, re.I | re.M)
        plat = m.group(1) if m else None
    rules["platforms"] = _platforms(plat) if plat else []
    if not rules["platforms"]:
        ask("platforms", "no 'Platform:' line found")

    # ---- payout
    payout: dict = {"currency": "IDR"}
    tarif = re.search(r"Rp\s*([\d.,]+)\s*per\s*([\d.,]+)\s*views", text, re.I)
    cpm = re.search(r"\bCPM\s*([\d.,]+)", text, re.I)
    if cpm:
        payout["cpm_stated"] = _num(cpm.group(1))
    min_v = re.search(r"Minimal Views[^:\n]*:\s*([\d.,]+)", text, re.I) or \
        re.search(r"target\s+([\d.,]+)\s*Views", text, re.I)
    max_v = re.search(r"Maksimal Claim\s*:\s*([\d.,]+)\s*views", text, re.I)
    fixed = re.search(r"fixed payout|tidak akan menambah", text, re.I)
    if tarif:
        amount, views = _num(tarif.group(1)), _num(tarif.group(2))
        payout["stated_as"] = f"Rp {tarif.group(1)} per {tarif.group(2)} views"
        if fixed:
            payout.update(model="fixed_threshold", per_video=amount,
                          min_views=_num(min_v.group(1)) if min_v else views,
                          above_threshold=f"flat: views beyond {views:,} pay nothing extra")
            if payout.get("cpm_stated"):
                payout["cpm_note"] = "brief states a CPM but the payout is fixed; informational only"
        else:
            payout.update(model="per_block", per_block=amount, block_views=views,
                          min_views=_num(min_v.group(1)) if min_v else views)
            if max_v:
                payout["max_paid_views_per_video"] = _num(max_v.group(1))
            else:
                ask("payout.max_paid_views_per_video", "no 'Maksimal Claim' cap stated")
            ask("payout.rounding", "brief doesn't say partial blocks pay nothing; assumed FULL blocks (floor)")
    else:
        payout["model"] = "unknown"
        ask("payout", "no 'Rp X per Y views' rate found")
    if re.search(r"tidak dapat di ?claim ulang|claim sekali", text, re.I):
        payout["claims_per_video"] = 1
    if re.search(r"Payout mengikuti jumlah views yang disubmit", text, re.I):
        payout["views_counted"] = "at submit time"
    if pm := _line(text, "Metode Pembayaran|Payment"):
        payout["payment_methods"] = [{"gopay": "GoPay", "dana": "DANA", "ovo": "OVO"}.get(x.lower(), x)
                                     for x in re.split(r"\s*(?:&|,|dan)\s*", pm) if x]
    if form := re.search(r"https://forms\.gle/\S+?(?=[)\s]|$)", text):
        payout["claim_form"] = form.group(0)
    if tag := re.search(r'Tag Discord\s+"([^"]+)"', text, re.I):
        payout["claim_requires"] = f"Discord server tag '{tag.group(1)}' (manual)"
        rules["manual_only"] = [{"id": "discord_tag", "app_work": False,
                                 "text": f'Discord server tag "{tag.group(1)}" required to claim'}]
    rules["payout"] = payout

    # ---- limits, budget, weeks
    lim = re.search(r"MAKSIMAL\s+(\d+)\s+VIDEO[^\n]*PER\s+BULAN", text, re.I)
    if lim:
        rules["limits"] = {"max_eligible_videos_per_platform_account_per_month": int(lim.group(1))}
        ask("limits.account_unit", "brief says '1 akun': per platform account or per creator? "
                                   "(IME admin answered: each platform account)")
    budget = re.search(r"Total reward dalam 1 Bulan\s*:\s*Rp\s*([\d.,]+)", text, re.I)
    refills = re.search(r"(\d+)\s*x\s*Refill", text, re.I)
    if budget:
        rules["budget"] = {"currency": "IDR", "total_per_month": _num(budget.group(1))}
        if refills:
            n = int(refills.group(1))
            rules["budget"].update(refills=n, per_refill=_num(budget.group(1)) // n)
            ask("budget.carry_over", "does unused weekly budget carry over? (not stated)")
    elif re.search(r"hingga budget habis", text, re.I):
        ask("budget.total", "'hingga budget habis' without a total")

    weeks = []
    seen = set()
    for m in re.finditer(r"Minggu\s*(\d+)\s*\S*\s*(\d{1,2})\s+([A-Za-z]+)\s*s/?d\s*(\d{1,2})\s+([A-Za-z]+)", text, re.I):
        if m.group(1) in seen:
            continue  # briefs repeat the schedule block
        seen.add(m.group(1))
        start, end = _date(m.group(2), m.group(3), today.year), _date(m.group(4), m.group(5), today.year)
        if start and end:
            weeks.append({"id": f"W{m.group(1)}", "start": start.isoformat(), "end": end.isoformat()})
    if weeks:
        rules["weeks"] = {"timezone": "Asia/Jakarta (WIB)", "list": weeks}
        if re.search(r"claim sesuai minggu|Hanya bisa claim di Minggu", text, re.I):
            rules["weeks"]["rule"] = "a video counts only in the week it was uploaded"
        if t := re.search(r"pukul\s+(\d{1,2}[:.]\d{2})\s*WIB", text, re.I):
            rules["weeks"]["refill_time"] = t.group(1).replace(".", ":")
        ask("weeks.year", f"brief gives day + month only; year read as {today.year}")
        last = date.fromisoformat(weeks[-1]["end"])
        ask("weeks.outside", f"uploads after {last:%d %b} (rest of the month): eligible? (not stated)")

    period = {}
    if m := re.search(r"diupload mulai tanggal\s+(\d{1,2})\s+([A-Za-z]+)(?:\s+(\d{4}))?", text, re.I):
        year = int(m.group(3)) if m.group(3) else today.year
        if d := _date(m.group(1), m.group(2), year):
            period["start"] = d.isoformat()
            if not m.group(3):
                ask("period.start", f"no year in the brief; read as {year}")
    if re.search(r"hingga budget habis", text, re.I):
        period.update(end=None, until="budget runs out")
    # English deadline: "Deadline: Oct 31, 2026" / "Submit views by Oct 31, 2026" / "by 31 October 2026"
    dl = re.search(r"(?:deadline|submit[^\n]{0,40}?\bby|ends?|until)\s*[:\-]?\s*"
                   r"(?:([A-Za-z]{3,9})\.?\s+(\d{1,2})|(\d{1,2})\s+([A-Za-z]{3,9}))(?:,?\s+(\d{4}))?", text, re.I)
    if dl and "end" not in period:
        month, day = (dl.group(1), dl.group(2)) if dl.group(1) else (dl.group(4), dl.group(3))
        year = int(dl.group(5)) if dl.group(5) else today.year
        if d := _date(day, month, year):
            period["end"] = d.isoformat()
            if not dl.group(5):
                ask("period.end", f"no year in the deadline; read as {year}")
    if m := re.search(r"periode yang tertera di\s+(\S+?)\.?(?:\s|$)", text, re.I):
        ask("period", f"period is announced elsewhere ({m.group(1)}), not in the brief")
    if period:
        rules["period"] = period

    # ---- sources, hashtags, socials, watermark
    sources = []
    bahan = _section(text, r"\*?\s*Bahan Clip", r"Highlight|Rules|Content|Hashtag")
    for m in re.finditer(r"youtube\.com/(@[\w.\-]+)", bahan, re.I):
        sources.append({"platform": "youtube", "channel": m.group(1), "job_source": True})
    rules["sources"] = sources
    if not sources:
        ask("sources", "no 'Bahan Clip' channel: where do clips come from?")

    tags_line = next((l for l in text.splitlines() if l.count("#") >= 2 and not re.search(r"harus|Wajib", l)), None) \
        or next((l for l in text.splitlines() if l.count("#") >= 2), "")
    tags = re.findall(r"#\w+", tags_line)
    if tags:
        rules["hashtags"] = {"required_in_order": tags}
        if not re.search(r"dengan urutan|in this order", text, re.I):
            ask("hashtags.order", "brief doesn't say the order matters")
    else:
        ask("hashtags", "no hashtag line found")
    mentions = sorted(set(re.findall(r"(?<![\w/])@[A-Za-z0-9_.]+", tags_line)))
    if mentions:
        rules["mentions"] = mentions

    socials = {}
    soc = _section(text, r"Social Media", r"Hashtag|Content")
    for name, url in re.findall(r"^\s*(Instagram|Tiktok|TikTok|Youtube|YouTube|X|Threads)\s*:\s*(\S+)", soc, re.M):
        socials[name.lower()] = url
    if socials:
        key = "brand_socials" if rules.get("category") == "brand" else "creator_socials"
        if key == "brand_socials":
            rules.setdefault("content", {})["brand_socials"] = socials
        else:
            rules["creator_socials"] = socials

    if re.search(r"Wajib menggunakan Watermark", text, re.I):
        wm = {"required": True}
        if m := re.search(r"\[Template Watermark\]\((\S+?)\)", text):
            wm["template_source"] = m.group(1)
        if m := re.search(r"\[Panduan Penempatan Watermark\]\((\S+?)\)", text):
            wm["placement_guide"] = {"source": m.group(1).split("?")[0]}
        rules["watermark"] = wm
        ask("watermark.asset_id", "match the template file to a watermark library asset")
        ask("watermark.preset", "size/position not in the brief (measure the placement guide)")
    elif re.search(r"tanpa watermark|dilarang .*watermark|\bno (?:personal |own |extra )?watermarks?\b", text, re.I):
        rules["watermark"] = {"required": False, "forbidden": True}

    # ---- content brief + rules
    content = rules.get("content", {})
    if m := re.search(r"Contoh Judul[^\n]*\n(.*?)(?:\n\s*\n|\Z)", text, re.I | re.S):
        titles = re.findall(r'"([^"]+)"', m.group(1))
        if titles:
            content.update(title_examples=titles, title_language="id")
    if re.search(r"tidak harus selalu menyebut", text, re.I):
        content["title_must_name_brand"] = False
    if content:
        rules["content"] = content

    lines = [l for l in _bullets(text) if re.search(r"Dilarang|Tidak diperbolehkan|tidak boleh|Wajib|harus", l, re.I)]
    found, ids = [], set()
    for l in lines:
        hit = next((r for r in CONTENT_RULES if re.search(r[1], l, re.I)), None)
        if hit and hit[0] not in ids:
            ids.add(hit[0])
            found.append({"id": hit[0], "text": hit[2]})
        elif not hit and not re.search(COVERED_ELSEWHERE, l, re.I) and not re.search(r"Clipper boleh|Seluruh Content", l, re.I) \
                and not re.search(r"Wajib mematuhi|Wajib tonton", l, re.I):
            ask("content_rules", f"unrecognised rule line: {l[:120]}")
            rules.setdefault("unrecognised_lines", []).append(l)
    rules["content_rules"] = found
    rules["unsure"] = unsure
    return rules


def parse_brief_file(path: str | Path, **kw) -> dict:
    """Parse docs/campaigns/<slug>.md (text between the BRIEF markers); pending → all unsure."""
    p = Path(path)
    slug = p.name[:-3] if p.name.endswith(".md") else p.stem
    return parse_brief(extract_brief(p.read_text(encoding="utf-8")), slug=slug, **kw)


# --------------------------------------------------------------------------- AI fallback

KNOWN_RULE_IDS = [r[0] for r in CONTENT_RULES]
AI_SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "category": {"type": "string", "description": "brand | creator | other"},
        "platforms": {"type": "array", "items": {"type": "string"}},
        "currency": {"type": "string", "description": "ISO code, e.g. IDR, USD"},
        "payout_model": {"type": "string", "description": "cpm | fixed_threshold | per_block | unknown"},
        "rate": {"type": "number", "description": "cpm: amount per 1000 views; per_block: amount per block; fixed_threshold: amount per qualifying post"},
        "block_views": {"type": "integer", "description": "per_block only"},
        "min_views": {"type": "integer"},
        "max_paid_views_per_post": {"type": "integer"},
        "max_payout_per_post": {"type": "number"},
        "total_budget": {"type": "number"},
        "hashtags": {"type": "array", "items": {"type": "string"}},
        "mentions": {"type": "array", "items": {"type": "string"}},
        "watermark": {"type": "string", "description": "required | forbidden | not_stated"},
        "min_length_seconds": {"type": "integer"},
        "max_length_seconds": {"type": "integer"},
        "start_date": {"type": "string", "description": "YYYY-MM-DD"},
        "end_date": {"type": "string", "description": "YYYY-MM-DD (deadline)"},
        "source_channels": {"type": "array", "items": {"type": "string"}, "description": "YouTube handles like @Name"},
        "content_rules": {"type": "array", "items": {"type": "object", "properties": {
            "id": {"type": "string", "description": "one of the known ids, or 'other'"},
            "text": {"type": "string", "description": "short English rule"}}, "required": ["id", "text"]}},
    },
    "required": ["platforms", "payout_model", "hashtags", "content_rules"],
}


def ai_gaps(rules: dict) -> list[str]:
    """Why the AI fallback should run (empty = patterns covered the brief)."""
    if rules.get("brief_pending"):
        return []
    out = []
    if (rules.get("payout") or {}).get("model") in (None, "unknown"):
        out.append("payout rate not recognised")
    if not rules.get("platforms"):
        out.append("platforms not recognised")
    if not (rules.get("hashtags") or {}).get("required_in_order"):
        out.append("hashtags not recognised")
    if not rules.get("content_rules"):
        out.append("no content rules recognised")
    if rules.get("unrecognised_lines"):
        out.append(f"{len(rules['unrecognised_lines'])} rule line(s) not recognised")
    return out


def build_ai_prompt(text: str, rules: dict, reasons: list[str]) -> str:
    lines = "\n".join(f"- {l}" for l in rules.get("unrecognised_lines", [])) or "(none)"
    return (
        "You extract campaign rules from a short-video clipping campaign brief.\n"
        "Only report what the brief states explicitly. Never guess: use an empty string, 0 or [] "
        "for anything not stated. Keep numbers as plain numbers (1.5, not '$1.50').\n"
        f"Known content-rule ids: {', '.join(KNOWN_RULE_IDS)}. Map each rule to one of them, or 'other'.\n"
        "content_rules are only about what a clip may show or say, or how it is promoted. Do NOT list "
        "platforms, hashtags, mentions, source channels, length, watermark, captions or deadlines there: "
        "they have their own fields.\n"
        "payout_model: 'cpm' = paid per 1,000 views (linear); 'fixed_threshold' = one fixed amount "
        "once a post reaches a view count; 'per_block' = amount per N views; 'unknown' otherwise.\n"
        f"The pattern parser could not handle: {'; '.join(reasons)}.\n"
        f"Lines it did not recognise:\n{lines}\n\n"
        f"BRIEF:\n{text.strip()}\n"
    )


def _mark(rules: dict, field: str) -> None:
    rules.setdefault("ai_derived", []).append(field)
    # the AI's answer replaces the pattern parser's "not found" note for the same field
    rules["unsure"] = [u for u in rules["unsure"] if not (u["field"] == field and u.get("source") != "ai")]
    rules["unsure"].append({"field": field, "why": "AI-derived from the brief: confirm in the Campaign screen",
                            "source": "ai"})


def merge_ai(rules: dict, data: dict) -> dict:
    """Fill gaps from the AI answer. Pattern values always win; every filled field is marked."""
    data = data or {}
    for key in ("name", "category"):
        if not rules.get(key) and data.get(key):
            rules[key] = str(data[key]).strip().lower() if key == "category" else str(data[key]).strip()
            _mark(rules, key)
    if not rules.get("platforms") and data.get("platforms"):
        plats = []
        for p in data["platforms"]:
            q = PLATFORM_ALIASES.get(str(p).lower().replace("instagram reels", "instagram").strip())
            if q and q not in plats:
                plats.append(q)
        if plats:
            rules["platforms"] = plats
            _mark(rules, "platforms")

    payout = rules.setdefault("payout", {})
    model, rate = (data.get("payout_model") or "unknown").lower(), data.get("rate") or 0
    if payout.get("model") in (None, "unknown") and model != "unknown" and rate:
        cur = (data.get("currency") or "").upper() or _currency_in(rules.get("_text", "")) or "UNSTATED"
        payout.update(currency=cur, ai=True)
        if model == "cpm":
            payout.update(model="per_block", per_block=rate, block_views=1000, stated_as=f"CPM {rate} {cur}",
                          rounding_note="CPM is usually prorated; per-1,000 blocks are an approximation")
        elif model == "fixed_threshold":
            payout.update(model="fixed_threshold", per_video=rate, min_views=data.get("min_views") or 0)
        elif model == "per_block" and data.get("block_views"):
            payout.update(model="per_block", per_block=rate, block_views=int(data["block_views"]))
        if model != "fixed_threshold" and data.get("min_views"):
            payout["min_views"] = int(data["min_views"])
        if data.get("max_paid_views_per_post"):
            payout["max_paid_views_per_video"] = int(data["max_paid_views_per_post"])
        if data.get("max_payout_per_post"):
            payout["max_payout_per_video"] = data["max_payout_per_post"]
        _mark(rules, "payout")
    if not rules.get("budget") and data.get("total_budget"):
        rules["budget"] = {"currency": (data.get("currency") or "").upper() or _currency_in(rules.get("_text", "")),
                           "total": data["total_budget"]}
        _mark(rules, "budget")

    if not (rules.get("hashtags") or {}).get("required_in_order") and data.get("hashtags"):
        tags = ["#" + str(t).lstrip("#").strip() for t in data["hashtags"] if str(t).strip("# ")]
        rules["hashtags"] = {"required_in_order": tags}
        _mark(rules, "hashtags")
    if not rules.get("mentions") and data.get("mentions"):
        rules["mentions"] = ["@" + str(m).lstrip("@").strip() for m in data["mentions"] if str(m).strip("@ ")]
        _mark(rules, "mentions")
    wm = (data.get("watermark") or "").lower()
    if "watermark" not in rules and wm in ("required", "forbidden"):
        rules["watermark"] = {"required": wm == "required", "forbidden": wm == "forbidden"}
        _mark(rules, "watermark")
    if not rules.get("video") and (data.get("min_length_seconds") or data.get("max_length_seconds")):
        rules["video"] = {"min_seconds": data.get("min_length_seconds") or None,
                          "max_seconds": data.get("max_length_seconds") or None}
        _mark(rules, "video")
    if not rules.get("period") and (data.get("start_date") or data.get("end_date")):
        rules["period"] = {"start": data.get("start_date") or None, "end": data.get("end_date") or None}
        _mark(rules, "period")
    if not rules.get("sources") and data.get("source_channels"):
        rules["sources"] = [{"platform": "youtube", "channel": "@" + str(c).split("@")[-1].strip("/ "),
                             "job_source": True} for c in data["source_channels"] if str(c).strip()]
        _mark(rules, "sources")

    have = {r["id"] for r in rules.get("content_rules", [])}
    for i, r in enumerate(data.get("content_rules") or []):
        rid = r.get("id") if r.get("id") in KNOWN_RULE_IDS else None
        if rid in have:
            continue
        rid = rid or "custom_" + re.sub(r"[^a-z0-9]+", "_", (r.get("text") or f"rule {i}").lower()).strip("_")[:40]
        if rid in have:
            continue
        have.add(rid)
        rules.setdefault("content_rules", []).append({"id": rid, "text": (r.get("text") or "").strip(), "ai": True})
        _mark(rules, f"content_rules.{rid}")
    return rules


def router_ai(max_tokens: int = 2000) -> Callable[[str, dict], dict]:
    """AI callable for parse_brief(ai=...) via shared.ai.router (utility provider, task 'brief').
    The process must have called shared.ai.router.configure(setting, log) first."""
    from shared.ai.router import ai_generate_json

    def call(prompt: str, schema: dict) -> dict:
        return ai_generate_json(prompt, schema, task="brief", max_tokens=max_tokens)
    return call
