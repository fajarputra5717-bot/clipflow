"""
Clip description (caption) prompt (115): ONE builder for the backend's "Generate description"
button and the worker's campaign description at analysis, so both write the same kind of text.
Moved verbatim from main.py; campaign clips get no hashtags from the model — the campaign's
own are appended afterwards in exact order (campaigns.with_campaign_hashtags).
"""

DESCRIPTION_SCHEMA = {
    "type": "object",
    "properties": {"description": {"type": "string"}},
    "required": ["description"],
}


def build_description_prompt(*, platform, content_type, title, subtitle, lang, lang_name,
                             rules=None, hashtags="", campaign=""):
    platform_label = {
        "youtube_shorts": "YouTube Shorts",
        "instagram_reels": "Instagram Reels",
        "tiktok": "TikTok",
    }.get(platform, "Shorts")

    prompt = (
        f"Write a short, scroll-stopping {platform_label} "
        f"caption/description for a vertical short-form clip.\n"
        f"Genre/mood: {content_type}\n"
        f"Clip title: {title}\n"
        f"Spoken subtitle in the clip ({lang_name}): {subtitle}\n\n"
        "Requirements: 1-3 short sentences or a punchy hook "
        f"line, native-sounding {lang_name}"
        + (" (bilingual is fine if it reads naturally)" if lang == "id" else "")
        + ", no markdown.\n\n"
        "Important: the title and subtitle above are all you "
        "know about this clip's content — you do not know the "
        "specific game, show, or brand name unless it is "
        "explicitly written in them. Do NOT invent, guess, or "
        "reuse a made-up product/game name (e.g. never write "
        "something like \"Riftstorm\" unless that exact word "
        "appears in the title or subtitle above). Talk about "
        "the moment itself instead ("
        + ('e.g. "this gameplay", "this video", "this match"' if lang == "en"
           else 'e.g. "gameplay ini", "video ini", "match ini"')
        + ").\n\n"
        + (
            "Do not write any hashtags; they are added separately."
            if rules else
            "End with 3-6 relevant hashtags"
            + (f" including {hashtags}" if hashtags else "")
            + (
                f", and mention the campaign tag {campaign}"
                if campaign
                else ""
            )
            + ". For any hashtags, only use generic ones tied to "
            "the genre/platform (e.g. #Shorts, #ContentIndonesia, "
            "#Highlights) — never a specific product/game hashtag "
            "unless that name literally appears in the title or "
            "subtitle above."
        )
        + "\n\nRespond ONLY with JSON: "
        '{"description": "<the caption>"}'
    )

    return prompt
