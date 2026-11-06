import pytest

from app.services.progress import DEFAULT_TASK_MINUTES, SubtaskInfo, TaskInfo, compute_progress, task_completion


def test_progress_is_weighted_by_effort_not_count():
    tasks = [TaskInfo("completed", 30), TaskInfo("not_started", 270)]
    p = compute_progress(tasks)
    assert p.percent == 10.0  # 1 of 2 tasks done, but only 30 of 300 minutes
    assert (p.total_minutes, p.done_minutes, p.remaining_minutes) == (300, 30, 270)
    assert (p.tasks_total, p.tasks_done) == (2, 1)


def test_empty_project_is_zero_not_an_error():
    assert compute_progress([]).percent == 0


def test_all_complete_is_100():
    assert compute_progress([TaskInfo("completed", 60), TaskInfo("completed", 15)]).percent == 100


def test_archived_tasks_are_excluded():
    p = compute_progress([TaskInfo("completed", 60), TaskInfo("archived", 600)])
    assert p.percent == 100 and p.tasks_total == 1


def test_unestimated_tasks_use_default_weight_and_are_reported():
    p = compute_progress([TaskInfo("completed"), TaskInfo("not_started")])
    assert p.total_minutes == 2 * DEFAULT_TASK_MINUTES and p.percent == 50
    assert p.unestimated_tasks == 2


def test_partial_subtasks_count_by_their_effort():
    task = TaskInfo("in_progress", 100, [SubtaskInfo(True, 30), SubtaskInfo(False, 10)])
    assert task_completion(task) == pytest.approx(0.75)
    assert compute_progress([task]).done_minutes == 75


def test_completed_task_ignores_its_subtasks():
    assert task_completion(TaskInfo("completed", 60, [SubtaskInfo(False)])) == 1.0


def test_task_without_subtasks_is_not_partially_done():
    assert task_completion(TaskInfo("in_progress", 60)) == 0.0
