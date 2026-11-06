"""Daily reflection facts and analytics. Everything here is computed from the user's own tasks:
no sampled, estimated or placeholder numbers, so an empty account shows empty charts."""

import uuid
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Category, DailyReview, Project, Task
from app.schemas.insights import (
    Analytics,
    CategoryProgress,
    DayPoint,
    ProjectBrief,
    ReviewFacts,
    ReviewRead,
    ReviewText,
    TaskBrief,
    TimeAccuracy,
)
from app.services import priority_store, projects
from app.services.priority import level_for

ACTIVE = ("inbox", "not_started", "in_progress", "blocked")
TOP_TOMORROW = 5


def _aware(value: datetime | None) -> datetime | None:
    return value if value is None or value.tzinfo else value.replace(tzinfo=UTC)


def day_bounds(day: date, offset_minutes: int) -> tuple[datetime, datetime]:
    """UTC instants for the start and end of a *local* calendar day (local = UTC + offset)."""
    start = datetime(day.year, day.month, day.day, tzinfo=UTC) - timedelta(minutes=offset_minutes)
    return start, start + timedelta(days=1)


def local_today(offset_minutes: int, now: datetime | None = None) -> date:
    return ((now or datetime.now(UTC)) + timedelta(minutes=offset_minutes)).date()


def _brief(t: Task) -> TaskBrief:
    return TaskBrief(
        id=t.id, title=t.title, deadline=_aware(t.deadline), estimated_minutes=t.estimated_minutes,
        actual_minutes=t.actual_minutes, priority_level=level_for(t.priority_score),
    )


# ── daily reflection ────────────────────────────────────────────────────────────
def get_review(db: Session, user_id: uuid.UUID, day: date, offset_minutes: int) -> ReviewRead:
    priority_store.recompute_all(db, user_id)  # so "tomorrow" suggestions reflect the clock
    start, end = day_bounds(day, offset_minutes)
    tasks = list(db.scalars(select(Task).where(Task.user_id == user_id, Task.status != "archived")))

    def done_today(t: Task) -> bool:
        c = _aware(t.completed_at)
        return t.status == "completed" and c is not None and start <= c < end

    completed = [t for t in tasks if done_today(t)]
    active = [t for t in tasks if t.status in ACTIVE]
    due = [t for t in active if t.status != "blocked" and t.deadline and _aware(t.deadline) < end]
    ranked = sorted((t for t in active if t.status != "blocked"), key=lambda t: (-t.priority_score, t.created_at))

    row = db.scalar(select(DailyReview).where(DailyReview.user_id == user_id, DailyReview.review_date == day))
    saved = None
    if row:
        saved = ReviewText(
            accomplished=row.accomplished or "", remaining=row.remaining or "",
            blockers=row.blockers or "", tomorrow_focus=row.tomorrow_focus or "",
        )
    return ReviewRead(
        date=day,
        saved=saved,
        facts=ReviewFacts(
            completed=[_brief(t) for t in sorted(completed, key=lambda t: _aware(t.completed_at))],
            completed_minutes=sum((t.actual_minutes if t.actual_minutes is not None else t.estimated_minutes) or 0 for t in completed),
            remaining=[_brief(t) for t in sorted(due, key=lambda t: _aware(t.deadline))],
            blocked=[_brief(t) for t in active if t.status == "blocked"],
            suggested_tomorrow=[_brief(t) for t in ranked[:TOP_TOMORROW]],
        ),
    )


def save_review(db: Session, user_id: uuid.UUID, day: date, text: ReviewText) -> None:
    row = db.scalar(select(DailyReview).where(DailyReview.user_id == user_id, DailyReview.review_date == day))
    if row is None:
        row = DailyReview(user_id=user_id, review_date=day)
        db.add(row)
    row.accomplished, row.remaining, row.blockers, row.tomorrow_focus = (
        text.accomplished.strip() or None, text.remaining.strip() or None,
        text.blockers.strip() or None, text.tomorrow_focus.strip() or None,
    )
    db.commit()


# ── analytics ───────────────────────────────────────────────────────────────────
def analytics(db: Session, user_id: uuid.UUID, days: int, offset_minutes: int, now: datetime | None = None) -> Analytics:
    now = now or datetime.now(UTC)
    today = local_today(offset_minutes, now)
    first_day = today - timedelta(days=days - 1)
    window_start, _ = day_bounds(first_day, offset_minutes)
    _, window_end = day_bounds(today, offset_minutes)

    tasks = list(db.scalars(select(Task).where(Task.user_id == user_id, Task.status != "archived")))
    done = [t for t in tasks if t.status == "completed" and (c := _aware(t.completed_at)) and window_start <= c < window_end]
    active = [t for t in tasks if t.status in ACTIVE]

    per_day: dict[date, list[Task]] = defaultdict(list)
    for t in done:
        per_day[(_aware(t.completed_at) + timedelta(minutes=offset_minutes)).date()].append(t)
    daily = [
        DayPoint(
            date=d, completed=len(per_day[d]),
            completed_minutes=sum((t.actual_minutes if t.actual_minutes is not None else t.estimated_minutes) or 0 for t in per_day[d]),
        )
        for d in (first_day + timedelta(days=i) for i in range(days))
    ]

    with_deadline = [t for t in done if t.deadline]
    on_time = [t for t in with_deadline if _aware(t.completed_at) <= _aware(t.deadline)]

    cats = {c.id: c for c in db.scalars(select(Category).where(Category.user_id == user_id).order_by(Category.sort_order))}
    counts: dict[uuid.UUID | None, list[int]] = defaultdict(lambda: [0, 0])
    for t in tasks:
        counts[t.category_id][0 if t.status == "completed" else 1] += 1
    by_category = [
        CategoryProgress(name=cats[cid].name, color=cats[cid].color, completed=c, pending=p)
        for cid in cats if (c := counts[cid][0]) + (p := counts[cid][1]) > 0
    ]
    if None in counts and sum(counts[None]) > 0:
        by_category.append(CategoryProgress(name="Uncategorised", color="#7A7A72", completed=counts[None][0], pending=counts[None][1]))

    measured = [t for t in done if t.estimated_minutes and t.actual_minutes is not None]
    misses = sorted(measured, key=lambda t: abs(t.actual_minutes - t.estimated_minutes), reverse=True)[:5]

    live = list(db.scalars(select(Project).where(Project.user_id == user_id, Project.status == "active").order_by(Project.created_at.desc())))
    project_rows = [
        ProjectBrief(id=p.id, name=p.name, percent=p.progress.percent, remaining_minutes=p.progress.remaining_minutes, deadline=p.deadline)
        for p in projects.build_read(db, user_id, live, with_phases=False)
    ]

    return Analytics(
        days=days, completed=len(done), pending=len(active),
        overdue=sum(1 for t in active if t.deadline and _aware(t.deadline) < now),
        blocked=sum(1 for t in active if t.status == "blocked"),
        completed_with_deadline=len(with_deadline), completed_on_time=len(on_time),
        daily=daily, by_category=by_category,
        time_accuracy=TimeAccuracy(
            tasks=len(measured), estimated_minutes=sum(t.estimated_minutes for t in measured),
            actual_minutes=sum(t.actual_minutes for t in measured), biggest_misses=[_brief(t) for t in misses],
        ),
        projects=project_rows,
    )
