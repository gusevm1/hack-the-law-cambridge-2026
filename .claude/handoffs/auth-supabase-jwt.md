# Handoff — Supabase JWT auth (backend gate + frontend token)

**Mode line.** Next session is **executing** a well-scoped feature: add Supabase-JWT verification as a FastAPI dependency gating `POST /chat`, mirroring jobmatch-ch's verifier/stub/dependency pattern (re-derive for our stack, do **not** copy). One operator decision blocks the *real* verifier — Open question #1 (Supabase signing alg). Local dev works with the stub regardless, so most of the build is unblocked.

## State
- **Not started.** Backend has NO auth today — `/chat` is open (Cloud Run `--allow-unauthenticated` + CORS `*`).
- Seam exists: `app/src/htl/routes/` is where the dependency slots in; `settings.py` is env-driven.
- **No DB in this project** → jobmatch's "lazy user sync" step does NOT port. Principal is just `user_id` (the `sub`) + `email`.

## Reference — READ for shape, re-derive (different stack; never copy)
jobmatch-ch, `app/src/jobmatch_ch/`:
- `infrastructure/auth/interface.py` — `Principal` (frozen dataclass) + `AuthVerifier` Protocol (`async verify(authorization) -> Principal`). Keep the shape; **drop** `tier`/`credits` (no DB/tiers here) — keep `user_id`, `email`, `is_stub`.
- `infrastructure/auth/supabase_verifier.py` — the real gate: `jwt.PyJWKClient(jwks_url, cache_keys=True, lifespan=300)`, `jwt.decode(token, key.key, algorithms=["ES256"], audience, issuer, options={"require":["exp","iat","sub"]})`, JWKS fetch wrapped in `asyncio.to_thread`. Keep the bearer-parse + claim-extract helpers. **Drop** the whole `_resolve_user`/DB block.
- `infrastructure/auth/stub.py` — `StubVerifier` returns a fixed dev principal for local/test.
- `routes/dependencies.py` — `get_verifier()` (`lru_cache`) picks Supabase if config present else stub; `_resolve_user` reads the `Authorization` header; `CurrentUser = Annotated[Principal, Depends(_resolve_user)]`. Tests override via `app.dependency_overrides[get_verifier]`.

## Plan (our repo, package `htl`)
1. `app/pyproject.toml`: add `pyjwt[crypto]>=2.9,<3.0`; `uv lock`.
2. `app/src/htl/auth/`: `interface.py` (Principal+Protocol), `supabase.py` (SupabaseVerifier), `stub.py` (StubVerifier).
3. `app/src/htl/routes/dependencies.py`: `get_verifier` + `CurrentUser`.
4. `settings.py`: add `supabase_jwks_url`, `supabase_issuer`, `supabase_audience = "authenticated"`.
5. `routes/chat.py`: add `user: CurrentUser` to gate `/chat`; leave `/health` open.
6. Tests: (a) stub-override → authed 200; (b) real verifier with a locally-minted ES256 key injected as the `SigningKeyResolver` (no network) → 401 on bad/expired/wrong-aud.
7. Frontend companion: `@supabase/supabase-js` client + a sign-in, then attach `Authorization: Bearer ${session.access_token}` in `frontend/lib/api.ts`. Env `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`.

## Carry-over notes
- **New Supabase project per hackathon** (operator preference). Record: project ref, JWKS URL = `https://<ref>.supabase.co/auth/v1/.well-known/jwks.json`, issuer = `https://<ref>.supabase.co/auth/v1`, audience = `authenticated`, anon key (frontend).
- Read entitlement-type claims ONLY from `app_metadata` (server-trusted), never `user_metadata` (user-writable) — keep the habit even without tiers.
- Keep `is_stub` on Principal so stub vs real sessions are identifiable.
- CORS already allows the `Authorization` header (`allow_headers=["*"]`); keep it allowed if origins get locked down later.
- Config-presence swap (stub when no Supabase env) keeps `just dev-api` + CI offline — don't gate local dev behind a live Supabase.

## Open questions / operator decisions
1. **[BLOCKS the real verifier]** Which signing alg does the new Supabase project use? Modern: asymmetric **ES256/RS256 + JWKS** (use `PyJWKClient`, what jobmatch does — set `algorithms` to match). Legacy: **HS256 shared secret** (no JWKS — verify with the project's JWT secret). Check Supabase dashboard → JWT keys, then pick the decode path. Local/stub work is NOT blocked.
2. Frontend sign-in: email magic-link (zero extra config) vs Google OAuth (needs a provider configured in Supabase). Pick per demo.
3. Hard-gate `/chat` (401 without token) vs allow-anonymous-with-principal. **Default: hard-gate `/chat`.**

## First moves
1. Create the new Supabase project; record JWKS URL / issuer / audience / anon key (Carry-over).
2. `git switch -c feat/auth-supabase-jwt origin/main`; ride `ship-feature`.
3. Read the four reference files for shape; build `htl/auth/` + `routes/dependencies.py` (no DB).
4. Wire `CurrentUser` into `/chat`; write the stub-override + ES256 unit tests; `just lint && just test`.

## Teardown
Delete this handoff (move to `.claude/handoffs/archive/`) when auth ships.
