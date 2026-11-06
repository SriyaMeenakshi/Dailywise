"""Deterministic daily scheduler. Pure functions: no database, no AI. Same input, same plan.

Times are minutes from local midnight. The plan:
  1. starts with the user's availability window, minus fixed/pinned blocks (the free gaps);
  2. repeatedly fills the EARLIEST open time with the best eligible task that fits there, where
     "best" is highest priority, nudged by energy (demanding work early, light work late);
  3. never starts a task before the tasks it depends on, never leaves the window, never overlaps;
  4. leaves a break between consecutive tasks, and reports what did not fit and why.
Deadlines are separate from time blocks: a task scheduled to finish after its deadline is flagged,
not moved, because the deadline is the user's fact and the block is only a plan.
"""

from dataclasses import dataclass, field

STEP = 5
DEFAULT_TASK_MINUTES = 30
ENERGY_NUDGE = 8.0


@dataclass(frozen=True)
class SchedTask:
    id: str
    title: str
    priority: float
    minutes: int | None = None
    deadline_min: int | None = None  # minutes from the plan date's local midnight (may be negative)
    energy: str = "medium"
    prerequisites: frozenset[str] = frozenset()  # unfinished tasks that must come first


@dataclass(frozen=True)
class Interval:
    start: int
    end: int


@dataclass(frozen=True)
class PlanConfig:
    day_start: int = 9 * 60
    day_end: int = 17 * 60
    break_minutes: int = 10
    start_after: int | None = None  # e.g. "now", when planning today


@dataclass(frozen=True)
class Placed:
    kind: str  # "task" | "break"
    start: int
    end: int
    task_id: str | None = None
    title: str | None = None
    warning: str | None = None


@dataclass(frozen=True)
class Unscheduled:
    task_id: str
    title: str
    reason: str


@dataclass
class Plan:
    blocks: list[Placed] = field(default_factory=list)
    unscheduled: list[Unscheduled] = field(default_factory=list)


def _ceil(value: int) -> int:
    return -(-value // STEP) * STEP


def duration(task: SchedTask) -> int:
    return _ceil(task.minutes or DEFAULT_TASK_MINUTES)


def free_gaps(window_start: int, window_end: int, busy: list[Interval]) -> list[Interval]:
    """The window minus the busy intervals, sorted, with no empty gaps."""
    gaps, cursor = [], window_start
    for b in sorted(busy, key=lambda i: (i.start, i.end)):
        if b.end <= cursor:
            continue
        if b.start > cursor:
            gaps.append(Interval(cursor, min(b.start, window_end)))
        cursor = max(cursor, b.end)
        if cursor >= window_end:
            break
    if cursor < window_end:
        gaps.append(Interval(cursor, window_end))
    return [g for g in gaps if g.end > g.start]


def _energy_adjusted(task: SchedTask, start: int, config: PlanConfig) -> float:
    span = max(config.day_end - config.day_start, 1)
    position = (start - config.day_start) / span
    early, late = position < 1 / 3, position > 2 / 3
    if task.energy == "high":
        return task.priority + (ENERGY_NUDGE if early else -ENERGY_NUDGE if late else 0)
    if task.energy == "low":
        return task.priority + (ENERGY_NUDGE if late else -ENERGY_NUDGE if early else 0)
    return task.priority


def build_plan(
    tasks: list[SchedTask],
    config: PlanConfig = PlanConfig(),
    busy: list[Interval] | None = None,
    already_placed: frozenset[str] = frozenset(),
) -> Plan:
    """`already_placed` are task ids that are satisfied for dependency purposes (e.g. pinned today)."""
    start = config.day_start if config.start_after is None else max(config.day_start, _ceil(config.start_after))
    gaps = free_gaps(start, config.day_end, busy or [])
    plan = Plan()
    placed_ids: set[str] = set(already_placed)
    remaining = {t.id: t for t in tasks}
    title_of = {t.id: t.title for t in tasks}
    window_minutes = config.day_end - start
    last_end: int | None = None  # end of the previous *task* block

    for t in list(remaining.values()):
        if duration(t) > max(window_minutes, 0):
            plan.unscheduled.append(Unscheduled(t.id, t.title, "Longer than your available time today"))
            del remaining[t.id]

    def candidate_start(task: SchedTask, cursor: int) -> int | None:
        """Earliest time at/after `cursor` where the task fits wholly inside one gap (after a break)."""
        need = duration(task)
        for gap in gaps:
            begin = max(gap.start, cursor)
            if last_end is not None and begin == last_end and config.break_minutes:
                begin += config.break_minutes  # a break follows the previous task
            begin = _ceil(begin)
            if begin + need <= gap.end:
                return begin
        return None

    cursor = start
    while remaining:
        options = []
        for task in remaining.values():
            if not task.prerequisites <= placed_ids:
                continue
            s = candidate_start(task, cursor)
            if s is not None:
                options.append((s, task))
        if not options:
            break
        earliest = min(s for s, _ in options)
        pool = [(t, s) for s, t in options if s == earliest]
        task, begin = max(
            pool,
            key=lambda ts: (
                _energy_adjusted(ts[0], ts[1], config),
                -(ts[0].deadline_min if ts[0].deadline_min is not None else 10**9),
                ts[0].title.lower(),
                ts[0].id,
            ),
        )
        end = begin + duration(task)
        if last_end is not None and config.break_minutes and begin - last_end >= config.break_minutes:
            plan.blocks.append(Placed("break", begin - config.break_minutes, begin))
        warning = None
        if task.deadline_min is not None and end > task.deadline_min:
            warning = "Scheduled after its deadline" if begin >= task.deadline_min else "Finishes after its deadline"
        plan.blocks.append(Placed("task", begin, end, task.id, task.title, warning))
        placed_ids.add(task.id)
        del remaining[task.id]
        cursor, last_end = end, end

    for task in remaining.values():
        missing = sorted(title_of.get(p, "another task") for p in task.prerequisites - placed_ids)
        if missing:
            reason = f"Waiting on {', '.join(missing)}"
        else:
            reason = "Not enough free time left today"
        plan.unscheduled.append(Unscheduled(task.id, task.title, reason))
    return plan
