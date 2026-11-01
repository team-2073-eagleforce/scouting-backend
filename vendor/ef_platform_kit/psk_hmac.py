"""psk-hmac sign/verify. Mirrors libs/node/src/psk-hmac.js."""
from __future__ import annotations

import hmac
import re
import secrets
import threading
import time
from typing import Callable, Mapping, Optional

from .canonical import ALGORITHM, canonical_string, hmac_hex, sha256_hex, split_target

DEFAULT_SKEW_MS = 300_000
_SIG_RE = re.compile(r"Signature=([0-9a-f]{64})")
_NONCE_RE = re.compile(r"^[A-Za-z0-9_-]{16,128}$")


class AuthError(Exception):
    status = 401


class ForbiddenError(AuthError):
    status = 403


def _now_ms() -> int:
    return int(time.time() * 1000)


def sign_request(*, key_id: str, secret: str, method: str, target: str, body: bytes | str | None = b"",
                 timestamp: Optional[int] = None, nonce: Optional[str] = None) -> dict:
    path, query = split_target(target)
    ts = _now_ms() if timestamp is None else timestamp
    n = nonce or secrets.token_urlsafe(16)
    content = sha256_hex(body)
    canon = canonical_string(key_id=key_id, timestamp=ts, nonce=n, method=method, path=path,
                             query=query, content_sha256=content)
    return {
        "X-EF-Key-Id": key_id,
        "X-EF-Timestamp": str(ts),
        "X-EF-Nonce": n,
        "X-EF-Content-SHA256": content,
        "Authorization": f"{ALGORITHM} Signature={hmac_hex(secret, canon)}",
    }


class NonceCache:
    def __init__(self, ttl_ms: int = DEFAULT_SKEW_MS * 2):
        self.ttl_ms = ttl_ms
        self._d: dict[str, int] = {}
        self._lock = threading.Lock()

    def seen(self, key: str, now: int) -> bool:
        with self._lock:
            if len(self._d) % 1000 == 0:
                for k in [k for k, exp in self._d.items() if exp <= now]:
                    del self._d[k]
            exp = self._d.get(key)
            if exp and exp > now:
                return True
            self._d[key] = now + self.ttl_ms
            return False


class PskHmacVerifier:
    """lookup_key(key_id) -> {"secret": str, "principal": dict} | None"""

    name = "psk-hmac"

    def __init__(self, lookup_key: Callable[[str], Optional[dict]], skew_ms: int = DEFAULT_SKEW_MS,
                 nonce_cache: Optional[NonceCache] = None, now: Callable[[], int] = _now_ms):
        self.lookup_key = lookup_key
        self.skew_ms = skew_ms
        self.nonce_cache = nonce_cache or NonceCache()
        self.now = now

    @staticmethod
    def applies(headers: Mapping[str, str]) -> bool:
        h = {k.lower(): v for k, v in headers.items()}
        return str(h.get("authorization", "")).startswith(ALGORITHM + " ")

    def authenticate(self, *, method: str, target: str, headers: Mapping[str, str], raw_body: bytes) -> dict:
        h = {k.lower(): v for k, v in headers.items()}
        key_id = h.get("x-ef-key-id")
        nonce = h.get("x-ef-nonce")
        m = _SIG_RE.search(h.get("authorization", ""))
        try:
            ts = int(h.get("x-ef-timestamp", ""))
        except ValueError:
            ts = None
        if not key_id or not nonce or ts is None or not m:
            raise AuthError("malformed signature headers")
        if not _NONCE_RE.match(nonce):
            raise AuthError("bad nonce")
        now = self.now()
        if abs(now - ts) > self.skew_ms:
            raise AuthError("timestamp outside allowed skew")
        entry = self.lookup_key(key_id)
        if not entry:
            raise AuthError("unknown key id")
        body_hash = sha256_hex(raw_body or b"")
        if h.get("x-ef-content-sha256") and h["x-ef-content-sha256"] != body_hash:
            raise AuthError("body hash mismatch")
        path, query = split_target(target)
        canon = canonical_string(key_id=key_id, timestamp=ts, nonce=nonce, method=method, path=path,
                                 query=query, content_sha256=body_hash)
        if not hmac.compare_digest(hmac_hex(entry["secret"], canon), m.group(1)):
            raise AuthError("bad signature")
        if self.nonce_cache.seen(f"{key_id}:{nonce}", now):
            raise AuthError("replayed nonce")
        principal = dict(entry["principal"])
        principal["authn"] = {"strategy": "psk-hmac", "at": now, "keyId": key_id}
        return principal
