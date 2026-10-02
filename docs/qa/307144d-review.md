# QA review · 307144d · 100 loudness verify acts: corrective pass, chip if still off, previews verified (closes gate-P0 #2)

Reviewer: Lane C · 2026-10-02 · deployed worker confirmed

Every output re-measured with ebur128; > 1 LU off or TP > −1 dBTP → one corrective pass (limiter headroom +
overshoot + 0.3 dB), re-measured; still off → "loudness" chip with numbers; never fatal; previews run the same
chain at 96k.

## Re-check (fresh GTA RP job fbda481f, peaky game audio)
| clip | pass 1 | after corrective | QA ebur128 |
|---|---|---|---|
| cfb5104c final | −14.3 / −0.9 dBTP | −14.1 / −1.3 | **−14.2 / −1.0** ✓ |
| 1336ee96 final | −15.8 / −1.2 | −14.9 / −1.4 | **−14.9 / −1.4** ✓ (within 1 LU) |
| cfb5104c preview | | | −14.1 / −1.3 ✓ |
| 1336ee96 preview | −15.8 / −0.1 | −15.3 / −1.7 | −15.3 / −1.7 → chip (until the final cleared it) |
On QA test job 4590c193 a preview stayed at −15.2 LUFS with the chip "Loudness still off after a corrective pass".
**Not silent any more → FIXED as claimed.**

## Findings
1. **Low · P1 backlog (owner 2026-10-02): peaky sources can end ~1.2 LU short (−15.2) with a chip; accepted for
   now.** Suggested fix: light compression before loudnorm for peaky sources (the corrective pass only lowers the
   limiter ceiling, so it fixes peaks, not loudness).
2. **Low · disk reserve under-counts** with the second temp file (`*.loudnorm2.tmp.mp4`): peak usage ≈ 3× the file,
   reserve is 2× + 1 MB.
3. **Process · containers recreated again during a QA render** (16:36:20, while QA's second final was finishing; it
   completed). Please check `/api/activity` before restarting.
