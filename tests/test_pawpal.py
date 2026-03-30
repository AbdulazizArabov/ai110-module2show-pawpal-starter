from datetime import date, timedelta, datetime
from unittest.mock import patch

import pytest

from pawpal_system import Task, Pet, Owner, Scheduler, ScheduledEntry, DailyPlan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_owner(minutes: int = 120) -> Owner:
    return Owner(name="Alex", email="alex@example.com", available_minutes_per_day=minutes)


def make_pet(name: str = "Mochi") -> Pet:
    return Pet(name=name, species="dog", age=3)


# ---------------------------------------------------------------------------
# Existing baseline tests
# ---------------------------------------------------------------------------

def test_mark_done_sets_complete():
    task = Task(name="Morning walk", category="walk", duration_minutes=30, priority=5)
    task.mark_done()
    assert task.is_complete is True


def test_add_task_increases_pet_task_count():
    pet = make_pet()
    task = Task(name="Breakfast", category="feeding", duration_minutes=10, priority=4)
    pet.add_task(task)
    assert len(pet.get_tasks()) == 1


# ---------------------------------------------------------------------------
# 1. Sorting Correctness
# ---------------------------------------------------------------------------

class TestSortByTime:
    def test_chronological_order(self):
        """Tasks come back earliest due_time first."""
        t1 = Task(name="Lunch",    category="feeding", duration_minutes=10, priority=3, due_time="12:00")
        t2 = Task(name="Morning",  category="walk",    duration_minutes=20, priority=3, due_time="07:00")
        t3 = Task(name="Evening",  category="walk",    duration_minutes=20, priority=3, due_time="18:00")

        scheduler = Scheduler(make_owner())
        result = scheduler.sort_by_time([t1, t2, t3])

        assert [t.due_time for t in result] == ["07:00", "12:00", "18:00"]

    def test_untimed_tasks_go_last(self):
        """Tasks with no due_time are placed after all timed tasks."""
        timed   = Task(name="Walk",  category="walk",    duration_minutes=30, priority=5, due_time="08:00")
        untimed = Task(name="Groom", category="grooming", duration_minutes=15, priority=5)

        scheduler = Scheduler(make_owner())
        result = scheduler.sort_by_time([untimed, timed])

        assert result[0].name == "Walk"
        assert result[1].name == "Groom"

    def test_same_time_tiebreak_by_priority(self):
        """When two tasks share a due_time, higher priority wins."""
        low  = Task(name="Low",  category="walk", duration_minutes=10, priority=2, due_time="09:00")
        high = Task(name="High", category="walk", duration_minutes=10, priority=5, due_time="09:00")

        scheduler = Scheduler(make_owner())
        result = scheduler.sort_by_time([low, high])

        assert result[0].name == "High"


class TestSortByPriority:
    def test_descending_priority_order(self):
        tasks = [
            Task(name="A", category="walk",    duration_minutes=10, priority=2),
            Task(name="B", category="feeding", duration_minutes=10, priority=5),
            Task(name="C", category="meds",    duration_minutes=10, priority=3),
        ]
        scheduler = Scheduler(make_owner())
        result = scheduler.sort_by_priority(tasks)

        assert [t.priority for t in result] == [5, 3, 2]


# ---------------------------------------------------------------------------
# 2. Recurrence Logic
# ---------------------------------------------------------------------------

class TestRecurrenceLogic:
    def test_daily_task_creates_next_day_occurrence(self):
        """Completing a daily task adds a new task due tomorrow."""
        pet = make_pet()
        today = date.today()
        task = Task(
            name="Morning walk", category="walk",
            duration_minutes=30, priority=5,
            recurrence="daily", due_date=today,
        )
        pet.add_task(task)

        scheduler = Scheduler(make_owner())
        new_task = scheduler.mark_task_complete("Morning walk", pet)

        assert new_task is not None
        assert new_task.due_date == today + timedelta(days=1)
        assert new_task.is_complete is False

    def test_weekly_task_creates_next_week_occurrence(self):
        """Completing a weekly task adds a new task due in 7 days."""
        pet = make_pet()
        today = date.today()
        task = Task(
            name="Bath time", category="grooming",
            duration_minutes=45, priority=3,
            recurrence="weekly", recur_day=today.weekday(), due_date=today,
        )
        pet.add_task(task)

        scheduler = Scheduler(make_owner())
        new_task = scheduler.mark_task_complete("Bath time", pet)

        assert new_task is not None
        assert new_task.due_date == today + timedelta(weeks=1)
        assert new_task.is_complete is False

    def test_non_recurring_task_returns_none(self):
        """Completing a one-off task returns None and adds nothing new."""
        pet = make_pet()
        task = Task(name="Vet visit", category="health", duration_minutes=60, priority=5)
        pet.add_task(task)

        scheduler = Scheduler(make_owner())
        result = scheduler.mark_task_complete("Vet visit", pet)

        assert result is None
        assert len(pet.get_tasks()) == 1   # original only, no new task added

    def test_mark_complete_raises_for_unknown_task(self):
        """ValueError raised when task name does not exist."""
        pet = make_pet()
        scheduler = Scheduler(make_owner())

        with pytest.raises(ValueError, match="No pending task"):
            scheduler.mark_task_complete("Nonexistent", pet)

    def test_mark_complete_raises_for_already_done_task(self):
        """ValueError raised when the matching task is already complete."""
        pet = make_pet()
        task = Task(name="Walk", category="walk", duration_minutes=20, priority=3)
        task.mark_done()
        pet.add_task(task)

        scheduler = Scheduler(make_owner())
        with pytest.raises(ValueError):
            scheduler.mark_task_complete("Walk", pet)


# ---------------------------------------------------------------------------
# 3. Conflict Detection
# ---------------------------------------------------------------------------

class TestConflictDetection:
    def _make_entry(self, pet_name, task_name, due_time, duration) -> ScheduledEntry:
        task = Task(name=task_name, category="walk", duration_minutes=duration,
                    priority=3, due_time=due_time)
        return ScheduledEntry(pet_name=pet_name, task=task)

    def test_overlapping_tasks_flagged(self):
        """Two tasks whose windows overlap produce a conflict."""
        e1 = self._make_entry("Mochi", "Walk",   "08:00", 30)  # 08:00–08:30
        e2 = self._make_entry("Mochi", "Feed",   "08:15", 30)  # 08:15–08:45  → 15 min overlap

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert len(conflicts) == 1
        assert "15 min overlap" in conflicts[0]

    def test_same_start_time_flagged(self):
        """Tasks starting at the exact same time are a conflict."""
        e1 = self._make_entry("Mochi", "Walk", "09:00", 20)
        e2 = self._make_entry("Mochi", "Feed", "09:00", 15)

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert len(conflicts) == 1

    def test_non_overlapping_tasks_no_conflict(self):
        """Back-to-back tasks that don't overlap produce no conflicts."""
        e1 = self._make_entry("Mochi", "Walk", "08:00", 30)  # ends 08:30
        e2 = self._make_entry("Mochi", "Feed", "08:30", 15)  # starts 08:30 exactly

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert conflicts == []

    def test_conflict_label_same_pet(self):
        """Overlapping tasks for the same pet get the [SAME PET] label."""
        e1 = self._make_entry("Mochi", "Walk", "10:00", 30)
        e2 = self._make_entry("Mochi", "Meds", "10:10", 20)

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert "[SAME PET]" in conflicts[0]

    def test_conflict_label_different_pets(self):
        """Overlapping tasks for different pets get the [DIFFERENT PETS] label."""
        e1 = self._make_entry("Mochi", "Walk",  "10:00", 30)
        e2 = self._make_entry("Bella", "Walk",  "10:10", 20)

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert "[DIFFERENT PETS]" in conflicts[0]

    def test_untimed_tasks_ignored_in_conflict_check(self):
        """Tasks without due_time are never flagged as conflicts."""
        e1 = self._make_entry("Mochi", "Walk",  None, 30)
        e2 = self._make_entry("Mochi", "Groom", None, 30)

        scheduler = Scheduler(make_owner())
        conflicts = scheduler.detect_conflicts([e1, e2])

        assert conflicts == []


# ---------------------------------------------------------------------------
# 4. Budget / fit_tasks edge cases
# ---------------------------------------------------------------------------

class TestFitTasks:
    def test_tasks_fit_exactly(self):
        """Tasks totaling exactly the budget are all scheduled."""
        t1 = Task(name="A", category="walk",    duration_minutes=30, priority=5)
        t2 = Task(name="B", category="feeding", duration_minutes=30, priority=4)

        scheduler = Scheduler(make_owner(minutes=60))
        scheduled, skipped = scheduler.fit_tasks([t1, t2], budget=60)

        assert len(scheduled) == 2
        assert skipped == []

    def test_task_over_budget_is_skipped(self):
        """A single task exceeding the budget lands in skipped."""
        task = Task(name="Long walk", category="walk", duration_minutes=90, priority=5)

        scheduler = Scheduler(make_owner(minutes=60))
        scheduled, skipped = scheduler.fit_tasks([task], budget=60)

        assert scheduled == []
        assert len(skipped) == 1

    def test_zero_budget_raises(self):
        scheduler = Scheduler(make_owner(minutes=1))
        with pytest.raises(ValueError):
            scheduler.fit_tasks([], budget=0)


# ---------------------------------------------------------------------------
# 5. Empty / no-pet edge cases
# ---------------------------------------------------------------------------

class TestEmptyStates:
    def test_pet_with_no_tasks_total_duration_zero(self):
        assert make_pet().total_duration() == 0

    def test_owner_with_no_pets_generates_empty_plan(self):
        owner = make_owner()
        scheduler = Scheduler(owner)
        plan = scheduler.generate_plan()

        assert plan.scheduled_entries == []
        assert plan.total_time_used == 0
        assert plan.conflicts == []


# ---------------------------------------------------------------------------
# 6. End-to-end generate_plan() integration
# ---------------------------------------------------------------------------

class TestGeneratePlan:
    def _build_scenario(self):
        """Owner with two pets, mixed tasks, 90-min budget."""
        owner = make_owner(minutes=90)

        mochi = make_pet("Mochi")
        mochi.add_task(Task(name="Morning walk", category="walk",    duration_minutes=30, priority=5, due_time="07:00"))
        mochi.add_task(Task(name="Breakfast",    category="feeding", duration_minutes=10, priority=4, due_time="08:00"))
        mochi.add_task(Task(name="Evening walk", category="walk",    duration_minutes=30, priority=3, due_time="18:00"))

        bella = make_pet("Bella")
        bella.add_task(Task(name="Meds",  category="meds",     duration_minutes=5,  priority=5, due_time="08:00"))
        bella.add_task(Task(name="Groom", category="grooming", duration_minutes=40, priority=2))

        owner.add_pet(mochi)
        owner.add_pet(bella)
        return owner

    def test_total_time_within_budget(self):
        """Scheduled tasks never exceed the owner's daily budget."""
        owner = self._build_scenario()
        plan = Scheduler(owner).generate_plan()
        assert plan.total_time_used <= owner.get_available_time()

    def test_scheduled_entries_have_pet_names(self):
        """Every ScheduledEntry carries a non-empty pet name."""
        owner = self._build_scenario()
        plan = Scheduler(owner).generate_plan()
        for entry in plan.scheduled_entries:
            assert entry.pet_name in ("Mochi", "Bella")

    def test_pet_name_filter_scopes_to_one_pet(self):
        """generate_plan(pet_name_filter=...) only includes that pet's tasks."""
        owner = self._build_scenario()
        plan = Scheduler(owner).generate_plan(pet_name_filter="Mochi")
        pet_names = {e.pet_name for e in plan.scheduled_entries}
        assert pet_names <= {"Mochi"}

    def test_high_priority_tasks_scheduled_first(self):
        """With priority-first strategy, P5 tasks appear before P2 tasks."""
        owner = self._build_scenario()
        plan = Scheduler(owner, strategy="priority-first").generate_plan()
        priorities = [e.task.priority for e in plan.scheduled_entries]
        assert priorities == sorted(priorities, reverse=True)

    def test_conflicts_surface_in_plan(self):
        """Overlapping timed tasks are reported in plan.conflicts."""
        owner = make_owner(minutes=120)
        pet = make_pet("Mochi")
        pet.add_task(Task(name="Walk", category="walk",    duration_minutes=30, priority=5, due_time="08:00"))
        pet.add_task(Task(name="Feed", category="feeding", duration_minutes=20, priority=4, due_time="08:10"))
        owner.add_pet(pet)

        plan = Scheduler(owner).generate_plan()
        assert len(plan.conflicts) >= 1


# ---------------------------------------------------------------------------
# 7. is_overdue() with mocked wall-clock time
# ---------------------------------------------------------------------------

class TestIsOverdue:
    def _task(self, due_time: str, complete: bool = False) -> Task:
        return Task(name="Walk", category="walk", duration_minutes=20,
                    priority=3, due_time=due_time, is_complete=complete)

    def test_overdue_when_past_due_time(self):
        """Task is overdue when current time is after due_time."""
        task = self._task("08:00")
        fake_now = datetime(2024, 1, 1, 9, 0, 0)   # 09:00 — past the 08:00 deadline
        with patch("pawpal_system.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = datetime.strptime
            assert task.is_overdue() is True

    def test_not_overdue_before_due_time(self):
        """Task is not overdue when current time is before due_time."""
        task = self._task("18:00")
        fake_now = datetime(2024, 1, 1, 9, 0, 0)   # 09:00 — well before 18:00
        with patch("pawpal_system.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = datetime.strptime
            assert task.is_overdue() is False

    def test_complete_task_never_overdue(self):
        """A completed task is never overdue regardless of time."""
        task = self._task("06:00", complete=True)
        fake_now = datetime(2024, 1, 1, 23, 59, 0)
        with patch("pawpal_system.datetime") as mock_dt:
            mock_dt.now.return_value = fake_now
            mock_dt.strptime.side_effect = datetime.strptime
            assert task.is_overdue() is False

    def test_no_due_time_never_overdue(self):
        """A task without due_time is never overdue."""
        task = Task(name="Walk", category="walk", duration_minutes=20, priority=3)
        assert task.is_overdue() is False


# ---------------------------------------------------------------------------
# 8. DailyPlan output — summary() and to_dict()
# ---------------------------------------------------------------------------

class TestDailyPlanOutput:
    def _make_plan(self) -> DailyPlan:
        task = Task(name="Morning walk", category="walk", duration_minutes=30,
                    priority=5, due_time="07:00", recurrence="daily")
        entry = ScheduledEntry(pet_name="Mochi", task=task)
        return DailyPlan(
            plan_date=date(2024, 6, 1),
            scheduled_entries=[entry],
            total_time_used=30,
            reasoning="Scheduled 1 task.",
            conflicts=["[SAME PET] example conflict"],
        )

    def test_summary_contains_plan_date(self):
        assert "2024-06-01" in self._make_plan().summary()

    def test_summary_contains_task_name(self):
        assert "Morning walk" in self._make_plan().summary()

    def test_summary_contains_conflict(self):
        assert "SAME PET" in self._make_plan().summary()

    def test_to_dict_keys_present(self):
        d = self._make_plan().to_dict()
        assert set(d.keys()) == {"date", "total_time_used", "reasoning",
                                 "scheduled_tasks", "conflicts"}

    def test_to_dict_task_fields(self):
        task_dict = self._make_plan().to_dict()["scheduled_tasks"][0]
        assert task_dict["pet"] == "Mochi"
        assert task_dict["task"] == "Morning walk"
        assert task_dict["duration_minutes"] == 30
        assert task_dict["recurrence"] == "daily"

    def test_to_dict_conflicts_list(self):
        assert len(self._make_plan().to_dict()["conflicts"]) == 1


# ---------------------------------------------------------------------------
# 9. weekly recur_day=None warning
# ---------------------------------------------------------------------------

class TestWeeklyMisconfiguration:
    def test_weekly_task_without_recur_day_is_excluded(self, capsys):
        """A weekly task with no recur_day is skipped and a WARNING is printed."""
        owner = make_owner()
        pet = make_pet()
        pet.add_task(Task(
            name="Bath", category="grooming",
            duration_minutes=30, priority=3,
            recurrence="weekly",   # recur_day intentionally omitted
        ))
        owner.add_pet(pet)

        plan = Scheduler(owner).generate_plan()
        captured = capsys.readouterr()

        assert plan.total_time_used == 0          # task was not scheduled
        assert "WARNING" in captured.out          # warning was printed
        assert "Bath" in captured.out
