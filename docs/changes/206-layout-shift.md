# 206 · Layout shift under 0.05 (deep audit M4, 2026-10-14)

Measured with a layout-shift observer, mocked API delayed 300 ms (data after the first frame, like the real server):

| Case | Before | After |
|---|---|---|
| First paint 390 | 0.015 | 0.000 |
| First paint 768 | 0.083 | 0.000 |
| First paint 1280 | 0.061 | 0.000 |
| Import → Review 390 | 0.084 | 0.000 |
| Import → Review 768 | 0.021 | 0.000 |

(Lane C's staging numbers: 0.108 / 0.095 / 0.039 first paint, 0.084 switch at 390.)
Causes: `#langNote` ("Detected from the audio.") and `#clipsNote` ("Your default: N") were empty `<p>`s filled after
the API answered, each adding a 19 px line and pushing the rest of the Analyze form down → `.seg-note` keeps one line
(`min-height: 1lh`, 1.4em fallback). Review (`review.js`, Lane B's file, two lines): the "Loading clips…" line sat in
`#rvBody` and the filters rendered above it, pushing it 237 px down on a phone → the loading line now sits in
`#rvFilters` and is replaced by the filters (a replacement is not a shift); the filter-load error clears it. The pill's
list reserves its button height (`min-height: var(--pill-btn)`) so the fixed pill doesn't grow when the steps render.
Spec: cls.spec.js (asserts < 0.05 for all five cases; failed on the old code for 768/1280 first paint and the 390 switch).
