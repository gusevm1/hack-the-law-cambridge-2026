"""Graph route pure-helper tests — offline, no DB.

The route's DB assembly is exercised live; here we pin the pure bits that decide
edge colour and the source link (the receipt) so they can't silently drift.
"""

from __future__ import annotations

from htl.citator.risk import polarity_label
from htl.routes.graph import _rank, _slug, _source_url


def test_polarity_matches_risk_sets() -> None:
    assert polarity_label("overruled") == "negative"
    assert polarity_label("limited") == "negative"
    assert polarity_label("followed") == "positive"
    assert polarity_label("distinguished") == "neutral"
    assert polarity_label("cited-neutral") == "neutral"
    assert polarity_label(None) == "neutral"


def test_rank_orders_negative_over_positive_over_neutral() -> None:
    assert _rank("overruled", 0.5) > _rank("followed", 0.99)
    assert _rank("followed", 0.5) > _rank("distinguished", 0.99)
    # within a polarity, higher confidence wins
    assert _rank("limited", 0.9) > _rank("limited", 0.4)


def test_slug_and_source_url() -> None:
    assert _slug("New York State Rifle & Pistol Assn., Inc. v. Bruen") == "new-york-state-rifle-pistol-assn-inc-v-bruen"
    assert _slug(None) == "case"
    url = _source_url(6480696, "Roe v. Wade")
    assert url == "https://www.courtlistener.com/opinion/6480696/roe-v-wade/"
