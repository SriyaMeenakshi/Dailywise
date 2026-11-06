from datetime import UTC, datetime, timedelta

import pytest

from app.services.priority import (
    DEFAULT_WEIGHTS,
    PriorityInput,
    blocking_factor,
    calculate,
    deadline_risk,
    level_for,
    normalize_weights,
    rating_to_score,
)

NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def make(**kw) -> PriorityInput:
    base = dict(importance=3, urgency=3, impact=3, status="not_started")
    return PriorityInput(**{**base, **kw})


def score(**kw) -> float:
    return calculate(make(**kw), now=NOW).score


def test_default_weights_match_the_spec_formula_and_sum_to_one():
    assert DEFAULT_WEIGHTS == {"importance": 0.25, "urgency": 0.20, "deadline": 0.25, "impact": 0.20, "blocking": 0.10}
    assert sum(DEFAULT_WEIGHTS.values()) == pytest.approx(1.0)


def test_ratings_normalise_to_0_100():
    assert [rating_to_score(r) for r in (1, 2, 3, 4, 5)] == [0, 25, 50, 75, 100]
    assert rating_to_score(99) == 100 and rating_to_score(-4) == 0


def test_hand_computed_score():
    # I=100 U=50 D=15 (no deadline) V=50 B=0 -> 25 + 10 + 3.75 + 10 + 0 = 48.75
    result = calculate(make(importance=5), now=NOW)
    assert result.computed == pytest.approx(48.8, abs=0.1)


def test_higher_importance_scores_higher():
    scores = [score(importance=i) for i in range(1, 6)]
    assert scores == sorted(scores) and len(set(scores)) == 5


def test_urgency_and_impact_raise_score():
    assert score(urgency=5) > score(urgency=1)
    assert score(impact=5) > score(impact=1)


def test_deadline_risk_increases_as_deadline_approaches():
    risks = [deadline_risk(NOW + timedelta(days=d), 60, NOW) for d in (30, 14, 7, 3, 1, 0.1)]
    assert risks == sorted(risks)
    assert all(0 < r < 100 for r in risks)


def test_longer_tasks_are_riskier_for_the_same_deadline():
    soon = NOW + timedelta(days=5)
    assert deadline_risk(soon, 8 * 60, NOW) > deadline_risk(soon, 15, NOW)


def test_overdue_is_maximum_risk_and_outranks_future():
    assert deadline_risk(NOW - timedelta(hours=1), None, NOW) == 100
    assert deadline_risk(NOW, None, NOW) == 100
    assert score(deadline=NOW - timedelta(days=2)) > score(deadline=NOW + timedelta(days=2))


def test_missing_deadline_is_low_but_not_zero():
    risk = deadline_risk(None, None, NOW)
    assert 0 < risk < 25
    assert score() < score(deadline=NOW + timedelta(days=1))


def test_naive_datetimes_are_treated_as_utc():
    naive = (NOW + timedelta(days=1)).replace(tzinfo=None)
    assert deadline_risk(naive, 60, NOW) == deadline_risk(NOW + timedelta(days=1), 60, NOW)


def test_blocking_factor_saturates():
    assert [blocking_factor(n) for n in (0, 1, 3, 10)] == [0, pytest.approx(33.33, abs=0.01), 100, 100]
    assert score(blocking_count=3) > score(blocking_count=0)


def test_waiting_on_dependencies_is_reported_not_penalised():
    waiting = calculate(make(waiting_on_count=2), now=NOW)
    assert waiting.score == calculate(make(), now=NOW).score
    assert "Waiting on 2 unfinished tasks" in waiting.explanation


@pytest.mark.parametrize("status", ["completed", "archived"])
def test_finished_tasks_are_not_ranked(status):
    result = calculate(make(status=status, importance=5, urgency=5, deadline=NOW - timedelta(days=1)), now=NOW)
    assert result.score == 0 and result.level == "low"
    assert status in result.explanation


def test_manual_override_wins_but_calculation_is_kept():
    result = calculate(make(importance=1, urgency=1, impact=1, override=95), now=NOW)
    assert result.score == 95 and result.level == "critical"
    assert result.computed < 30 and result.override == 95
    assert "manually" in result.explanation


def test_override_of_zero_is_respected():
    assert calculate(make(importance=5, override=0), now=NOW).score == 0


def test_factors_are_stored_and_contributions_add_up():
    result = calculate(make(importance=5, deadline=NOW + timedelta(days=2), blocking_count=1), now=NOW)
    assert [f["key"] for f in result.factors] == ["importance", "urgency", "deadline", "impact", "blocking"]
    assert sum(f["contribution"] for f in result.factors) == pytest.approx(result.computed, abs=0.3)
    assert all(0 <= f["value"] <= 100 for f in result.factors)


def test_explanation_names_the_main_drivers():
    text = calculate(make(importance=5, deadline=NOW - timedelta(days=1)), now=NOW).explanation
    assert "overdue" in text and "importance (5/5)" in text


def test_custom_weights_change_ranking_and_are_normalised():
    deadline_heavy = {"importance": 0, "urgency": 0, "deadline": 1, "impact": 0, "blocking": 0}
    near = calculate(make(importance=1, deadline=NOW + timedelta(hours=2)), deadline_heavy, NOW).score
    far_but_important = calculate(make(importance=5, deadline=NOW + timedelta(days=60)), deadline_heavy, NOW).score
    assert near > far_but_important
    scaled = normalize_weights({k: v * 10 for k, v in DEFAULT_WEIGHTS.items()})
    assert scaled == pytest.approx(DEFAULT_WEIGHTS)


@pytest.mark.parametrize(
    "bad",
    [
        {"importance": 1},
        {**DEFAULT_WEIGHTS, "importance": -1},
        {k: 0 for k in DEFAULT_WEIGHTS},
        {**DEFAULT_WEIGHTS, "mood": 1},
    ],
)
def test_invalid_weights_rejected(bad):
    with pytest.raises(ValueError):
        normalize_weights(bad)


def test_levels():
    assert [level_for(s) for s in (0, 34.9, 35, 55, 75, 100)] == ["low", "low", "medium", "high", "critical", "critical"]


def test_calculation_is_deterministic():
    item = make(importance=4, deadline=NOW + timedelta(days=3))
    assert calculate(item, now=NOW) == calculate(item, now=NOW)
