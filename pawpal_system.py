from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# Task
# ---------------------------------------------------------------------------

@dataclass
class Task:
    name: str
    category: str          # e.g. "walk", "feeding", "meds"
    duration_minutes: int
    priority: int          # 1 (lowest) – 5 (highest)
    is_complete: bool = False
    due_time: Optional[str] = None   # e.g. "08:00", used for overdue check

    def mark_done(self) -> None:
        """Mark this task as completed."""
        pass

    def is_overdue(self) -> bool:
        """Return True if the task is past its due time and not yet complete."""
        pass


# ---------------------------------------------------------------------------
# Pet
# ---------------------------------------------------------------------------

@dataclass
class Pet:
    name: str
    species: str
    age: int
    tasks: list[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Append a Task to this pet's task list."""
        pass

    def get_tasks(self) -> list[Task]:
        """Return the list of tasks for this pet."""
        pass

    def total_duration(self) -> int:
        """Return the sum of duration_minutes across all tasks."""
        pass


# ---------------------------------------------------------------------------
# Owner
# ---------------------------------------------------------------------------

class Owner:
    def __init__(self, name: str, email: str, available_minutes_per_day: int) -> None:
        self.name = name
        self.email = email
        self.available_minutes_per_day = available_minutes_per_day
        self._pets: list[Pet] = []

    def add_pet(self, pet: Pet) -> None:
        """Add a Pet to this owner's collection."""
        pass

    def get_pets(self) -> list[Pet]:
        """Return the list of pets owned."""
        pass

    def get_available_time(self) -> int:
        """Return the owner's daily time budget in minutes."""
        pass


# ---------------------------------------------------------------------------
# DailyPlan
# ---------------------------------------------------------------------------

class DailyPlan:
    def __init__(
        self,
        plan_date: date,
        scheduled_tasks: list[Task],
        total_time_used: int,
        reasoning: str,
    ) -> None:
        self.plan_date = plan_date
        self.scheduled_tasks = scheduled_tasks
        self.total_time_used = total_time_used
        self.reasoning = reasoning

    def summary(self) -> str:
        """Return a human-readable summary of the plan."""
        pass

    def to_dict(self) -> dict:
        """Return the plan as a dictionary (for storage or display)."""
        pass


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class Scheduler:
    def __init__(self, owner: Owner, strategy: str = "priority-first") -> None:
        self.owner = owner
        self.strategy = strategy  # e.g. "priority-first"

    def generate_plan(self) -> DailyPlan:
        """Build and return a DailyPlan for the owner's pets."""
        pass

    def sort_by_priority(self, tasks: list[Task]) -> list[Task]:
        """Return tasks sorted by priority descending (highest first)."""
        pass

    def fit_tasks(self, tasks: list[Task], budget: int) -> list[Task]:
        """Select tasks that fit within the given time budget."""
        pass

    def explain_reasoning(self, scheduled: list[Task], skipped: list[Task]) -> str:
        """Produce a plain-English explanation of why tasks were included or skipped."""
        pass

    def export_plan(self, plan: DailyPlan) -> dict:
        """Export the plan to a serialisable dictionary."""
        pass
