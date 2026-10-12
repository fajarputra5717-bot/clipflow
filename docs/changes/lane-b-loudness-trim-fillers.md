
## Update after QA a156a53 (trim not applied on an ordinary compressed clip)
The trim stacked a gain pass on an already limited AAC file: it overshot the peak (dropped) or lost loudness.
Now up to two trims, stopping once within ±0.5 LU: (1) redo the normalising pass from the ORIGINAL with the
target offset by the measured error, (2) a gain pass on the result; each kept only if closer and the peak is no
worse. Throwaway worker container, real downloads, compression on: 6 of 7 land -14.0..-14.4 (before: two at
-14.6); the clipped source stays -15.0.
