"""Event envelope + ULID. Mirrors libs/node/src/envelope.js."""
from __future__ import annotations

import os
import re
import time

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")
_TYPE_RE = re.compile(r"^[a-z0-9_]+(\.[a-z0-9_]+)*\.v\d+$")


def ulid(now_ms: int | None = None) -> str:
    ts = int(time.time() * 1000) if now_ms is None else now_ms
    t = ""
    for _ in range(10):
        t = _CROCKFORD[ts % 32] + t
        ts //= 32
    bits = int.from_bytes(os.urandom(10), "big")
    r = ""
    for _ in range(16):
        r = _CROCKFORD[bits & 31] + r
        bits >>= 5
    return t + r


def create_envelope(type_: str, payload, *, source: str, seq: int | None = None, event: str | None = None,
                    ts_src: int | None = None, id_: str | None = None) -> dict:
    env = {"id": id_ or ulid(), "type": type_, "source": source,
           "ts_src": int(time.time() * 1000) if ts_src is None else ts_src, "payload": payload}
    if seq is not None:
        env["seq"] = seq
    if event:
        env["event"] = event
    return env


def validate_envelope(env) -> list[str]:
    if not isinstance(env, dict):
        return ["not an object"]
    errs = []
    if not isinstance(env.get("id"), str) or not _ULID_RE.match(env["id"]):
        errs.append("id must be a ULID")
    if not isinstance(env.get("type"), str) or not _TYPE_RE.match(env["type"]):
        errs.append('type must look like "domain.name.v1"')
    if not isinstance(env.get("source"), str) or not env.get("source"):
        errs.append("source required")
    if not isinstance(env.get("ts_src"), (int, float)):
        errs.append("ts_src must be epoch ms")
    if env.get("seq") is not None and (not isinstance(env["seq"], int) or env["seq"] < 0):
        errs.append("seq must be a non-negative integer")
    if "payload" not in env:
        errs.append("payload required")
    return errs
