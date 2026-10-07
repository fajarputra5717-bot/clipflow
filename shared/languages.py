"""
Per-job language (079): the languages ClipFlow handles end to end and
their caption stoplists.

jobs.language is what the user asked for (auto|en|id; NULL = a job from
before 079, treated as Indonesian). jobs.effective_language is what the
pipeline actually used after Whisper's detection; everything downstream
(hook prompt, AI text tools, Submagic) reads that via job_language().
"""

import re

SUPPORTED = ("en", "id")
REQUESTABLE = ("auto",) + SUPPORTED
NAMES = {"en": "English", "id": "Indonesian"}
DEFAULT = "id"            # legacy jobs and the default fallback
MIN_CONFIDENCE = 0.6      # below this, Auto falls back to the form's last explicit choice


def job_language(effective=None, requested=None):
    """'en' or 'id' for a job row: effective first, then an explicit
    request, else the legacy default."""
    if effective in SUPPORTED:
        return effective
    if requested in SUPPORTED:
        return requested
    return DEFAULT


def name(code):
    return NAMES.get(code, NAMES[DEFAULT])


# Caption stoplists for keyword highlighting (111): words never worth
# highlighting, incl. exclamations and religious words (119). Lower-case; compare after stripping
# punctuation. Indonesian includes common spoken/slang particles.
STOPWORDS = {
    "id": frozenset("""
        ada adalah agar akan aku aja ajah aku amat anda apa apakah atau
        bagaimana bahwa baik banget banyak bila bisa boleh buat bukan
        cuma dah dalam dan dari deh dengan di dia dong dulu gak ga gitu
        gua gue guys hal hanya harus hingga ia ini itu iya ya jadi jika
        juga kak kalau kalo kamu kami kan karena kayak ke kemudian kenapa
        kita kok lagi lah lain lalu lu lo mah mana masih mau maka memang
        mereka mungkin nah nanti nih nya oleh pada para pun saat saja
        sama sampai sangat saya se sebuah sedang seperti sih siapa sini
        situ sudah tapi telah tentang terus tuh untuk wah waktu yang yuk
    """.split()) | frozenset("""
        astaghfirullah astaghfirullahaladzim astagfirullah astagfirullahaladzim
        astaghfirulloh allah alloh ya allahu akbar masyaallah mashaallah
        masya subhanallah alhamdulillah insyaallah inshaallah bismillah
        wallahi wallah demi tuhan astaga ampun anjir anjay anjing anjrit
        buset busyet bjir njir waduh wadaw wih woy woi weh lho loh dih
        hah heh hahaha haha wkwk wkwkwk
    """.split()),  # 119: exclamations / religious words (never highlight)
    "en": frozenset("""
        a about after again all also am an and any are as at be because
        been before being but by can could did do does doing down during
        each few for from further had has have having he her here hers
        him his how i if in into is it its just me more most my no nor
        not now of off on once only or other our out over own same she
        should so some such than that the their them then there these
        they this those through to too under until up very was we were
        what when where which while who whom why will with would you
        your yeah okay ok like gonna wanna oh uh um
    """.split()) | frozenset("""
        omg wow whoa woah god gosh jesus christ lord holy damn hell
        dang yo bro dude haha hahaha lol wtf
    """.split()),  # 119: exclamations / religious words (never highlight)
}


def stopwords_for(code):
    return STOPWORDS.get(code, STOPWORDS[DEFAULT])


# ---- filler words (P4 task 5b, lane B): SUGGESTIONS in the editor timeline, never auto-cut.
# Each filler is a sequence of token patterns (regex, full match on the lower-cased word with
# punctuation stripped), so stretched forms ("emmm", "eeeh") and multi-word fillers match.
FILLERS = {
    "id": [
        ["e+h+"], ["e+m+"], ["a+nu+"], ["kayak"], ["gitu"], ["apa", "namanya"],
    ],
    "en": [
        ["u+m+"], ["u+h+"], ["like"], ["you", "know"], ["i", "mean"],
    ],
}

_FILLER_RE = {code: [[re.compile(rf"^{p}$") for p in seq] for seq in seqs] for code, seqs in FILLERS.items()}
_PUNCT = re.compile(r"[^\w']+", re.UNICODE)


def _norm(word):
    return _PUNCT.sub("", str(word or "").lower())


def filler_spans(words, code=None):
    """Filler suggestions in a word list [{text|word, start, end}, ...] → [{i0, i1, start, end, text}]
    (i0..i1 inclusive word indexes). code = the job's language; None/unknown = every list.
    Longest match first, no overlaps."""
    lists = [_FILLER_RE[code]] if code in _FILLER_RE else list(_FILLER_RE.values())
    seqs = sorted((s for lst in lists for s in lst), key=len, reverse=True)
    toks = [_norm(w.get("text") if isinstance(w, dict) and "text" in w else w.get("word")) for w in words]
    out, i = [], 0
    while i < len(toks):
        hit = next((s for s in seqs if i + len(s) <= len(toks)
                    and all(p.match(toks[i + k]) for k, p in enumerate(s))), None)
        if hit:
            j = i + len(hit) - 1
            out.append({"i0": i, "i1": j, "start": float(words[i]["start"]), "end": float(words[j]["end"]),
                        "text": " ".join(str(words[k].get("text") or words[k].get("word") or "") for k in range(i, j + 1))})
            i = j + 1
        else:
            i += 1
    return out
