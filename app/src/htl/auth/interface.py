"""The auth-verifier contract. Routes depend on ``Principal`` (our internal
identity) and never learn which verifier produced it — stub in local/CI, the
real Supabase JWT verifier in deployed envs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True)
class Principal:
    user_id: UUID  # our internal users.id, NOT the Supabase sub
    supabase_sub: str | None
    email: str | None
    is_stub: bool = False


class AuthVerifier(Protocol):
    async def verify(self, authorization: str | None) -> Principal: ...
