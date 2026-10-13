# 202 · Closed job overlay is hidden + inert (deep audit M2, 2026-10-13)

`#jobOverlay` was `opacity:0; pointer-events:none` when closed, so Tab reached its invisible × and screen readers read
"Running jobs / No jobs running". Closed now = `visibility:hidden` (delayed by `--dur-4` so the close animation still
plays) + the `inert` attribute (toggled in `renderJobOverlay()`, present in the markup at load). Spec
`overlays.spec.js` "Tab never lands inside an invisible layer" walks 30 Tab stops and fails if focus is inside any
hidden/transparent ancestor (failed before the fix on both projects).
