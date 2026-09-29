# 065 — libass spike: R-18 effects + R-19 font weights (tests only)
Date: 2026-09-29 · Commit: see `git log --grep "libass spike"` · Files: tests/libass-spike/*, docs only · No app code changed

## Setup
Throwaway container from the `riftstorm-worker` image (`docker run --rm --network none`): ffmpeg 5.1.9,
**libass 0.17.1** (Debian 12), fontconfig provider. `worker/fonts/` was mounted read-only at
`/usr/share/fonts/truetype/clipflow/`, then `fc-cache -f` ran. The 1080×1920 frames are the `ass=` filter over a
grey `color` source. libass's own `fontselect:` log lines (ffmpeg `-loglevel verbose`) record which file and named
instance it picked. Ink area (pixels > 160 in a fixed crop, same text at 64 px) quantifies weight. Reproduce:
`tests/libass-spike/run.sh` (the command is in its header).

## R-18 results (frames looked at, not just logged)
| Feature | Result | What the frame shows |
|---|---|---|
| per-word `{\c}` with `\kf` | **works** | At 1.0 s, "THIS" is yellow and "WORD" red, the colours set by each word's `\c`. "GLOWS NOW" are still the grey SecondaryColour. At 0.1 s only the first letter of THIS is filled (the sweep). |
| `\p1` rounded box behind text | **works** | A separate event on layer 0: a 560×110 bezier-cornered rectangle (`\bord0\shad0`, `\1a&H20&`). It renders as a clean orange rounded box with "BOXED HOOK" on layer 1 on top. Rounding and padding are pure geometry, so make_ass must compute the text width itself. |
| per-word `\t` | **works, with one gotcha** | Naive `{\t(0,300,…)}POP {\t(300,600,…)}ONE …`: at 0.07 s the **whole line** is already tinted and scaling, and at 1.0 s all words sit at 140 %. An override (`\t` included) carries over to every later word. The fix, verified at 0.07 / 0.37 / 0.67 s, is to prefix each word with its base values (`\fscx100\fscy100\c&HFFFFFF&`) before its own `\t`, plus a second `\t` back to 100 % for a pop. Then exactly one word (POP, then ONE, then AT) is enlarged and yellow. |
| colour emoji | **does not work → feature dropped** | The worker image has no emoji font: 🔥 draws as tofu, and 😂 ✅ fall back to **monochrome outline** glyphs (DejaVu/FreeSerif). With Noto Color Emoji mounted (CBDT bitmap font), libass selects it (`-> NotoColorEmoji.ttf`) but draws **nothing**: blank gaps, 0 saturated pixels in the crop. libass has no colour-bitmap glyph support. |

Emoji conclusion: drop the emoji feature (as REBUILD says) and **strip emoji from caption text** in make_ass. Today
they render as tofu or monochrome outlines. Don't install a colour emoji font, which makes them vanish instead.

## R-19 font weights: no fallback to Regular
libass selects the **named instance** of each variable font: the face index carries the instance in its high 16
bits, e.g. `Montserrat[wght].ttf, 589824, Montserrat_900wght`.
| Requested | Picked (fontselect) | Ink | Looks |
|---|---|---|---|
| Montserrat `\b0` / `\b1`(=700) / `\b800` / `\b900` | 400 / 700 / 800 / 900 instances | 3044 / 5507 / 6365 / 7197 | four distinct weights |
| `Montserrat ExtraBold` / `Montserrat Black` (`\b0`) | 800 / 900 instances | 6365 / 7197 | identical to `\b800` / `\b900` |
| Oswald `\b0` / `\b1` | Regular / 700 instance | 2890 / 4705 | distinct |
| Inter `\b0` / `\b1` / `\b900` | Regular / 700 / 900 instances | 3640 / 6276 / 7686 | distinct |
| Poppins `\b1`, `\b800`, `Poppins ExtraBold` | Poppins-Bold.ttf / -ExtraBold.ttf | 4104 / 4574 / 4574 | correct statics |
| Anton, Bebas Neue, Archivo Black (`\b0`) | their own files | — | correct faces |

**The condition for cutting static instances was not met, so none were made.** worker/fonts/ is unchanged.

### Gotcha: synthetic bold on top of the right instance
Same instance, same file, but `\b` adds libass faux-emboldening for some faces:
- Inter: `Inter Bold` (\b0) 5462 vs `Inter \b1` 6276 (+15 %). `Inter Black` (\b0) 6962 vs `\b900` 7686 (+10 %).
- Oswald: `Oswald Bold` (\b0) 4263 vs `Oswald \b1` 4705 (+10 %).
- Statics: Anton `\b1` 5118 vs `\b0` 4611 (+11 %). Archivo Black `\b1` 8737 vs 7972 (+10 %).
- **None** for Montserrat (full name vs `\b` identical) or Poppins.
The likely cause is that libass compares the requested weight with the face's own OS/2 weight, which for Inter/Oswald
is the default instance's 400. Visually it is subtle (slightly blobbier counters) but real.

**Recommendation for R-19 wiring (Lane A):** put the weight in the **font name** and keep `Bold` at 0 in the ASS
`Style:`. Use `Montserrat Black`, `Montserrat ExtraBold`, `Montserrat Bold`, `Inter Black`, `Inter Bold`,
`Oswald Bold`, `Poppins ExtraBold`, `Poppins` (Bold file), `Anton`, `Bebas Neue`, `Archivo Black`. This gives the
designed weight for every face without faux bold and without extra files. If a style really wants the ASS bold
flag, do not set it on Anton, Bebas Neue, Archivo Black, Inter or Oswald.

## Not covered
The fonts are not yet in the built worker image (it has only README in `clipflow/`), so this used a bind mount.
Italics were not tested. Outline/border (`\bord`) interaction with faux bold was not measured. make_ass() itself was not run.
