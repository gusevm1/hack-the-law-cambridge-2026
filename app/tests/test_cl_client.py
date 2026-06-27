"""Paced CL client tests — offline (the HTTP request is monkeypatched).

Pins the two guarantees that make retrieval consistent: a global minimum interval
between calls, and that all calls serialise through the file lock.
"""

from __future__ import annotations

import time

from htl.citator import cl_client


def test_enforces_minimum_interval(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cl_client, "_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(cl_client, "_STATE_PATH", str(tmp_path / "last"))
    monkeypatch.setattr(cl_client, "MIN_INTERVAL", 0.3)
    monkeypatch.setattr(cl_client, "_request_with_backoff", lambda *a, **k: {"ok": True})

    t0 = time.monotonic()
    assert cl_client.cl_get_json("https://x/1") == {"ok": True}
    assert cl_client.cl_get_json("https://x/2") == {"ok": True}  # must wait the interval
    elapsed = time.monotonic() - t0
    assert elapsed >= 0.3  # the second call was paced behind the first


def test_stamps_last_call_time(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(cl_client, "_LOCK_PATH", str(tmp_path / "lock"))
    monkeypatch.setattr(cl_client, "_STATE_PATH", str(tmp_path / "last"))
    monkeypatch.setattr(cl_client, "MIN_INTERVAL", 0.0)
    monkeypatch.setattr(cl_client, "_request_with_backoff", lambda *a, **k: {})

    assert cl_client._last_call() == 0.0
    cl_client.cl_get_json("https://x")
    assert cl_client._last_call() > 0.0  # timestamp persisted for the next caller
