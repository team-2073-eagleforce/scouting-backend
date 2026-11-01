"""EF1-HMAC-SHA256 canonical request. Byte-identical to libs/node/src/canonical.js."""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import unquote

ALGORITHM = "EF1-HMAC-SHA256"
_UNRESERVED = set(b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.~")


def sha256_hex(data: bytes | str | None) -> str:
    if data is None:
        data = b""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _rfc3986(s: str) -> str:
    return "".join(chr(b) if b in _UNRESERVED else "%%%02X" % b for b in s.encode("utf-8"))


def _decode(s: str) -> str:
    try:
        return unquote(s.replace("+", "%20"), errors="strict")
    except UnicodeDecodeError:
        return s


def canonical_query(raw: str | None) -> str:
    if not raw:
        return ""
    q = raw[1:] if raw.startswith("?") else raw
    pairs = []
    for part in filter(None, q.split("&")):
        name, sep, value = part.partition("=")
        pairs.append((_decode(name), _decode(value if sep else "")))
    pairs.sort(key=lambda p: (p[0].encode("utf-8"), p[1].encode("utf-8")))
    return "&".join(f"{_rfc3986(n)}={_rfc3986(v)}" for n, v in pairs)


def split_target(target: str) -> tuple[str, str]:
    path, _, query = target.partition("?")
    return path, query


def canonical_string(*, key_id: str, timestamp: int | str, nonce: str, method: str, path: str,
                     query: str, content_sha256: str) -> str:
    return "\n".join([
        ALGORITHM, key_id, str(timestamp), nonce, method.upper(), path,
        canonical_query(query or ""), content_sha256,
    ])


def hmac_hex(secret: str, msg: str) -> str:
    return hmac.new(secret.encode("utf-8"), msg.encode("utf-8"), hashlib.sha256).hexdigest()
