"""Supabase JWT verifier — the real access gate.

Verifies each access token's signature against Supabase's JWKS (asymmetric
ES256) plus issuer / audience / expiry, then maps the verified ``sub`` to our
``users`` row (lazy-create on first sight). Returns a provider-agnostic
``Principal``. Any verification failure — missing/garbled header, bad signature,
wrong issuer/audience, expired, missing required claim, JWKS lookup failure —
raises ``Unauthorized`` (401). It never decodes without verifying.

The JWKS fetch is the one piece of blocking I/O (PyJWT's ``PyJWKClient`` uses
urllib + caches keys, refetching on an unknown ``kid``), so we run it in a
thread to keep the event loop free.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, Protocol

import jwt

from htl.auth.interface import AuthVerifier, Principal
from htl.db import repositories
from htl.errors import Unauthorized
from htl.settings import Settings

_ALGORITHMS = ["ES256"]
# Supabase mints short-lived (~1h) access tokens and rarely rotates the JWKS, so
# a 5-minute key cache is plenty and bounds staleness on rotation.
_JWKS_LIFESPAN_SECONDS = 300
_JWKS_FETCH_TIMEOUT_SECONDS = 10


class SigningKeyResolver(Protocol):
    """The slice of ``jwt.PyJWKClient`` the verifier needs. A Protocol so tests
    inject a local public key with no network round-trip; a real ``PyJWKClient``
    satisfies it structurally."""

    def get_signing_key_from_jwt(self, token: str) -> Any: ...


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise Unauthorized("missing Authorization header")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise Unauthorized("Authorization header is not a Bearer token")
    return token.strip()


def _extract_sub(claims: dict[str, Any]) -> str:
    sub = claims.get("sub")
    if not isinstance(sub, str) or not sub:
        raise Unauthorized("token has no usable 'sub' claim")
    return sub


class SupabaseVerifier(AuthVerifier):
    def __init__(
        self,
        *,
        issuer: str,
        audience: str,
        signing_key_resolver: SigningKeyResolver,
        session_factory: Callable[[], Any],
    ) -> None:
        self._issuer = issuer
        self._audience = audience
        self._keys = signing_key_resolver
        self._session_factory = session_factory

    @classmethod
    def build_from_settings(
        cls, settings: Settings, session_factory: Callable[[], Any]
    ) -> SupabaseVerifier:
        """Construct from config. Fails fast — rather than booting a gate that
        401s every request — if the JWKS URL / issuer aren't both wired."""
        if not settings.supabase_jwks_url or not settings.supabase_issuer:
            raise RuntimeError(
                "SupabaseVerifier requires supabase_jwks_url and supabase_issuer."
            )
        jwk_client = jwt.PyJWKClient(
            settings.supabase_jwks_url,
            cache_keys=True,
            lifespan=_JWKS_LIFESPAN_SECONDS,
            timeout=_JWKS_FETCH_TIMEOUT_SECONDS,
        )
        return cls(
            issuer=settings.supabase_issuer,
            audience=settings.supabase_audience,
            signing_key_resolver=jwk_client,
            session_factory=session_factory,
        )

    async def verify(self, authorization: str | None) -> Principal:
        token = _bearer_token(authorization)
        claims = await self._decode(token)
        sub = _extract_sub(claims)
        email = claims.get("email") if isinstance(claims.get("email"), str) else None
        user_id = await self._resolve_user_id(sub=sub, email=email)
        return Principal(user_id=user_id, supabase_sub=sub, email=email, is_stub=False)

    async def _decode(self, token: str) -> dict[str, Any]:
        try:
            # PyJWKClientError is a PyJWTError subclass, so one except covers
            # both the JWKS lookup and the signature/claim validation.
            signing_key = await asyncio.to_thread(self._keys.get_signing_key_from_jwt, token)
            claims: dict[str, Any] = jwt.decode(
                token,
                signing_key.key,
                algorithms=_ALGORITHMS,
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
            return claims
        except jwt.PyJWTError as exc:
            raise Unauthorized(f"JWT verification failed: {type(exc).__name__}") from exc

    async def _resolve_user_id(self, *, sub: str, email: str | None) -> Any:
        """Lazy user sync: get-or-create our ``users`` row for this Supabase
        ``sub`` and return our internal ``users.id`` (the FK messages use)."""
        async with self._session_factory() as session:
            user = await repositories.get_or_create_user(session, supabase_sub=sub, email=email)
            await session.commit()
            return user.id
