# 139 · Login limits: 5 failures per username + IP (15 min), 50 per username from any IP, 20 per IP · app/auth.py, main.py

- Lane C Low (P1.5 gate): 5 bad passwords locked a USERNAME for everyone for 15 min (lockout DoS). Now the tight limit
  is per username + client IP (`LOGIN_MAX_FAILS_USER_IP = 5`), a looser per-username limit (`LOGIN_MAX_FAILS_USER =
  50`) still stops distributed guessing, and the per-IP limit (20, any usernames) stays. Window 15 min, 429 +
  Retry-After as before. A good login clears that user's failures from that IP only.

**Verified:** backend image import ok; prod login 200 (limits are write-path: probe of the three limits on staging).

**Staging (lane-a-limits, fake X-Real-IP 10.99.x.x, direct to the backend):** 5 wrong from IP1 → 401×5, 6th (right
password) 429; same user from IP2 with the right password 200 (no lockout DoS); 50 failures across 10 IPs → right
password from a fresh IP 429; 20 failures from one IP (any usernames) → 21st 429, another IP unaffected. Lane A's probe
rows deleted afterwards.
