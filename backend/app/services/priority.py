"""Deterministic priority engine. Pure functions: no database, no network, no AI.

    P = wI*I + wU*U + wD*D + wV*V + wB*B        (every factor normalised to 0-100)

I importance, U urgency, V expected impact: the 1-5 rating mapped linearly to 0-100.
D deadline risk: 100 when due/overdue, decaying with the time left relative to the effort needed.
B blocking factor: how many unfinished tasks are waiting on this one.
"""

from dataclasses import dataclass
from datetime import UTC, datetime

FACTOR_KEYS = ("importance", "urgency", "deadline", "impact", "blocking")
FACTOR_LABELS = {
    "importance": "Importance",
    "urgency": "Urgency",
    "deadline": "Deadline risk",
    "impact": "Expected impact",
    "blocking": "Blocks other tasks",
}
DEFAULT_WEIGHTS: dict[str, float] = {
    "importance": 0.25,
    "urgency": 0.20,
    "deadline": 0.25,
    "impact": 0.20,
    "blocking": 0.10,
}

INACTIVE_STATUSES = frozenset({"completed", "archived"})
NO_DEADLINE_RISK = 15.0  # a task with no deadline is rarely urgent, but never zero
DEFAULT_EFFORT_MINUTES = 60
WORKDAY_MINUTES = 480
BLOCKING_SATURATION = 3  # this many waiting tasks = maximum blocking factor


def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
    """Validate and scale weights so they sum to 1. Raises ValueError on bad input."""
    if not weights:
        return dict(DEFAULT_WEIGHTS)
    if set(weights) != set(FACTOR_KEYS):
        raise ValueError(f"weights must contain exactly: {', '.join(FACTOR_KEYS)}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("weights cannot be negative")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("at least one weight must be greater than zero")
    return {k: weights[k] / total for k in FACTOR_KEYS}


def rating_to_score(rating: int) -> float:
    """1..5 -> 0..100."""
    return (min(max(rating, 1), 5) - 1) / 4 * 100


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def deadline_risk(deadline: datetime | None, estimated_minutes: int | None, now: datetime) -> float:
    if deadline is None:
        return NO_DEADLINE_RISK
    days_left = (_aware(deadline) - _aware(now)).total_seconds() / 86_400
    if days_left <= 0:
        return 100.0
    effort_days = (estimated_minutes or DEFAULT_EFFORT_MINUTES) / WORKDAY_MINUTES
    # 100 at the deadline; halves when the time left equals (3 days + the task's own effort).
    return 100.0 / (1.0 + days_left / (3.0 + effort_days))


def blocking_factor(waiting_count: int) -> float:
    return min(100.0, 100.0 * max(waiting_count, 0) / BLOCKING_SATURATION)


def level_for(score: float) -> str:
    if score >= 75:
        return "critical"
    if score >= 55:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


@dataclass(frozen=True)
class PriorityInput:
    importance: int
    urgency: int
    impact: int
    status: str
    deadline: datetime | None = None
    estimated_minutes: int | None = None
    blocking_count: int = 0  # unfinished tasks that depend on this one
    waiting_on_count: int = 0  # unfinished tasks this one depends on
    override: int | None = None


@dataclass(frozen=True)
class PriorityResult:
    score: float  # effective: the override when set, otherwise `computed`
    computed: float
    override: int | None
    level: str
    factors: list[dict]
    explanation: str


def _deadline_note(deadline: datetime | None, now: datetime) -> str:
    if deadline is None:
        return "no deadline"
    days = (_aware(deadline) - _aware(now)).total_seconds() / 86_400
    if days <= 0:
        return "overdue"
    if days < 1:
        return "due within a day"
    return f"due in {round(days)} day{'s' if round(days) != 1 else ''}"


def calculate(
    item: PriorityInput, weights: dict[str, float] | None = None, now: datetime | None = None
) -> PriorityResult:
    now = now or datetime.now(UTC)
    w = normalize_weights(weights)

    if item.status in INACTIVE_STATUSES:
        factors = [
            {"key": k, "label": FACTOR_LABELS[k], "value": 0.0, "weight": w[k], "contribution": 0.0}
            for k in FACTOR_KEYS
        ]
        return PriorityResult(0.0, 0.0, None, "low", factors, f"This task is {item.status}, so it is not ranked.")

    values = {
        "importance": rating_to_score(item.importance),
        "urgency": rating_to_score(item.urgency),
        "deadline": deadline_risk(item.deadline, item.estimated_minutes, now),
        "impact": rating_to_score(item.impact),
        "blocking": blocking_factor(item.blocking_count),
    }
    factors = [
        {
            "key": k,
            "label": FACTOR_LABELS[k],
            "value": round(values[k], 1),
            "weight": round(w[k], 4),
            "contribution": round(values[k] * w[k], 1),
        }
        for k in FACTOR_KEYS
    ]
    computed = round(sum(values[k] * w[k] for k in FACTOR_KEYS), 1)

    top = sorted(factors, key=lambda f: f["contribution"], reverse=True)[:2]
    notes = {
        "deadline": _deadline_note(item.deadline, now),
        "importance": f"{item.importance}/5",
        "urgency": f"{item.urgency}/5",
        "impact": f"{item.impact}/5",
        "blocking": f"{item.blocking_count} waiting",
    }
    drivers = " and ".join(f"{f['label'].lower()} ({notes[f['key']]})" for f in top if f["contribution"] > 0)
    parts = [f"Score {computed:g}, {level_for(computed)}."]
    if drivers:
        parts.append(f"Mostly driven by {drivers}.")
    if item.waiting_on_count:
        n = item.waiting_on_count
        parts.append(f"Waiting on {n} unfinished {'task' if n == 1 else 'tasks'}.")

    score = float(item.override) if item.override is not None else computed
    if item.override is not None:
        parts.append(f"You set this manually to {item.override}; the calculated score is {computed:g}.")
    return PriorityResult(score, computed, item.override, level_for(score), factors, " ".join(parts))
