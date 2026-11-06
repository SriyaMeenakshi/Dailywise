import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ScheduleBlock, Task, UserPreference
from app.schemas.plan import BlockRead, GenerateRequest, PlannerPrefs, PlanRead, UnscheduledRead
from app.schemas.task import TaskUpdate
from app.services import priority_store
from app.services import tasks as task_service
from app.services.scheduler import Interval, PlanConfig, SchedTask, build_plan

DEFAULT_PREFS = PlannerPrefs(workday_start_min=9 * 60, workday_end_min=17 * 60, break_minutes=10)
PLANNABLE = ("inbox", "not_started", "in_progress")  # blocked/finished/archived tasks are not scheduled
MAX_CANDIDATES = 60
MAX_UNSCHEDULED_SHOWN = 8


def get_prefs(db: Session, user_id: uuid.UUID) -> PlannerPrefs:
    pref = db.get(UserPreference, user_id)
    if pref is None or pref.workday_start_min is None:
        return DEFAULT_PREFS
    return PlannerPrefs(
        workday_start_min=pref.workday_start_min,
        workday_end_min=pref.workday_end_min if pref.workday_end_min is not None else DEFAULT_PREFS.workday_end_min,
        break_minutes=pref.break_minutes if pref.break_minutes is not None else DEFAULT_PREFS.break_minutes,
    )


def set_prefs(db: Session, user_id: uuid.UUID, prefs: PlannerPrefs) -> PlannerPrefs:
    pref = db.get(UserPreference, user_id) or UserPreference(user_id=user_id)
    pref.workday_start_min, pref.workday_end_min, pref.break_minutes = (
        prefs.workday_start_min, prefs.workday_end_min, prefs.break_minutes,
    )
    db.add(pref)
    db.commit()
    return prefs


def _read(block: ScheduleBlock, levels: dict[uuid.UUID, str]) -> BlockRead:
    out = BlockRead.model_validate(block)
    out.priority_level = levels.get(block.task_id) if block.task_id else None
    return out


def _levels(db: Session, user_id: uuid.UUID, blocks: list[ScheduleBlock]) -> dict[uuid.UUID, str]:
    ids = [b.task_id for b in blocks if b.task_id]
    if not ids:
        return {}
    from app.services.priority import level_for

    rows = db.execute(select(Task.id, Task.priority_score).where(Task.id.in_(ids), Task.user_id == user_id)).all()
    return {i: level_for(s) for i, s in rows}


def blocks_for(db: Session, user_id: uuid.UUID, day: date) -> list[ScheduleBlock]:
    return list(db.scalars(
        select(ScheduleBlock).where(ScheduleBlock.user_id == user_id, ScheduleBlock.plan_date == day)
        .order_by(ScheduleBlock.start_min, ScheduleBlock.created_at)
    ))


def _active(blocks: list[ScheduleBlock]) -> list[ScheduleBlock]:
    return [b for b in blocks if b.kind != "postponed"]


def _plan_read(db, user_id, day, prefs, blocks, unscheduled=(), unscheduled_total=0) -> PlanRead:
    levels = _levels(db, user_id, blocks)
    planned = sum(b.end_min - b.start_min for b in blocks if b.kind == "task")
    busy = sum(b.end_min - b.start_min for b in _active(blocks))
    return PlanRead(
        date=day, window_start=prefs.workday_start_min, window_end=prefs.workday_end_min,
        break_minutes=prefs.break_minutes, blocks=[_read(b, levels) for b in blocks],
        unscheduled=list(unscheduled), unscheduled_total=unscheduled_total, planned_minutes=planned,
        free_minutes=max(prefs.workday_end_min - prefs.workday_start_min - busy, 0),
    )


def get_plan(db: Session, user_id: uuid.UUID, day: date) -> PlanRead:
    return _plan_read(db, user_id, day, get_prefs(db, user_id), blocks_for(db, user_id, day))


def generate(db: Session, user_id: uuid.UUID, req: GenerateRequest) -> PlanRead:
    """Rebuild the day. Fixed, pinned (user-moved), completed and postponed blocks are preserved."""
    prefs = get_prefs(db, user_id)
    priority_store.recompute_all(db, user_id)
    existing = blocks_for(db, user_id, req.date)
    for b in existing:
        if b.kind in ("task", "break") and not b.pinned and not b.done:
            db.delete(b)
    keep = [b for b in existing if b.kind in ("fixed", "postponed") or b.pinned or b.done]
    busy = [Interval(b.start_min, b.end_min) for b in _active(keep)]
    pinned_task_ids = {b.task_id for b in keep if b.task_id and b.kind == "task"}
    postponed = {b.task_id for b in keep if b.kind == "postponed" and b.task_id}

    graph = priority_store.load_graph(db, user_id)
    tasks = list(db.scalars(
        select(Task).where(Task.user_id == user_id, Task.status.in_(PLANNABLE))
        .order_by(Task.priority_score.desc(), Task.created_at).limit(MAX_CANDIDATES + len(pinned_task_ids) + len(postponed))
    ))
    midnight = datetime(req.date.year, req.date.month, req.date.day, tzinfo=UTC)
    sched = []
    for t in tasks:
        if t.id in pinned_task_ids or t.id in postponed:
            continue
        deadline_min = None
        if t.deadline:
            d = t.deadline if t.deadline.tzinfo else t.deadline.replace(tzinfo=UTC)
            local = d + timedelta(minutes=req.utc_offset_minutes)
            deadline_min = int((local - midnight).total_seconds() // 60)
        prereqs = frozenset(str(p) for p in graph.deps.get(t.id, ()) if graph.active(p))
        sched.append(SchedTask(str(t.id), t.title, t.priority_score, t.estimated_minutes, deadline_min, t.energy, prereqs))
    sched = sched[:MAX_CANDIDATES]

    plan = build_plan(
        sched,
        PlanConfig(prefs.workday_start_min, prefs.workday_end_min, prefs.break_minutes, req.start_after_min),
        busy,
        already_placed=frozenset(str(i) for i in pinned_task_ids),
    )
    for p in plan.blocks:
        db.add(ScheduleBlock(
            user_id=user_id, plan_date=req.date, kind=p.kind, task_id=uuid.UUID(p.task_id) if p.task_id else None,
            title=p.title, start_min=p.start, end_min=p.end, warning=p.warning,
        ))
    db.commit()
    unscheduled = [UnscheduledRead(task_id=uuid.UUID(u.task_id), title=u.title, reason=u.reason) for u in plan.unscheduled]
    return _plan_read(
        db, user_id, req.date, prefs, blocks_for(db, user_id, req.date),
        unscheduled[:MAX_UNSCHEDULED_SHOWN], len(unscheduled),
    )


# ── editing ─────────────────────────────────────────────────────────────────────
def get_block(db: Session, user_id: uuid.UUID, block_id: uuid.UUID) -> ScheduleBlock:
    block = db.scalar(select(ScheduleBlock).where(ScheduleBlock.id == block_id, ScheduleBlock.user_id == user_id))
    if block is None:
        raise HTTPException(404, "Block not found")
    return block


def _overlaps(blocks: list[ScheduleBlock], start: int, end: int, ignore: set[uuid.UUID] = frozenset()) -> bool:
    return any(b.start_min < end and start < b.end_min for b in _active(blocks) if b.id not in ignore)


def create_fixed(db: Session, user_id: uuid.UUID, day: date, title: str, start: int, end: int) -> ScheduleBlock:
    if _overlaps(blocks_for(db, user_id, day), start, end):
        raise HTTPException(409, "That overlaps another block. Move or remove it first.")
    block = ScheduleBlock(user_id=user_id, plan_date=day, kind="fixed", title=title.strip(), start_min=start, end_min=end, pinned=True)
    db.add(block)
    db.commit()
    return block


def update_block(db: Session, user_id: uuid.UUID, block_id: uuid.UUID, changes: dict) -> ScheduleBlock:
    block = get_block(db, user_id, block_id)
    if block.kind == "postponed":
        raise HTTPException(409, "Bring this task back before editing it")
    if "title" in changes:
        if block.kind not in ("fixed",):
            raise HTTPException(422, "Only your own blocks can be renamed")
        block.title = changes["title"].strip()
    if "done" in changes:
        _set_done(db, user_id, block, changes["done"])
    start, end = changes.get("start_min", block.start_min), changes.get("end_min", block.end_min)
    if ("start_min" in changes or "end_min" in changes) and (start, end) != (block.start_min, block.end_min):
        if start >= end:
            raise HTTPException(422, "The block must end after it starts")
        if _overlaps(blocks_for(db, user_id, block.plan_date), start, end, {block.id}):
            raise HTTPException(409, "That overlaps another block")
        block.start_min, block.end_min, block.pinned, block.warning = start, end, True, None
    db.commit()
    return block


def _set_done(db: Session, user_id: uuid.UUID, block: ScheduleBlock, done: bool) -> None:
    if block.kind != "task" or block.task_id is None:
        raise HTTPException(422, "Only task blocks can be completed")
    block.done = done
    task_service.update_task(db, user_id, block.task_id, TaskUpdate(status="completed" if done else "in_progress"))


def move_block(db: Session, user_id: uuid.UUID, block_id: uuid.UUID, direction: str) -> list[ScheduleBlock]:
    """Swap with the neighbouring task block, re-laying both inside the span they already occupied."""
    block = get_block(db, user_id, block_id)
    if block.kind != "task":
        raise HTTPException(422, "Only task blocks can be reordered")
    tasks = [b for b in blocks_for(db, user_id, block.plan_date) if b.kind == "task"]
    i = tasks.index(next(b for b in tasks if b.id == block.id))
    j = i - 1 if direction == "up" else i + 1
    if not 0 <= j < len(tasks):
        raise HTTPException(409, "It is already at the " + ("top" if direction == "up" else "bottom"))
    first, second = (tasks[j], tasks[i]) if direction == "up" else (tasks[i], tasks[j])
    gap = second.start_min - first.end_min
    len_first, len_second = first.end_min - first.start_min, second.end_min - second.start_min
    span_start = first.start_min
    # `second` now goes first, keeping the original gap between them.
    second.start_min, second.end_min = span_start, span_start + len_second
    first.start_min, first.end_min = second.end_min + gap, second.end_min + gap + len_first
    for b in (first, second):
        b.pinned, b.warning = True, None
    # Anything that sat in the gap (a break) must not now overlap: drop breaks inside the span.
    for b in blocks_for(db, user_id, block.plan_date):
        if b.kind == "break" and b.start_min < first.end_min and second.start_min < b.end_min:
            db.delete(b)
    db.commit()
    return [first, second]


def postpone(db: Session, user_id: uuid.UUID, block_id: uuid.UUID) -> ScheduleBlock:
    block = get_block(db, user_id, block_id)
    if block.kind != "task":
        raise HTTPException(422, "Only task blocks can be postponed")
    block.kind, block.pinned, block.done, block.warning = "postponed", False, False, None
    db.commit()
    return block


def delete_block(db: Session, user_id: uuid.UUID, block_id: uuid.UUID) -> None:
    """Deleting a postponed marker brings that task back into the next generated plan for the day."""
    db.delete(get_block(db, user_id, block_id))
    db.commit()
