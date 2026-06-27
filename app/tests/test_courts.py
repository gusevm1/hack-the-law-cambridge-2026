"""Court taxonomy — the shared source of truth for retrieval + triage.

Pins the apex/circuit/other buckets so the two consumers can't drift.
"""

from __future__ import annotations

from htl.citator import courts


def test_court_rank_orders_apex_circuit_other() -> None:
    assert courts.court_rank("scotus") == 0
    assert courts.court_rank("ca5") == 1
    assert courts.court_rank("cadc") == 1
    assert courts.court_rank("cafc") == 1
    assert courts.court_rank("ny") == 2
    assert courts.court_rank(None) == 2


def test_binding_only_apex_and_federal_circuit() -> None:
    assert courts.binding("scotus") == (True, 1.0)
    assert courts.binding("ca2") == (True, 0.7)
    assert courts.binding("nysd") == (False, 0.3)  # district court does not bind
    assert courts.binding("txapp") == (False, 0.3)  # state court does not bind


def test_high_courts_is_scotus_plus_thirteen_circuits() -> None:
    # scotus + ca1..ca11 + cadc + cafc = 14, all binding
    assert len(courts.HIGH_COURTS) == 14
    assert all(courts.binding(c)[0] for c in courts.HIGH_COURTS)
