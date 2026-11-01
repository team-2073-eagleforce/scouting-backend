"""EagleForce platform-kit (Python). Mirrors libs/node; see platform-kit/auth/SPEC.md.

Standard library only, so it can be vendored into Django, FastAPI, and scripts without new deps.
"""
from .canonical import ALGORITHM, sha256_hex, canonical_query, canonical_string, split_target, hmac_hex
from .psk_hmac import AuthError, ForbiddenError, NonceCache, sign_request, PskHmacVerifier
from .pairing import (
    ALPHABET, generate_pairing_secret, normalize_pairing_secret, derive_pairing_key,
    client_proof, server_proof,
)
from .scopes import scope_matches, has_scope, require_scope
from .envelope import ulid, create_envelope, validate_envelope

__version__ = "0.1.0"
__all__ = [n for n in dir() if not n.startswith("_")]
