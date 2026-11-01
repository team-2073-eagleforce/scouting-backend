"""Scope matching. Mirrors libs/node/src/scopes.js."""
from __future__ import annotations

from .psk_hmac import ForbiddenError


def scope_matches(granted: str, required: str) -> bool:
    if granted == "*":
        return True
    g = granted.split(":")
    r = required.split(":")
    for i, seg in enumerate(g):
        last = i == len(g) - 1
        if seg == "*" and last:
            return True
        if i >= len(r):
            return False
        if seg == "*":
            continue
        if seg.endswith("*") and r[i].startswith(seg[:-1]):
            if last:
                return True
            continue
        if seg != r[i]:
            return False
    return len(g) == len(r)


def has_scope(principal: dict | None, required: str) -> bool:
    return bool(principal) and any(scope_matches(s, required) for s in principal.get("scopes", []))


def require_scope(principal: dict | None, required: str) -> None:
    if not has_scope(principal, required):
        raise ForbiddenError(f"missing scope {required}")
