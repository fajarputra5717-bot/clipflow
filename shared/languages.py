"""
Per-job language (079): the languages ClipFlow handles end to end and
their caption stoplists.

jobs.language is what the user asked for (auto|en|id; NULL = a job from
before 079, treated as Indonesian). jobs.effective_language is what the
pipeline actually used after Whisper's detection; everything downstream
(hook prompt, AI text tools, Submagic) reads that via job_language().
"""

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


# Caption stoplists, prepared for TASKS-3 T2 keyword highlighting (not used
# yet): words never worth highlighting. Lower-case; compare after stripping
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
    """.split()),
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
    """.split()),
}


def stopwords_for(code):
    return STOPWORDS.get(code, STOPWORDS[DEFAULT])
