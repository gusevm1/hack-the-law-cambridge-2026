"""Court taxonomy — one source of truth for apex / federal-circuit / other.

Both retrieval (ingest: fetch the binding tier in full) and triage (binding tier
in the depth score) bucket CourtListener court slugs the same way. It lived in two
places — ``ingest_citator._FED_APPELLATE`` / ``court_rank`` / ``HIGH_COURTS`` and
``triage._FED_CIRCUIT`` / ``_binding`` — so they could silently drift. Defined once
here instead.
"""

from __future__ import annotations

import re

# CourtListener slugs for federal appellate courts: the 11 numbered circuits + DC + Federal.
FED_CIRCUIT = re.compile(r"^(ca\d+|cadc|cafc)$")

# The binding tier — retrieval fetches these in full (a bounded set).
HIGH_COURTS = ["scotus", "cadc", "cafc", *(f"ca{i}" for i in range(1, 12))]

# Triage depth-score weights: apex binds hardest, then circuit, then non-binding.
_BINDING_W = {"apex": 1.0, "circuit": 0.7, "other": 0.3}


def is_federal_circuit(court: str | None) -> bool:
    return bool(court and FED_CIRCUIT.match(court))


def court_rank(court: str | None) -> int:
    """Lower is higher: SCOTUS (0) < federal appellate (1) < everything else (2).
    Retrieval uses it for fetch-priority + dedup ordering."""
    if court == "scotus":
        return 0
    if is_federal_circuit(court):
        return 1
    return 2


def binding(court: str | None) -> tuple[bool, float]:
    """Does a citing court bind a SCOTUS target? apex / federal-circuit only.
    Returns ``(is_binding, weight)`` — the weight feeds the triage depth score.

    ponytail: target assumed SCOTUS (Bruen). For a circuit/state target the binding
    set would narrow — encode per-target if we generalise past gun law.
    """
    if court == "scotus":
        return True, _BINDING_W["apex"]
    if is_federal_circuit(court):
        return True, _BINDING_W["circuit"]
    return False, _BINDING_W["other"]
