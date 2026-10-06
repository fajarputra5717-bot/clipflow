"""137: "Get another hook" must return a moment distinct from every clip this job has had.

A candidate range is too close to a used one when they overlap by more than 30 % of the
shorter of the two, or their starts are within 10 s. Pure; used by main.py's new-hook."""

OVERLAP_MAX_FRAC = 0.30
START_MIN_GAP_S = 10.0


def too_close(a, b) -> bool:
    (s1, e1), (s2, e2) = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
    if abs(s1 - s2) < START_MIN_GAP_S:
        return True
    overlap = max(0.0, min(e1, e2) - max(s1, s2))
    shorter = min(e1 - s1, e2 - s2)
    return shorter > 0 and overlap > OVERLAP_MAX_FRAC * shorter


def conflict(candidate, used):
    """The first used range `candidate` is too close to, else None."""
    return next((u for u in used if too_close(candidate, u)), None)


def merge(used, *ranges, limit=200):
    """Append ranges not already listed (rounded to 0.1 s); keeps the newest `limit`."""
    seen = {(round(float(s), 1), round(float(e), 1)) for s, e in used}
    out = [[float(s), float(e)] for s, e in used]
    for s, e in ranges:
        key = (round(float(s), 1), round(float(e), 1))
        if key not in seen and float(e) > float(s):
            seen.add(key)
            out.append([float(s), float(e)])
    return out[-limit:]
