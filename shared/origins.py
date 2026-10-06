"""138: is a cookie-authenticated write coming from our own page?

Compare the browser's Origin with the URL the browser used to reach us, as scheme + host + port
(default ports normalised: http 80, https 443). Behind our nginx that URL is
X-Forwarded-Proto + X-Forwarded-Host ($http_host: the Host header exactly as the browser sent it,
port included; nginx's own $server_port is the container port and can't be used). X-Forwarded-Port
(other proxies) fills in a missing port. Anything else must be listed in CORS_ALLOWED_ORIGINS.
The backend is reachable only through nginx (127.0.0.1 + the compose network), so these headers are ours."""

from urllib.parse import urlsplit

DEFAULT_PORTS = {"http": 80, "https": 443}


def _split_host(hostport: str):
    hostport = (hostport or "").strip().lower()
    if not hostport:
        return "", None
    if hostport.startswith("["):  # [v6]:port
        host, _, rest = hostport[1:].partition("]")
        port = rest[1:] if rest.startswith(":") else ""
    else:
        host, _, port = hostport.rpartition(":") if hostport.count(":") == 1 else (hostport, "", "")
    try:
        return host, int(port) if port else None
    except ValueError:
        return host, None


def key(scheme: str, hostport: str, port=None):
    """(scheme, host, port) with the default port filled in; None if unusable."""
    scheme = (scheme or "").lower()
    if scheme not in DEFAULT_PORTS:
        return None
    host, p = _split_host(hostport)
    if not host:
        return None
    if p is None and port not in (None, ""):
        try:
            p = int(port)
        except (TypeError, ValueError):
            p = None
    return scheme, host, p or DEFAULT_PORTS[scheme]


def origin_key(origin: str):
    if not origin or origin == "null":
        return None
    try:
        u = urlsplit(origin.strip().rstrip("/"))
    except ValueError:
        return None
    return key(u.scheme, u.netloc)


def allowed(origin: str, *, scheme: str, host: str, forwarded_port=None, extra=()) -> bool:
    """True when `origin` is our own scheme+host+port, or listed in `extra` (CORS_ALLOWED_ORIGINS)."""
    o = origin_key(origin)
    if o is None:
        return False
    if o == key(scheme, host, forwarded_port):
        return True
    return o in {origin_key(x) for x in extra}
