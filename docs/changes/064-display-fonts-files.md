# 064 — R-19 prep: SIL-OFL caption fonts added to worker/fonts/ (files only)
Date: 2026-09-29 · Commit: see `git log --grep "R-19 prep"` · Files: worker/fonts/** · No code changed

## What changed
Added Anton, Bebas Neue, Archivo Black, Poppins Bold + ExtraBold (static), and Montserrat, Oswald and Inter (variable),
each in its own `worker/fonts/<family>/` with that family's `OFL.txt`. They come from `google/fonts` `ofl/<family>/`
pinned at commit 23e54b51ddffbc7713c583748e3bd86f62b1fa4a. `worker/fonts/README.txt` lists the fc-scan family names,
the files and their sha256. The existing Dockerfile `COPY fonts/` + `fc-cache -f` picks them up on the next worker build.

## Licence check
All 7 `METADATA.pb` files say `license: "OFL"`. All 7 `OFL.txt` bodies are the same SIL OFL 1.1 text (compared after
normalising whitespace and http→https). No family declares a Reserved Font Name. File sizes match the GitHub listing.

## Decisions & trade-offs
- google/fonts has **no static Montserrat/Oswald/Inter** any more, only `[wght]` variable files. They are shipped
  as is. fontconfig exposes the named instances (Montserrat Bold/ExtraBold/Black, Oswald Bold, Inter Bold/Black).
  Whether libass selects the instance or renders the default weight is **untested**. If it renders the default,
  cut statics with `fontTools.varLib.instancer` (OFL allows it; no RFN).
- Only the weights R-19 names were taken for Poppins (static files exist, so no need for the whole family).

## Gotchas for future changes (Lane A wiring)
- Use the exact family names: `Anton`, `Bebas Neue`, `Archivo Black`, `Poppins`, `Montserrat`, `Oswald`, `Inter`.
  Weight comes from the style (Bold / ExtraBold / Black), so the ASS `Bold` flag alone gives only Bold (700).
- R-19's known bug: the normaliser falling back to the default font. Trace it to the `Style:` line and render every
  font/weight to a frame.

## Verification
`fc-scan` on the host for every file (output in README.txt). Not built into the worker image, and nothing rendered.
