"""Pairing secrets. Mirrors libs/node/src/pairing.js."""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets

ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
_KDF_LABEL = b"ef-pairing-v1"


def _rand(n: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(n))


def _group(s: str, size: int) -> str:
    return "-".join(s[i:i + size] for i in range(0, len(s), size))


def generate_pairing_secret(fmt: str = "long", gateway_name: str = "", secret: str | None = None) -> dict:
    if fmt == "short":
        s = _rand(8)
        return {"format": fmt, "secret": s, "display": _group(s, 4)}
    if fmt == "long":
        s = _rand(26)
        return {"format": fmt, "secret": "EF1" + s, "display": "ef1-" + _group(s, 5).lower()}
    if fmt == "qr":
        inner = {"secret": secret, "display": secret} if secret else generate_pairing_secret("long")
        payload = json.dumps({"v": 1, "t": "ef-pair", "s": inner["secret"], "n": gateway_name}, separators=(",", ":"))
        return {"format": fmt, "secret": inner["secret"], "display": inner["display"], "qrPayload": payload}
    raise ValueError(f"unknown pairing format: {fmt}")


def normalize_pairing_secret(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("pairing secret must be a string")
    s = value.strip()
    if s.startswith("{"):
        obj = json.loads(s)
        if obj.get("t") != "ef-pair" or not isinstance(obj.get("s"), str):
            raise ValueError("not an ef-pair QR payload")
        s = obj["s"]
    s = s.upper().replace(" ", "").replace("-", "").replace("\t", "").replace("\n", "")
    if s.startswith("EF1"):
        s = s[3:]
    if len(s) < 6:
        raise ValueError("pairing secret too short")
    # Generated secrets use the unambiguous ALPHABET; custom typed secrets may use any A-Z / 0-9.
    if not s.isascii() or not s.isalnum():
        raise ValueError("pairing secret may only contain letters, digits, spaces and dashes")
    return s


def derive_pairing_key(value: str) -> bytes:
    return hmac.new(_KDF_LABEL, normalize_pairing_secret(value).encode("utf-8"), hashlib.sha256).digest()


def _proof(key: bytes, role: str, g: str, c: str, d: str) -> str:
    return hmac.new(key, f"ef-pair-{role}\n{g}\n{c}\n{d}".encode("utf-8"), hashlib.sha256).hexdigest()


def client_proof(key: bytes, gateway_nonce: str, client_nonce: str, device_id: str) -> str:
    return _proof(key, "client", gateway_nonce, client_nonce, device_id)


def server_proof(key: bytes, gateway_nonce: str, client_nonce: str, device_id: str) -> str:
    return _proof(key, "server", gateway_nonce, client_nonce, device_id)
