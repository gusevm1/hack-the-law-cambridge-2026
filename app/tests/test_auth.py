"""Supabase verifier unit tests — offline.

Mints real ES256 tokens against a local EC keypair and injects a fake signing-key
resolver (no network). The accept path's DB write is stubbed (get_or_create_user
patched), so no Postgres is needed; the reject paths use a poison factory to
prove the gate rejects *before* any DB work.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec

from htl.auth.supabase import SupabaseVerifier, _extract_sub
from htl.db import repositories
from htl.errors import Unauthorized
from htl.settings import Settings

ISSUER = "https://test.supabase.co/auth/v1"
AUDIENCE = "authenticated"


@dataclass
class _FakeKey:
    key: Any


class _StaticResolver:
    def __init__(self, public_key: Any) -> None:
        self._pub = public_key

    def get_signing_key_from_jwt(self, token: str) -> _FakeKey:
        return _FakeKey(key=self._pub)


class _RaisingResolver:
    def get_signing_key_from_jwt(self, token: str) -> _FakeKey:
        raise jwt.PyJWKClientError("no signing key for kid")


class _FakeSession:
    async def commit(self) -> None:
        pass


@asynccontextmanager
async def _fake_session_cm() -> AsyncIterator[_FakeSession]:
    yield _FakeSession()


def _poison_factory() -> Any:
    raise AssertionError("session factory must not be touched when the token is rejected")


@pytest.fixture(scope="module")
def keypair() -> tuple[Any, Any]:
    priv = ec.generate_private_key(ec.SECP256R1())
    return priv, priv.public_key()


def _mint(
    priv: Any,
    *,
    sub: str | None = None,
    email: str | None = "user@example.com",
    iss: str = ISSUER,
    aud: str = AUDIENCE,
    exp_delta: int = 3600,
    include_iat: bool = True,
) -> str:
    now = datetime.now(tz=UTC)
    payload: dict[str, Any] = {
        "sub": sub if sub is not None else str(uuid.uuid4()),
        "iss": iss,
        "aud": aud,
        "exp": now + timedelta(seconds=exp_delta),
    }
    if email is not None:
        payload["email"] = email
    if include_iat:
        payload["iat"] = now
    return jwt.encode(payload, priv, algorithm="ES256")


def _verifier(public_key: Any, factory: Any) -> SupabaseVerifier:
    return SupabaseVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_key_resolver=_StaticResolver(public_key),
        session_factory=factory,
    )


# --- Accept -----------------------------------------------------------------


async def test_valid_token_accepted_and_maps_to_our_user(
    keypair: tuple[Any, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    priv, pub = keypair
    sub = str(uuid.uuid4())
    uid = uuid.uuid4()

    async def fake_goc(session: Any, *, supabase_sub: str, email: str | None) -> Any:
        assert supabase_sub == sub
        return SimpleNamespace(id=uid)

    monkeypatch.setattr(repositories, "get_or_create_user", fake_goc)

    token = _mint(priv, sub=sub, email="alice@htl.test")
    principal = await _verifier(pub, _fake_session_cm).verify(f"Bearer {token}")

    assert principal.is_stub is False
    assert principal.user_id == uid  # our internal id, not the Supabase sub
    assert principal.supabase_sub == sub
    assert principal.email == "alice@htl.test"


# --- Reject (no DB touch) ---------------------------------------------------


async def test_missing_authorization_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    _, pub = keypair
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(None)


async def test_non_bearer_and_empty_token_are_unauthorized(keypair: tuple[Any, Any]) -> None:
    _, pub = keypair
    v = _verifier(pub, _poison_factory)
    with pytest.raises(Unauthorized):
        await v.verify("Basic dXNlcjpwYXNz")
    with pytest.raises(Unauthorized):
        await v.verify("Bearer ")


async def test_expired_token_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    priv, pub = keypair
    token = _mint(priv, exp_delta=-10)
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(f"Bearer {token}")


async def test_missing_iat_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    priv, pub = keypair
    token = _mint(priv, include_iat=False)
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(f"Bearer {token}")


async def test_wrong_issuer_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    priv, pub = keypair
    token = _mint(priv, iss="https://evil.example/auth/v1")
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(f"Bearer {token}")


async def test_wrong_audience_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    priv, pub = keypair
    token = _mint(priv, aud="anon")
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(f"Bearer {token}")


async def test_tampered_signature_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    _, pub = keypair
    attacker = ec.generate_private_key(ec.SECP256R1())
    token = _mint(attacker)  # well-formed, signed by the wrong key
    with pytest.raises(Unauthorized):
        await _verifier(pub, _poison_factory).verify(f"Bearer {token}")


async def test_jwks_lookup_failure_is_unauthorized(keypair: tuple[Any, Any]) -> None:
    priv, _ = keypair
    token = _mint(priv)
    v = SupabaseVerifier(
        issuer=ISSUER,
        audience=AUDIENCE,
        signing_key_resolver=_RaisingResolver(),
        session_factory=_poison_factory,
    )
    with pytest.raises(Unauthorized):
        await v.verify(f"Bearer {token}")


def test_extract_sub_rejects_missing_or_non_string() -> None:
    with pytest.raises(Unauthorized):
        _extract_sub({})
    with pytest.raises(Unauthorized):
        _extract_sub({"sub": 12345})
    assert _extract_sub({"sub": "abc"}) == "abc"


# --- build_from_settings ----------------------------------------------------


def test_build_from_settings_raises_without_config() -> None:
    with pytest.raises(RuntimeError):
        SupabaseVerifier.build_from_settings(Settings(), _poison_factory)


def test_build_from_settings_constructs_when_configured() -> None:
    settings = Settings(
        supabase_jwks_url="https://x.supabase.co/auth/v1/.well-known/jwks.json",
        supabase_issuer="https://x.supabase.co/auth/v1",
    )
    assert isinstance(
        SupabaseVerifier.build_from_settings(settings, _poison_factory), SupabaseVerifier
    )
