from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date, datetime
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
    due_time: Optional[str] = None  # "HH:MM" 24-hour format, e.g. "08:00"

    def mark_done(self) -> None:
        """Mark this task as completed."""
        self.is_complete = True

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
    ) -> None:
        """Create a DailyPlan describing scheduled entries and reasoning."""
        self.plan_date = plan_date
        self.scheduled_entries = scheduled_entries
        self.total_time_used = total_time_used
        self.reasoning = reasoning

    def summary(self) -> str:
        """Return a human-readable summary of the plan."""
        lines = [f"PawPal+ Daily Plan — {self.plan_date}",
                 f"Total time: {self.total_time_used} min", ""]
        for entry in self.scheduled_entries:
            t = entry.task
            lines.append(
                f"  [P{t.priority}] {entry.pet_name}: {t.name}"
                f" ({t.duration_minutes} min, {t.category})"
            )
        lines += ["", f"Reasoning: {self.reasoning}"]
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
                    "is_complete": e.task.is_complete,
                }
                for e in self.scheduled_entries
            ],
        }


# ---------------------------------------------------------------------------
# Scheduler — the "brain" that retrieves, organises, and fits tasks
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self, owner: Owner, strategy: str = "priority-first") -> None:
        """Initialize Scheduler referring to an owner and scheduling strategy."""
        self.owner = owner
        self.strategy = strategy  # "priority-first" (only supported strategy for now)

    def generate_plan(self) -> DailyPlan:
        """
        Build and return a DailyPlan for the owner's pets.

        Flow:
          1. Walk owner → pets → tasks, building a {task_id: pet_name} map.
          2. Sort all tasks by priority (highest first).
          3. Fit sorted tasks within the owner's time budget → (scheduled, skipped).
          4. Re-attach pet names via ScheduledEntry.
          5. Produce plain-English reasoning.
          6. Return DailyPlan.
        """
        # Step 1 — collect all tasks, remembering which pet each belongs to
        pet_of: dict[int, str] = {}
        all_tasks: list[Task] = []
        for pet in self.owner.get_pets():
            for task in pet.get_tasks():
                pet_of[id(task)] = pet.name
                all_tasks.append(task)

        # Step 2 — sort
        sorted_tasks = self.sort_by_priority(all_tasks)

        # Step 3 — fit within budget
        budget = self.owner.get_available_time()
        scheduled, skipped = self.fit_tasks(sorted_tasks, budget)

        # Step 4 — pair tasks back with their pet names
        entries = [ScheduledEntry(pet_name=pet_of[id(t)], task=t) for t in scheduled]

        # Step 5 — explain
        reasoning = self.explain_reasoning(scheduled, skipped)

        # Step 6 — assemble and return
        total_time = sum(t.duration_minutes for t in scheduled)
        return DailyPlan(
            plan_date=date.today(),
            scheduled_entries=entries,
            total_time_used=total_time,
            reasoning=reasoning,
        )

    def sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return a new list of tasks sorted by priority descending (5 first)."""
        return sorted(tasks, key=lambda t: t.priority, reverse=True)

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
