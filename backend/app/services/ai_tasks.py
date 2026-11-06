"""Turns raw model output into safe, bounded suggestions, and applies approved plans.

The model only ever *suggests*. Nothing is saved until the user approves it in the UI, and every
approved item goes through the same validation as manually-entered data."""

import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.ai_gateway import AIGateway
from app.ai.schemas import Decomposition, ParseResult
from app.models import Category, Phase, Project, Subtask, Task, TaskDependency
from app.schemas.ai import (
    MAX_PHASES,
    MAX_SUBTASKS,
    MAX_TASKS_PER_PHASE,
    MAX_TASKS_TOTAL,
    ApplyRequest,
    ApplyResponse,
    DecomposeBody,
    DecomposeRequest,
    DecomposeResponse,
    ParseRequest,
    ParseResponse,
    PlanPhase,
    PlanSubtask,
    PlanTask,
    SuggestedTask,
)
from app.services import priority_store
from app.services.tasks import log

MAX_PARSED_TASKS = 20
MIN_MINUTES, MAX_MINUTES = 5, 60 * 16

# If a note contains none of these (and no digits), it cannot be stating a deadline.
_TIME_WORDS = re.compile(
    r"\d|today|tonight|tomorrow|yesterday|week|weekend|month|year|monday|tuesday|wednesday|thursday|friday|"
    r"saturday|sunday|\b(?:mon|tue|tues|wed|thu|thur|fri|sat|sun)\b|january|february|march|april|may|june|july|"
    r"august|september|october|november|december|eod|eow|deadline|\bdue\b|asap|morning|evening|noon",
    re.IGNORECASE,
)


def _clean(text: str | None, limit: int) -> str | None:
    text = (text or "").strip()
    return text[:limit] if text else None


def _clamp_minutes(value: int | None) -> int | None:
    if value is None:
        return None
    return value if MIN_MINUTES <= value <= MAX_MINUTES else None  # an absurd estimate is worse than none


def _local_now(offset_minutes: int) -> datetime:
    return datetime.now(UTC) + timedelta(minutes=offset_minutes)


def _parse_deadline(raw: str | None, offset_minutes: int, today_local: datetime) -> tuple[datetime | None, bool]:
    """Model date string -> (UTC datetime, has_time). Date-only deadlines mean end of that day."""
    if not raw:
        return None, False
    raw = raw.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None, False
    has_time = len(raw) > 10 and (parsed.hour or parsed.minute) != 0
    if parsed.tzinfo is not None:
        return parsed.astimezone(UTC), has_time
    if not has_time:
        parsed = parsed.replace(hour=23, minute=59)
    utc = (parsed - timedelta(minutes=offset_minutes)).replace(tzinfo=UTC)
    if parsed.date() < (today_local - timedelta(days=1)).date():
        return None, False  # a deadline long in the past is almost certainly a model mistake
    return utc, has_time


def parse_tasks(db: Session, user_id: uuid.UUID, gateway: AIGateway, req: ParseRequest) -> ParseResponse:
    categories = list(db.scalars(select(Category).where(Category.user_id == user_id).order_by(Category.sort_order)))
    by_name = {c.name.lower(): c for c in categories}
    now_local = _local_now(req.utc_offset_minutes)
    today = now_local.strftime("%Y-%m-%d")

    message = (
        f"Current local date: {today} ({now_local.strftime('%A')}).\n"
        f"Categories: {', '.join(c.name for c in categories) or '(none)'}\n\n"
        f"<note>\n{req.text}\n</note>"
    )
    result = gateway.run(
        db, user_id, feature="parse_tasks", input_text=req.text, user_message=message,
        # `today` is part of the key: "by Friday" means different dates on different days.
        cache_payload={"text": " ".join(req.text.split()), "today": today, "categories": sorted(by_name)},
        schema=ParseResult, force=req.force,
    )

    note_mentions_time = bool(_TIME_WORDS.search(req.text))
    removed = False
    tasks: list[SuggestedTask] = []
    for item in result.data.tasks[:MAX_PARSED_TASKS]:
        title = _clean(item.title, 300)
        if not title:
            continue
        deadline, has_time = (None, False)
        if item.deadline:
            if note_mentions_time:
                deadline, has_time = _parse_deadline(item.deadline, req.utc_offset_minutes, now_local)
            removed = removed or deadline is None
        category = by_name.get((item.category or "").strip().lower())
        tasks.append(SuggestedTask(
            title=title,
            description=_clean(item.description, 2000),
            category_id=category.id if category else None,
            category_name=category.name if category else None,
            deadline=deadline,
            deadline_has_time=has_time,
            expected_outcome=_clean(item.expected_outcome, 2000),
            estimated_minutes=_clamp_minutes(item.estimated_minutes),
            importance=item.importance if item.importance and 1 <= item.importance <= 5 else None,
        ))
    questions = [q for q in (_clean(q, 300) for q in result.data.questions[:5]) if q]
    return ParseResponse(tasks=tasks, questions=questions, cached=result.cached, model=result.model, deadlines_removed=removed)


# ── project decomposition ───────────────────────────────────────────────────────
def _reaches(edges: dict[str, set[str]], start: str, target: str) -> bool:
    seen, stack = set(), [start]
    while stack:
        node = stack.pop()
        if node == target:
            return True
        if node not in seen:
            seen.add(node)
            stack.extend(edges.get(node, ()))
    return False


def _sanitise(raw: Decomposition) -> tuple[DecomposeBody | None, bool]:
    truncated = len(raw.phases) > MAX_PHASES
    phases: list[PlanPhase] = []
    total = 0
    used_refs: set[str] = set()
    for pi, phase in enumerate(raw.phases[:MAX_PHASES], start=1):
        name = _clean(phase.name, 200)
        if not name:
            continue
        tasks: list[PlanTask] = []
        truncated = truncated or len(phase.tasks) > MAX_TASKS_PER_PHASE
        for ti, t in enumerate(phase.tasks[:MAX_TASKS_PER_PHASE], start=1):
            title = _clean(t.title, 300)
            if not title or total >= MAX_TASKS_TOTAL:
                truncated = truncated or bool(title)
                continue
            ref = (t.ref or "").strip()[:40]
            if not ref or ref in used_refs:
                ref = f"p{pi}t{ti}"
                while ref in used_refs:
                    ref += "x"
            used_refs.add(ref)
            truncated = truncated or len(t.subtasks) > MAX_SUBTASKS
            subs = [
                PlanSubtask(title=s_title, estimated_minutes=_clamp_minutes(s.estimated_minutes))
                for s in t.subtasks[:MAX_SUBTASKS] if (s_title := _clean(s.title, 300))
            ]
            tasks.append(PlanTask(
                ref=ref, title=title, description=_clean(t.description, 2000),
                estimated_minutes=_clamp_minutes(t.estimated_minutes), subtasks=subs,
                depends_on=[d.strip() for d in t.depends_on],
            ))
            total += 1
        phases.append(PlanPhase(name=name, milestone=_clean(phase.milestone, 300), tasks=tasks))

    # Keep only dependencies that point at real tasks, and drop any edge that would close a loop.
    known = {t.ref for p in phases for t in p.tasks}
    edges: dict[str, set[str]] = {}
    for p in phases:
        for t in p.tasks:
            kept: list[str] = []
            for d in dict.fromkeys(t.depends_on):
                # t -> d closes a loop exactly when d already (transitively) depends on t.
                if d in known and d != t.ref and not _reaches(edges, d, t.ref):
                    kept.append(d)
            t.depends_on = kept
            edges[t.ref] = set(kept)
    if not phases or not any(p.tasks for p in phases):
        return None, truncated
    name = _clean(raw.project_name, 200) or "New project"
    return DecomposeBody(project_name=name, objective=_clean(raw.objective, 5000), phases=phases), truncated


def decompose_project(db: Session, user_id: uuid.UUID, gateway: AIGateway, req: DecomposeRequest) -> DecomposeResponse:
    from app.ai.errors import AIInvalidResponse

    message = f"<goal>\n{req.goal}\n</goal>\n<context>\n{req.context or '(none)'}\n</context>"
    result = gateway.run(
        db, user_id, feature="decompose_project", input_text=req.goal + req.context, user_message=message,
        cache_payload={"goal": " ".join(req.goal.split()), "context": " ".join(req.context.split())},
        schema=Decomposition, force=req.force,
    )
    body, truncated = _sanitise(result.data)
    if body is None:
        raise AIInvalidResponse("The AI did not produce a usable plan. Try describing the goal in more detail.")
    return DecomposeResponse(**body.model_dump(), cached=result.cached, model=result.model, truncated=truncated)


def apply_plan(db: Session, user_id: uuid.UUID, req: ApplyRequest) -> ApplyResponse:
    """Create the user-approved plan in one transaction."""
    from fastapi import HTTPException

    if req.project_id:
        project = db.scalar(select(Project).where(Project.id == req.project_id, Project.user_id == user_id))
        if project is None:
            raise HTTPException(404, "Project not found")
    else:
        project = Project(user_id=user_id, name=req.project_name, objective=req.objective, deadline=req.deadline)
        db.add(project)
        db.flush()

    order = (db.scalar(select(func.max(Phase.sort_order)).where(Phase.project_id == project.id)) or 0)
    ref_to_task: dict[str, Task] = {}
    pending_deps: list[tuple[str, str]] = []
    n_tasks = 0
    for phase_in in req.phases:
        order += 1
        phase = Phase(user_id=user_id, project_id=project.id, name=phase_in.name, milestone=phase_in.milestone, sort_order=order)
        db.add(phase)
        db.flush()
        for t in phase_in.tasks:
            task = Task(
                user_id=user_id, project_id=project.id, phase_id=phase.id, title=t.title, description=t.description,
                estimated_minutes=t.estimated_minutes, status="not_started",
            )
            db.add(task)
            db.flush()
            log(db, user_id, task.id, "created", {"title": task.title, "source": "ai_breakdown"})
            for i, s in enumerate(t.subtasks, start=1):
                db.add(Subtask(user_id=user_id, task_id=task.id, title=s.title, estimated_minutes=s.estimated_minutes, sort_order=i))
            ref_to_task[t.ref] = task
            pending_deps.extend((t.ref, d) for d in t.depends_on)
            n_tasks += 1
    for ref, dep in pending_deps:
        db.add(TaskDependency(task_id=ref_to_task[ref].id, depends_on_id=ref_to_task[dep].id, user_id=user_id))
    db.commit()
    priority_store.recompute_all(db, user_id)
    return ApplyResponse(project_id=project.id, phases_created=len(req.phases), tasks_created=n_tasks)
