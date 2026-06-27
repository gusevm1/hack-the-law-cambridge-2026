"""Single-flight, globally-paced CourtListener client.

CourtListener allows ~4 requests/min; bursts trip a 15-minute throttle that then
starves everything. Inconsistent retrieval traces entirely to *concurrent* callers
(ingest + resolve + ad-hoc checks) racing that limit. So every CL request goes
through ``cl_get_json``, which:

1. holds an exclusive **file lock** — only one CL request is in flight at a time,
   process-wide (and across separate processes), so nothing can race the limit;
2. enforces a **minimum interval** between requests via a persisted timestamp
   (default 20s ⇒ 3/min, a safe margin under 4/min);
3. **backs off on 429** and retries rather than truncating.

The lock/timestamp live in files (paths overridable via env) so independent
invocations cooperate. This is the one gate that makes retrieval consistent.
"""

from __future__ import annotations

import fcntl
import json
import os
import ssl
import time
import urllib.error
import urllib.request
from typing import Any

USER_AGENT = "htl-citator/0.1 (hack-the-law-cambridge-2026)"

_LOCK_PATH = os.environ.get("CL_LOCK_PATH", "/tmp/htl-cl.lock")
_STATE_PATH = os.environ.get("CL_STATE_PATH", "/tmp/htl-cl.last")
MIN_INTERVAL = float(os.environ.get("CL_MIN_INTERVAL", "20"))

# macOS Pythons often lack a system CA bundle; certifi is the repo's standard fix.
try:
    import certifi

    _SSL_CTX: ssl.SSLContext | None = ssl.create_default_context(cafile=certifi.where())
except Exception:  # pragma: no cover
    _SSL_CTX = None


def _last_call() -> float:
    try:
        return float(open(_STATE_PATH).read().strip() or 0)
    except (OSError, ValueError):
        return 0.0


def _stamp(t: float) -> None:
    try:
        with open(_STATE_PATH, "w") as f:
            f.write(str(t))
    except OSError:  # pragma: no cover - best effort
        pass


def _request_with_backoff(url: str, token: str | None, timeout: int, retries: int) -> dict[str, Any]:
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        if token:
            req.add_header("Authorization", f"Token {token}")
        try:
            with urllib.request.urlopen(req, timeout=timeout, context=_SSL_CTX) as resp:  # noqa: S310
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < retries:
                wait = 20 * (attempt + 1)
                print(f"    · 429 rate-limited; backing off {wait}s")
                time.sleep(wait)
                continue
            raise
    raise RuntimeError("unreachable")  # pragma: no cover


def cl_get_json(url: str, *, token: str | None = None, timeout: int = 30,
                retries: int = 4) -> dict[str, Any]:
    """Fetch JSON from CourtListener under a global single-flight lock + pacing.

    Blocks until it's safe to call (no other in-flight request, and ≥ MIN_INTERVAL
    since the last global call), then requests with 429 backoff. Serialising here is
    what keeps us under the rate limit no matter how many callers there are.
    """
    with open(_LOCK_PATH, "w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        wait = MIN_INTERVAL - (time.time() - _last_call())
        if wait > 0:
            time.sleep(wait)
        try:
            return _request_with_backoff(url, token, timeout, retries)
        finally:
            _stamp(time.time())
