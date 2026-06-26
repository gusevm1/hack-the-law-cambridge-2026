"""Dev/CI stub verifier: returns a fixed principal regardless of the request.

Used locally and in tests so neither needs a live Supabase. The fixed user id
is seeded by Alembic 0001, so message FKs resolve when the stub runs against a
real database. ``get_verifier`` (routes/dependencies) selects this whenever the
Supabase JWKS/issuer settings are absent.
"""

from __future__ import annotations

from uuid import UUID

from htl.auth.interface import AuthVerifier, Principal

STUB_USER_ID = UUID("00000000-0000-0000-0000-000000000001")

STUB_PRINCIPAL = Principal(
    user_id=STUB_USER_ID,
    supabase_sub=None,
    email="dev@htl.local",
    is_stub=True,
)


class StubVerifier(AuthVerifier):
    async def verify(self, authorization: str | None) -> Principal:
        return STUB_PRINCIPAL


STUB_VERIFIER = StubVerifier()
