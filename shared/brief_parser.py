"""Campaign brief text → rules dict (the docs/campaigns/<slug>.rules.json schema) + `unsure` list.

Deterministic and pure (no AI, no I/O except parse_brief_file): the briefs are Indonesian
MotionKlip/Whop-style templates with stable section labels, so patterns beat a model here and the
result is repeatable. Anything the text doesn't settle goes into `unsure` as
{"field", "why"} instead of being guessed; a human (or the admin) answers those.

  rules = parse_brief(text, today=date(2026, 10, 2))
  shared.payouts.model_from_rules(rules)   # FixedThreshold / PerBlock / Unknown
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Optional

BRIEF_START, BRIEF_END = "--- BRIEF START ---", "--- BRIEF END ---"

PLATFORM_ALIASES = {
    "tiktok": "tiktok", "tik tok": "tiktok", "youtube": "youtube", "yt": "youtube",
    "youtube shorts": "youtube", "instagram": "instagram", "ig": "instagram", "reels": "instagram",
    "facebook": "facebook", "fb": "facebook", "x": "x", "twitter": "x", "threads": "threads",
}
MONTHS_ID = {"januari": 1, "februari": 2, "maret": 3, "april": 4, "mei": 5, "juni": 6, "juli": 7,
             "agustus": 8, "september": 9, "oktober": 10, "november": 11, "desember": 12,
             "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7, "august": 8,
             "october": 10, "december": 12}

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


def parse_brief(text: Optional[str], *, today: Optional[date] = None, slug: Optional[str] = None) -> dict:
    """Rules dict in the docs/campaigns schema, plus `unsure: [{field, why}]`.

    today  anchors years the brief leaves out (briefs say '30 September', '1 Oktober').
    """
    today = today or date.today()
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
    elif re.search(r"tanpa watermark|no watermark|dilarang .*watermark", text, re.I):
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
    rules["content_rules"] = found
    rules["unsure"] = unsure
    return rules


def parse_brief_file(path: str | Path, **kw) -> dict:
    """Parse docs/campaigns/<slug>.md (text between the BRIEF markers); pending → all unsure."""
    p = Path(path)
    slug = p.name[:-3] if p.name.endswith(".md") else p.stem
    return parse_brief(extract_brief(p.read_text(encoding="utf-8")), slug=slug, **kw)
