from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Task — a single care activity for a pet
# ---------------------------------------------------------------------------

@dataclass
class Task:
    name: str
    category: str          # e.g. "walk", "feeding", "meds"
    duration_minutes: int
    priority: int          # 1 (lowest) – 5 (highest)
    is_complete: bool = False
    due_time: Optional[str] = None    # "HH:MM" 24-hour format, e.g. "08:00"
    recurrence: Optional[str] = None  # None | "daily" | "weekly"
    recur_day: Optional[int] = None   # 0=Mon … 6=Sun; only used when recurrence=="weekly"
    due_date: Optional[date] = None   # calendar date this instance belongs to

    def mark_done(self) -> None:
        """Mark this task as completed."""
        self.is_complete = True

    def next_occurrence(self, from_date: date) -> Optional[Task]:
        """
        Return a fresh Task for the next scheduled occurrence, or None if
        this task is not recurring.

        timedelta math:
          daily  → from_date + timedelta(days=1)   — exactly 24 hours later
          weekly → from_date + timedelta(weeks=1)  — same weekday, 7 days later

        The new instance is reset to is_complete=False and its due_date is
        set to the calculated next date.  All other fields are copied as-is.
        """
        if self.recurrence == "daily":
            next_date = from_date + timedelta(days=1)
        elif self.recurrence == "weekly":
            next_date = from_date + timedelta(weeks=1)
        else:
            return None
        return replace(self, is_complete=False, due_date=next_date)

    @property
    def due_minutes(self) -> Optional[int]:
        """
        Convert due_time from "HH:MM" string format into a plain integer
        representing minutes since midnight (e.g. "08:30" → 510).

        Returns None if due_time is not set, which tells the scheduler to
        treat this task as having no deadline and place it last in any
        time-sorted ordering.

        Used by sort_by_time() and detect_conflicts() so that neither method
        needs to call datetime.strptime() directly.
        """
        if self.due_time is None:
            return None
        dt = datetime.strptime(self.due_time, "%H:%M")
        return dt.hour * 60 + dt.minute

    def is_overdue(self) -> bool:
        """
        Return True if the task has a due_time, is not complete,
        and the current wall-clock time is past that due_time.
        """
        if self.is_complete or self.due_time is None:
            return False
        now = datetime.now().time()
        due = datetime.strptime(self.due_time, "%H:%M").time()
        return now > due


# ---------------------------------------------------------------------------
# Pet — stores a pet's profile and its list of care tasks
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Append a Task to this pet's task list."""
        self.tasks.append(task)

    def get_tasks(self) -> list[Task]:
        """Return the list of tasks for this pet."""
        return self.tasks

    def total_duration(self) -> int:
        """Return the sum of duration_minutes across all tasks."""
        return sum(t.duration_minutes for t in self.tasks)


# ---------------------------------------------------------------------------
# Owner — manages multiple pets and exposes the daily time budget
# ---------------------------------------------------------------------------

class Owner:
    def __init__(self, name: str, email: str, available_minutes_per_day: int) -> None:
        """Create an Owner with a time budget and empty pet list."""
        self.name = name
        self.email = email
        self.available_minutes_per_day = available_minutes_per_day
        self._pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a Pet to this owner's collection."""
        self._pets.append(pet)

    def get_pets(self) -> list[Pet]:
        """Return the list of pets owned."""
        return self._pets

    def get_available_time(self) -> int:
        """Return the owner's daily time budget in minutes."""
        return self.available_minutes_per_day


# ---------------------------------------------------------------------------
# ScheduledEntry — pairs a scheduled Task with the pet it belongs to,
# so DailyPlan can display "Mochi: Morning walk" rather than a nameless task.
# ---------------------------------------------------------------------------

@dataclass
class ScheduledEntry:
    pet_name: str
    task: Task


# ---------------------------------------------------------------------------
# DailyPlan — the output object produced by Scheduler
# ---------------------------------------------------------------------------

class DailyPlan:
    def __init__(
        self,
        plan_date: date,
        scheduled_entries: list[ScheduledEntry],
        total_time_used: int,
        reasoning: str,
        conflicts: Optional[list[str]] = None,
    ) -> None:
        """Create a DailyPlan describing scheduled entries, reasoning, and any conflicts."""
        self.plan_date = plan_date
        self.scheduled_entries = scheduled_entries
        self.total_time_used = total_time_used
        self.reasoning = reasoning
        self.conflicts: list[str] = conflicts or []

    def summary(self) -> str:
        """Return a human-readable summary of the plan."""
        lines = [f"PawPal+ Daily Plan — {self.plan_date}",
                 f"Total time: {self.total_time_used} min", ""]
        for entry in self.scheduled_entries:
            t = entry.task
            time_tag = f" @ {t.due_time}" if t.due_time else ""
            recur_tag = f" [{t.recurrence}]" if t.recurrence else ""
            lines.append(
                f"  [P{t.priority}] {entry.pet_name}: {t.name}"
                f" ({t.duration_minutes} min, {t.category}{time_tag}{recur_tag})"
            )
        lines += ["", f"Reasoning: {self.reasoning}"]
        if self.conflicts:
            lines += ["", "Conflicts detected:"]
            for c in self.conflicts:
                lines.append(f"  !! {c}")
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """Return the plan as a serialisable dictionary (for storage or display)."""
        return {
            "date": str(self.plan_date),
            "total_time_used": self.total_time_used,
            "reasoning": self.reasoning,
            "scheduled_tasks": [
                {
                    "pet": e.pet_name,
                    "task": e.task.name,
                    "category": e.task.category,
                    "duration_minutes": e.task.duration_minutes,
                    "priority": e.task.priority,
                    "due_time": e.task.due_time,
                    "is_complete": e.task.is_complete,
                    "recurrence": e.task.recurrence,
                }
                for e in self.scheduled_entries
            ],
            "conflicts": self.conflicts,
        }


# ---------------------------------------------------------------------------
# Scheduler — the "brain" that retrieves, organises, and fits tasks
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self, owner: Owner, strategy: str = "priority-first") -> None:
        """Initialize Scheduler referring to an owner and scheduling strategy."""
        self.owner = owner
        self.strategy = strategy  # "priority-first" (only supported strategy for now)

    def mark_task_complete(self, task_name: str, pet: Pet) -> Optional[Task]:
        """
        Mark the first pending task matching task_name as done.

        If the task is recurring, next_occurrence() is called with today's
        date to produce a new instance (due_date = today + timedelta(days=1)
        for daily, or today + timedelta(weeks=1) for weekly).  That new
        instance is automatically added to the pet's task list.

        Returns the newly created Task, or None for non-recurring tasks.
        Raises ValueError if no matching pending task is found.
        """
        for task in pet.get_tasks():
            if task.name == task_name and not task.is_complete:
                task.mark_done()
                next_task = task.next_occurrence(date.today())
                if next_task is not None:
                    pet.add_task(next_task)
                return next_task
        raise ValueError(f"No pending task '{task_name}' found for {pet.name}.")

    def generate_plan(
        self,
        pet_name_filter: Optional[str] = None,
        include_complete: bool = False,
    ) -> DailyPlan:
        """
        Build and return a DailyPlan for the owner's pets.

        Flow:
          1. Collect incomplete tasks (or all, if include_complete=True),
             optionally scoped to a single pet via pet_name_filter.
          2. Expand recurring tasks into fresh per-day copies.
          3. Sort by strategy ("priority-first" or "time-first").
          4. Fit within budget → (scheduled, skipped).
          5. Re-attach pet names via ScheduledEntry.
          6. Detect overlapping time-window conflicts.
          7. Produce plain-English reasoning.
          8. Return DailyPlan.
        """
        today = date.today()

        # Step 1 — collect tasks, respecting filters
        pet_of: dict[int, str] = {}
        all_tasks: list[Task] = []
        for pet in self.owner.get_pets():
            if pet_name_filter is not None and pet.name != pet_name_filter:
                continue
            for task in pet.get_tasks():
                if not include_complete and task.is_complete:
                    continue
                pet_of[id(task)] = pet.name
                all_tasks.append(task)

        # Step 2 — expand recurring tasks into today's concrete copies
        all_tasks = self.expand_recurring(all_tasks, pet_of, today)

        # Step 3 — sort
        if self.strategy == "time-first":
            sorted_tasks = self.sort_by_time(all_tasks)
        else:
            sorted_tasks = self.sort_by_priority(all_tasks)

        # Step 4 — fit within budget
        budget = self.owner.get_available_time()
        scheduled, skipped = self.fit_tasks(sorted_tasks, budget)

        # Step 5 — pair tasks back with their pet names
        entries = [ScheduledEntry(pet_name=pet_of[id(t)], task=t) for t in scheduled]

        # Step 6 — detect conflicts and print warnings (never raises)
        conflicts = self.detect_conflicts(entries)
        if conflicts:
            self.warn_conflicts(conflicts)

        # Step 7 — explain
        reasoning = self.explain_reasoning(scheduled, skipped)

        # Step 8 — assemble and return
        total_time = sum(t.duration_minutes for t in scheduled)
        return DailyPlan(
            plan_date=today,
            scheduled_entries=entries,
            total_time_used=total_time,
            reasoning=reasoning,
            conflicts=conflicts,
        )

    def sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return a new list of tasks sorted by priority descending (5 first)."""
        return sorted(tasks, key=lambda t: t.priority, reverse=True)

    def sort_by_time(self, tasks: list[Task]) -> list[Task]:
        """
        Sort tasks using the Earliest Deadline First (EDF) algorithm.

        Tasks are ordered by due_minutes ascending so the task with the
        closest deadline is always scheduled first.  Tasks with no due_time
        receive float("inf") as their sort key, which pushes them naturally
        to the end of the list without any special-case branching.

        When two tasks share the same due_time, the one with the higher
        priority score wins the tiebreak (achieved by sorting on -priority).

        Args:
            tasks: Unsorted list of Task objects.

        Returns:
            A new list sorted earliest-deadline first, untimed tasks last.
        """
        return sorted(tasks, key=lambda t: (t.due_minutes or float("inf"), -t.priority))

    def filter_tasks(
        self,
        pet_name: Optional[str] = None,
        is_complete: Optional[bool] = None,
    ) -> list[Task]:
        """
        Return a filtered view of tasks across all pets owned by this Scheduler's owner.

        Both filters are optional and can be combined:
          - pet_name:    when provided, only tasks belonging to that pet are included.
          - is_complete: when True, returns only completed tasks; when False, returns
                         only pending tasks; when None (default), returns all tasks
                         regardless of completion status.

        This method does not modify any task or pet — it only reads and filters.

        Args:
            pet_name:    Name of the pet to filter by, or None for all pets.
            is_complete: Completion status to filter by, or None for no filter.

        Returns:
            List of matching Task objects in their original insertion order.
        """
        results: list[Task] = []
        for pet in self.owner.get_pets():
            if pet_name is not None and pet.name != pet_name:
                continue
            for task in pet.get_tasks():
                if is_complete is not None and task.is_complete != is_complete:
                    continue
                results.append(task)
        return results

    def expand_recurring(
        self,
        tasks: list[Task],
        pet_of: dict[int, str],
        plan_date: date,
    ) -> list[Task]:
        """
        Expand recurring task templates into concrete instances for plan_date.

        Each recurring task is replaced by a fresh copy produced with
        dataclasses.replace(), resetting is_complete to False so previous
        completions never carry over into today's plan.  The original template
        object is left untouched in pet.tasks.

        Recurrence rules:
          - "daily":  always included; copied on every call.
          - "weekly": only included when plan_date.weekday() == task.recur_day,
                      so the task appears on the correct day of the week.
          - None:     task is passed through unchanged.

        The pet_of mapping is updated with the new copy's id so that
        generate_plan() can still look up which pet each task belongs to.

        Args:
            tasks:     Flat list of tasks already collected from all pets.
            pet_of:    Dict mapping id(task) → pet name; mutated in place for copies.
            plan_date: The date being planned (usually date.today()).

        Returns:
            New list with recurring tasks replaced by their per-day copies.
        """
        expanded: list[Task] = []
        for task in tasks:
            if task.recurrence is None:
                expanded.append(task)
            elif task.recurrence == "daily":
                copy = replace(task, is_complete=False)
                pet_of[id(copy)] = pet_of[id(task)]
                expanded.append(copy)
            elif task.recurrence == "weekly":
                if task.recur_day is not None and plan_date.weekday() == task.recur_day:
                    copy = replace(task, is_complete=False)
                    pet_of[id(copy)] = pet_of[id(task)]
                    expanded.append(copy)
        return expanded

    def detect_conflicts(self, entries: list[ScheduledEntry]) -> list[str]:
        """
        Scan scheduled entries for overlapping time windows and return warning messages.

        Strategy (lightweight sweep):
          1. Build a list of (entry, start_min, end_min) tuples for every entry
             that has a due_time.  Entries without a due_time are ignored.
          2. Sort by start_min ascending.
          3. For each entry i, compare against every subsequent entry j until
             j.start >= i.end — at that point no further overlap is possible
             (because the list is sorted), so the inner loop breaks early.
          4. For each overlapping pair, compute the overlap duration and label
             the conflict as [SAME PET] or [DIFFERENT PETS].

        This method never raises and never modifies any task or entry.
        The scheduler continues to completion regardless of how many conflicts
        are found — conflicts are warnings, not errors.

        Args:
            entries: List of ScheduledEntry objects from the current plan.

        Returns:
            List of human-readable conflict warning strings, empty if none found.
        """
        timed: list[tuple[ScheduledEntry, int, int]] = []
        for e in entries:
            start = e.task.due_minutes
            if start is None:
                continue
            end = start + e.task.duration_minutes
            timed.append((e, start, end))

        timed.sort(key=lambda x: x[1])

        conflicts: list[str] = []
        for i in range(len(timed)):
            e1, _, end1 = timed[i]
            for j in range(i + 1, len(timed)):
                e2, s2, end2 = timed[j]
                if s2 >= end1:
                    break  # sorted by start; no later task can overlap e1
                overlap_mins = min(end1, end2) - s2
                label = "[SAME PET]" if e1.pet_name == e2.pet_name else "[DIFFERENT PETS]"
                conflicts.append(
                    f"{label} {e1.pet_name}: '{e1.task.name}'"
                    f" ({e1.task.due_time}, {e1.task.duration_minutes} min)"
                    f" overlaps {e2.pet_name}: '{e2.task.name}'"
                    f" ({e2.task.due_time}, {e2.task.duration_minutes} min)"
                    f" — {overlap_mins} min overlap"
                )
        return conflicts

    def warn_conflicts(self, conflicts: list[str]) -> None:
        """
        Print a WARNING line to stdout for every conflict detected.
        Lightweight — never raises, never modifies state.
        """
        for msg in conflicts:
            print(f"  WARNING: {msg}")

    def fit_tasks(
        self, tasks: list[Task], budget: int
    ) -> tuple[list[Task], list[Task]]:
        """
        Greedily select tasks that fit within budget (minutes).
        Returns (scheduled, skipped).
        Raises ValueError if budget <= 0.
        """
        if budget <= 0:
            raise ValueError(f"Budget must be > 0, got {budget}.")
        scheduled: list[Task] = []
        skipped: list[Task] = []
        time_used = 0
        for task in tasks:
            if time_used + task.duration_minutes <= budget:
                scheduled.append(task)
                time_used += task.duration_minutes
            else:
                skipped.append(task)
        return scheduled, skipped

    def explain_reasoning(
        self, scheduled: list[Task], skipped: list[Task]
    ) -> str:
        """Produce a plain-English explanation of scheduling decisions."""
        lines: list[str] = []

        if scheduled:
            lines.append(f"Scheduled {len(scheduled)} task(s):")
            for t in scheduled:
                lines.append(
                    f"  - {t.name} (priority {t.priority}, {t.duration_minutes} min)"
                )
        else:
            lines.append("No tasks fit within the available time budget.")

        if skipped:
            lines.append(f"Skipped {len(skipped)} task(s) — not enough time remaining:")
            for t in skipped:
                lines.append(
                    f"  - {t.name} (priority {t.priority}, {t.duration_minutes} min)"
                )

        return "\n".join(lines)
