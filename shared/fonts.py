"""
Caption fonts (R-19): the one list backend and worker agree on.
index.html's SUBTITLE_FONTS / SUBTITLE_FONT_PREVIEW mirror it by hand.

Each name is what goes into the ASS `Style:` Fontname field, so it must
match an installed family/full name exactly (`fc-list : family style`).
The display fonts ship in worker/fonts/ (SIL OFL, see each OFL.txt);
the Dockerfile installs them into /usr/share/fonts/truetype/clipflow/.

ass_bold:
    None -> keep the style preset's Bold flag (the original system fonts,
            unchanged behaviour).
    0    -> always Bold=0. The weight is selected by the family name
            ("Montserrat Black", "Inter Bold"): libass picks that named
            instance. Setting the ASS bold flag on top adds libass faux
            bold (+10-15% ink on Inter, Oswald, Anton, Archivo Black),
            measured in the libass spike (docs/changes/065).
"""

DEFAULT_CAPTION_FONT = "Liberation Sans Bold"

CAPTION_FONTS = {
    # System fonts from the Debian packages (baseline list).
    "Liberation Sans Bold": {"ass_bold": None},
    "Liberation Sans": {"ass_bold": None},
    "Noto Sans Bold": {"ass_bold": None},
    "Noto Sans": {"ass_bold": None},
    "DejaVu Sans Bold": {"ass_bold": None},
    "DejaVu Sans": {"ass_bold": None},
    # Display fonts (worker/fonts/, R-19).
    "Montserrat Black": {"ass_bold": 0},
    "Montserrat ExtraBold": {"ass_bold": 0},
    "Montserrat Bold": {"ass_bold": 0},
    "Inter Black": {"ass_bold": 0},
    "Inter Bold": {"ass_bold": 0},
    "Oswald Bold": {"ass_bold": 0},
    "Poppins ExtraBold": {"ass_bold": 0},
    "Poppins Bold": {"ass_bold": 0},
    "Anton": {"ass_bold": 0},
    "Bebas Neue": {"ass_bold": 0},
    "Archivo Black": {"ass_bold": 0},
}


def normalize_caption_font(name):
    """Exact catalog name for `name` (case/space-insensitive), else the
    default. Returns (font, recognised)."""
    wanted = " ".join(str(name or "").split()).casefold()
    for font in CAPTION_FONTS:
        if font.casefold() == wanted:
            return font, True
    return DEFAULT_CAPTION_FONT, False


def caption_font_bold(name, preset_bold):
    """ASS Style Bold value for this font given the preset's value."""
    override = CAPTION_FONTS.get(name, {}).get("ass_bold")
    return preset_bold if override is None else override
