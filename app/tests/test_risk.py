"""Risk aggregation unit tests — pure, offline (no LLM, no DB).

Exercises ``aggregate_risk`` directly with synthetic treatments to pin the
verdict logic: a strong negative → red, mild criticism diluted by neutral cites →
green, moderate criticism → amber, trend grouping, ground-truth lookup, and the
no-data path.
"""

from __future__ import annotations

from datetime import date

from htl.citator.risk import CitingTreatment, aggregate_risk

TODAY = date(2026, 6, 27)
ROE = {"case_id": 108713, "case_name": "Roe v. Wade", "citation": "410 U.S. 113",
       "court": "scotus", "date_filed": date(1973, 1, 22)}
UNLISTED = {"case_id": 999, "case_name": "Some Case", "citation": "1 U.S. 1",
            "court": "scotus", "date_filed": date(1900, 1, 1)}


def _t(type_, court="scotus", conf=0.9, year=2022, scope="whole-case",
       name="Citing Co.", ground=False, quote="q") -> CitingTreatment:
    return CitingTreatment(
        type=type_, scope=scope, on_other_grounds=ground, quote=quote, confidence=conf,
        citing_case_name=name, citing_court=court, citing_date_filed=date(year, 1, 1),
    )


def test_strong_negative_high_court_is_red() -> None:
    r = aggregate_risk(ROE, [_t("overruled", court="scotus", conf=0.9)], total_citing=1, today=TODAY)
    assert r.signal == "red"
    assert r.status == "overruled"
    assert r.risk_score == 1.0
    # ground truth is wired for Roe → rationale names the overruling case
    assert r.ground_truth.on_loc_overruled_list is True
    assert r.ground_truth.overruled_by == "Dobbs v. Jackson (2022)"
    assert "Dobbs" in r.risk_rationale
    assert r.negative_treatments[0].type == "overruled"


def test_circuit_overruled_also_red() -> None:
    # a ca5 panel reporting the overruling still trips the dispositive path (weight 0.6)
    r = aggregate_risk(ROE, [_t("overruled", court="ca5", conf=0.95)], total_citing=1, today=TODAY)
    assert r.signal == "red" and r.risk_score == 1.0


def test_strong_negative_low_court_or_low_conf_not_dispositive() -> None:
    # state court (weight 0.3) abrogated → not the dispositive red path…
    r = aggregate_risk(UNLISTED, [_t("abrogated", court="ny", conf=0.9)], total_citing=1, today=TODAY)
    assert r.signal != "red"
    # …but still a negative treatment surfaced
    assert r.negative_treatments and r.negative_treatments[0].type == "abrogated"


def test_mild_criticism_diluted_by_neutral_is_green() -> None:
    treatments = [_t("criticised", court="ny", conf=0.6, year=2020)] + [
        _t("cited-neutral", court="ny", conf=0.9, year=2021) for _ in range(4)
    ]
    r = aggregate_risk(UNLISTED, treatments, total_citing=5, today=TODAY)
    assert r.signal == "green"
    assert r.status == "good"
    assert r.risk_score <= 0.4


def test_moderate_criticism_is_amber() -> None:
    treatments = [
        _t("criticised", court="scotus", conf=0.8, year=2021),
        _t("criticised", court="scotus", conf=0.8, year=2021),
        _t("followed", court="ny", conf=0.8, year=2021),
    ]
    r = aggregate_risk(UNLISTED, treatments, total_citing=3, today=TODAY)
    assert r.signal == "amber"
    assert r.status == "good-but-eroding"
    assert 0.4 < r.risk_score < 1.0


def test_distinguished_is_neutral_not_negative() -> None:
    r = aggregate_risk(UNLISTED, [_t("distinguished", court="scotus", conf=0.9)],
                       total_citing=1, today=TODAY)
    assert r.negative_treatments == []
    assert r.signal == "green"


def test_trend_groups_by_year() -> None:
    treatments = [
        _t("criticised", year=1990),
        _t("followed", year=2000),
        _t("criticised", year=2000),
        _t("distinguished", year=2005),  # neutral → omitted from trend
        _t("overruled", year=2022, court="ny", conf=0.5),  # neg, but not dispositive
    ]
    r = aggregate_risk(UNLISTED, treatments, total_citing=5, today=TODAY)
    years = [p.year for p in r.trend]
    assert years == [1990, 2000, 2022]  # sorted, neutral-only 2005 dropped
    p2000 = next(p for p in r.trend if p.year == 2000)
    assert (p2000.neg, p2000.pos) == (1, 1)
    assert p2000.neg_share == 0.5


def test_positive_signal_counts() -> None:
    treatments = [
        _t("followed", court="ny", conf=0.8),
        _t("followed", court="ny", conf=0.8),
        _t("cited-neutral", court="ny", conf=0.8),
    ]
    r = aggregate_risk(UNLISTED, treatments, total_citing=40, today=TODAY)
    assert r.positive_signal.approving_cites == 2
    assert r.positive_signal.total_citing == 40


def test_no_treatments_is_unknown() -> None:
    r = aggregate_risk(UNLISTED, [], total_citing=0, today=TODAY)
    assert r.signal == "unknown"
    assert r.status == "unknown"
    assert r.risk_score == 0.0
    assert r.trend == []
    assert r.ground_truth.on_loc_overruled_list is False
    assert r.ground_truth.overruled_by is None
    assert r.as_of == "2026-06-27"
