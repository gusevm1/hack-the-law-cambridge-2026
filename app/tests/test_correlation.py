"""Correlation-id middleware: mint when absent, reuse a valid inbound ULID,
replace a junk one. Uses /health so no auth or DB is involved."""

from fastapi.testclient import TestClient
from ulid import ULID

from htl.correlation import CORRELATION_ID_HEADER
from htl.main import app

client = TestClient(app)


def test_mints_correlation_id_when_absent() -> None:
    cid = client.get("/health").headers[CORRELATION_ID_HEADER]
    ULID.from_str(cid)  # raises if not a valid ULID


def test_reuses_valid_inbound_correlation_id() -> None:
    given = str(ULID())
    r = client.get("/health", headers={CORRELATION_ID_HEADER: given})
    assert r.headers[CORRELATION_ID_HEADER] == given


def test_replaces_invalid_correlation_id() -> None:
    r = client.get("/health", headers={CORRELATION_ID_HEADER: "not-a-ulid"})
    out = r.headers[CORRELATION_ID_HEADER]
    assert out != "not-a-ulid"
    ULID.from_str(out)
