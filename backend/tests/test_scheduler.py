from app.services.scheduler import Interval, PlanConfig, SchedTask, build_plan, free_gaps

H = 60
CFG = PlanConfig(day_start=9 * H, day_end=17 * H, break_minutes=10)
NO_BREAK = PlanConfig(day_start=9 * H, day_end=17 * H, break_minutes=0)


def t(id, minutes=60, priority=50, **kw):
    return SchedTask(id=id, title=id.upper(), priority=priority, minutes=minutes, **kw)


def tasks_in(plan):
    return [b for b in plan.blocks if b.kind == "task"]


def no_overlap(plan):
    blocks = sorted(plan.blocks, key=lambda b: b.start)
    return all(a.end <= b.start for a, b in zip(blocks, blocks[1:]))


def test_higher_priority_goes_first():
    plan = build_plan([t("low", priority=10), t("high", priority=90), t("mid", priority=50)], NO_BREAK)
    assert [b.task_id for b in tasks_in(plan)] == ["high", "mid", "low"]


def test_empty_input_gives_an_empty_plan():
    plan = build_plan([], CFG)
    assert plan.blocks == [] and plan.unscheduled == []


def test_blocks_stay_inside_the_window_and_never_overlap():
    plan = build_plan([t(f"t{i}", 45, priority=i) for i in range(20)], CFG)
    assert plan.blocks and no_overlap(plan)
    assert all(CFG.day_start <= b.start and b.end <= CFG.day_end for b in plan.blocks)
    assert plan.unscheduled  # twenty 45-minute tasks cannot fit in 8 hours


def test_breaks_separate_tasks_but_not_trailing():
    plan = build_plan([t("a"), t("b")], CFG)
    kinds = [(b.kind, b.start, b.end) for b in plan.blocks]
    assert kinds == [("task", 540, 600), ("break", 600, 610), ("task", 610, 670)]


def test_no_break_when_break_minutes_is_zero():
    plan = build_plan([t("a"), t("b")], NO_BREAK)
    assert [b.kind for b in plan.blocks] == ["task", "task"] and plan.blocks[1].start == 600


def test_task_that_does_not_fit_is_reported_not_squeezed():
    plan = build_plan([t("big", 600)], CFG)
    assert plan.blocks == [] and plan.unscheduled[0].reason == "Longer than your available time today"


def test_leftover_tasks_are_reported_with_a_reason():
    plan = build_plan([t("a", 240, 90), t("b", 240, 80), t("c", 60, 10)], CFG)
    # a ends 13:00; with the break, b (4h) would end 17:10 and not fit, but the smaller c does.
    assert [b.task_id for b in tasks_in(plan)] == ["a", "c"]
    assert [(u.task_id, u.reason) for u in plan.unscheduled] == [("b", "Not enough free time left today")]


def test_busy_blocks_are_respected():
    busy = [Interval(10 * H, 12 * H)]  # a fixed 10:00-12:00 commitment
    plan = build_plan([t("a", 90, 90), t("b", 60, 50)], NO_BREAK, busy)
    spans = {b.task_id: (b.start, b.end) for b in tasks_in(plan)}
    assert spans == {"b": (9 * H, 10 * H), "a": (12 * H, 12 * H + 90)}  # a (90m) cannot fit before 10:00
    assert no_overlap(plan) and all(not (b.start < 12 * H and b.end > 10 * H) for b in plan.blocks)


def test_earliest_gap_is_filled_before_later_ones():
    busy = [Interval(10 * H, 12 * H)]
    plan = build_plan([t("big", 120, 90), t("small", 60, 10)], NO_BREAK, busy)
    by_id = {b.task_id: b for b in tasks_in(plan)}
    assert by_id["small"].start == 9 * H  # fills the 9-10 gap instead of leaving it empty
    assert by_id["big"].start == 12 * H


def test_task_longer_than_every_gap_is_unscheduled():
    busy = [Interval(10 * H, 12 * H), Interval(13 * H, 17 * H)]
    plan = build_plan([t("a", 90)], NO_BREAK, busy)
    assert plan.blocks == [] and len(plan.unscheduled) == 1


def test_dependencies_order_tasks_even_against_priority():
    base = t("base", priority=10)
    dependent = t("dependent", priority=99, prerequisites=frozenset({"base"}))
    plan = build_plan([dependent, base], NO_BREAK)
    assert [b.task_id for b in tasks_in(plan)] == ["base", "dependent"]


def test_task_waiting_on_an_unschedulable_prerequisite_is_not_scheduled():
    plan = build_plan([t("big", 900), t("child", prerequisites=frozenset({"big"}))], CFG)
    assert plan.blocks == []
    reasons = {u.task_id: u.reason for u in plan.unscheduled}
    assert reasons["child"] == "Waiting on BIG"


def test_prerequisite_outside_the_candidate_set_blocks_the_task():
    plan = build_plan([t("child", prerequisites=frozenset({"unknown"}))], CFG)
    assert plan.blocks == [] and plan.unscheduled[0].reason.startswith("Waiting on")


def test_already_placed_prerequisite_unblocks_the_task():
    plan = build_plan([t("child", prerequisites=frozenset({"pinned"}))], CFG, already_placed=frozenset({"pinned"}))
    assert [b.task_id for b in tasks_in(plan)] == ["child"]


def test_dependency_chain_is_scheduled_in_order():
    chain = [t("c", priority=99, prerequisites=frozenset({"b"})), t("b", priority=50, prerequisites=frozenset({"a"})), t("a", priority=1)]
    assert [b.task_id for b in tasks_in(build_plan(chain, NO_BREAK))] == ["a", "b", "c"]


def test_energy_high_work_early_low_work_late():
    tasks = [t("light", 60, 50, energy="low"), t("heavy", 60, 50, energy="high")]
    order = [b.task_id for b in tasks_in(build_plan(tasks, NO_BREAK))]
    assert order == ["heavy", "light"]


def test_energy_nudge_does_not_override_a_big_priority_gap():
    tasks = [t("urgent-light", 60, 95, energy="low"), t("minor-heavy", 60, 20, energy="high")]
    assert tasks_in(build_plan(tasks, NO_BREAK))[0].task_id == "urgent-light"


def test_deadline_breaks_priority_ties():
    tasks = [t("later", 60, 50, deadline_min=2000), t("sooner", 60, 50, deadline_min=700)]
    assert tasks_in(build_plan(tasks, NO_BREAK))[0].task_id == "sooner"


def test_deadline_warnings_are_flagged_but_tasks_still_scheduled():
    plan = build_plan([t("a", 60, 50, deadline_min=9 * H + 30), t("b", 60, 40, deadline_min=9 * H)], NO_BREAK)
    warnings = {b.task_id: b.warning for b in tasks_in(plan)}
    assert warnings["a"] == "Finishes after its deadline"
    assert warnings["b"] == "Scheduled after its deadline"


def test_no_warning_when_the_deadline_is_comfortable():
    plan = build_plan([t("a", 60, deadline_min=12 * H)], NO_BREAK)
    assert tasks_in(plan)[0].warning is None


def test_start_after_skips_the_past_and_rounds_up():
    plan = build_plan([t("a")], PlanConfig(9 * H, 17 * H, 10, start_after=11 * H + 3))
    assert tasks_in(plan)[0].start == 11 * H + 5


def test_start_after_end_of_day_schedules_nothing():
    plan = build_plan([t("a")], PlanConfig(9 * H, 17 * H, 10, start_after=17 * H))
    assert plan.blocks == [] and plan.unscheduled[0].task_id == "a"


def test_durations_round_up_to_five_minutes_and_default_when_missing():
    plan = build_plan([t("a", 31), SchedTask("b", "B", 10, None)], NO_BREAK)
    spans = {b.task_id: b.end - b.start for b in tasks_in(plan)}
    assert spans == {"a": 35, "b": 30}


def test_plan_is_deterministic_regardless_of_input_order():
    items = [t(f"t{i}", 30 + i, priority=i % 3 * 10) for i in range(8)]
    assert build_plan(items, CFG) == build_plan(list(reversed(items)), CFG)


def test_free_gaps():
    gaps = free_gaps(540, 1020, [Interval(600, 660), Interval(650, 700), Interval(1000, 2000)])
    assert gaps == [Interval(540, 600), Interval(700, 1000)]
    assert free_gaps(540, 1020, [Interval(0, 2000)]) == []
