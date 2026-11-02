"""Password hashing (scrypt) and stateless signed session tokens (HMAC-SHA256).

Tokens carry the user ID and an expiry only; roles and tenant are re-read from the DB on every
request, so disabling a user or changing roles takes effect immediately.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time

_N, _R, _P = 2**14, 8, 1


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def hash_password(password: str) -> str:
    if len(password) < 8:
        raise ValueError("Password must have at least 8 characters")
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, expected = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode(), salt=_unb64(salt), n=int(n), r=int(r), p=int(p), dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, _unb64(expected))


class SessionSigner:
    def __init__(self, secret: str, ttl_seconds: int):
        if len(secret) < 32:
            raise ValueError("AUTH_SECRET must have at least 32 characters")
        self._key = secret.encode()
        self.ttl_seconds = ttl_seconds

    def _sign(self, body: str) -> str:
        return _b64(hmac.new(self._key, body.encode(), hashlib.sha256).digest())

    def issue(self, user_id: str, now: float | None = None) -> str:
        expires = int((now if now is not None else time.time()) + self.ttl_seconds)
        body = _b64(json.dumps({"sub": user_id, "exp": expires}, separators=(",", ":")).encode())
        return f"{body}.{self._sign(body)}"

    def verify(self, token: str, now: float | None = None) -> str | None:
        """The user ID of a valid, unexpired token; None otherwise."""
        body, _, signature = token.partition(".")
        if not body or not hmac.compare_digest(signature, self._sign(body)):
            return None
        try:
            claims = json.loads(_unb64(body))
        except ValueError:
            return None
        if claims.get("exp", 0) < (now if now is not None else time.time()):
            return None
        return claims.get("sub") if isinstance(claims.get("sub"), str) else None
