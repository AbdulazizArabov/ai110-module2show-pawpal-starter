from __future__ import annotations
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional
import json


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

    @property
    def priority_label(self) -> str:
        """
        Return a human-readable, emoji-coded priority label.

        Mapping:
          4–5  →  🔴 High
          3    →  🟡 Medium
          1–2  →  🟢 Low

        Used by the UI to colour-code task tables without any presentation
        logic leaking into the scheduler or plan objects.
        """
        if self.priority >= 4:
            return "🔴 High"
        if self.priority == 3:
            return "🟡 Medium"
        return "🟢 Low"

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

    # ------------------------------------------------------------------
    # Persistence helpers (private)
    # ------------------------------------------------------------------

    @staticmethod
    def _task_to_dict(task: Task) -> dict:
        return {
            "name":             task.name,
            "category":         task.category,
            "duration_minutes": task.duration_minutes,
            "priority":         task.priority,
            "is_complete":      task.is_complete,
            "due_time":         task.due_time,
            "recurrence":       task.recurrence,
            "recur_day":        task.recur_day,
            "due_date":         task.due_date.isoformat() if task.due_date else None,
        }

    @staticmethod
    def _task_from_dict(d: dict) -> Task:
        return Task(
            name=d["name"],
            category=d["category"],
            duration_minutes=d["duration_minutes"],
            priority=d["priority"],
            is_complete=d.get("is_complete", False),
            due_time=d.get("due_time"),
            recurrence=d.get("recurrence"),
            recur_day=d.get("recur_day"),
            due_date=date.fromisoformat(d["due_date"]) if d.get("due_date") else None,
        )

    @staticmethod
    def _pet_to_dict(pet: Pet) -> dict:
        return {
            "name":    pet.name,
            "species": pet.species,
            "age":     pet.age,
            "tasks":   [Owner._task_to_dict(t) for t in pet.get_tasks()],
        }

    @staticmethod
    def _pet_from_dict(d: dict) -> Pet:
        pet = Pet(name=d["name"], species=d["species"], age=d["age"])
        for t_dict in d.get("tasks", []):
            pet.add_task(Owner._task_from_dict(t_dict))
        return pet

    # ------------------------------------------------------------------
    # Public persistence API
    # ------------------------------------------------------------------

    def save_to_json(self, path: str | Path = "data.json") -> None:
        """
        Serialise this Owner (including all pets and their tasks) to a
        JSON file at *path*.

        The file is written atomically via a temporary sibling so a
        crash mid-write never leaves a truncated file.  All Python
        date objects are stored as ISO-8601 strings ("YYYY-MM-DD").

        Args:
            path: Destination file path.  Defaults to "data.json" in
                  the current working directory.
        """
        payload = {
            "name":                     self.name,
            "email":                    self.email,
            "available_minutes_per_day": self.available_minutes_per_day,
            "pets": [self._pet_to_dict(p) for p in self._pets],
        }
        target = Path(path)
        tmp = target.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(target)

    @classmethod
    def load_from_json(cls, path: str | Path = "data.json") -> Owner:
        """
        Deserialise an Owner from a JSON file previously written by
        save_to_json().

        Raises FileNotFoundError if the file does not exist (caller
        should catch and fall back to a default Owner).

        Args:
            path: Source file path.  Defaults to "data.json".

        Returns:
            A fully reconstructed Owner with all pets and tasks.
        """
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        owner = cls(
            name=data["name"],
            email=data.get("email", ""),
            available_minutes_per_day=data["available_minutes_per_day"],
        )
        for p_dict in data.get("pets", []):
            owner.add_pet(cls._pet_from_dict(p_dict))
        return owner


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
        elif self.strategy == "priority-time":
            sorted_tasks = self.sort_by_priority_then_time(all_tasks)
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

    def sort_by_priority_then_time(self, tasks: list[Task]) -> list[Task]:
        """
        Sort tasks by priority descending first, then by due_minutes ascending
        as a tiebreaker within each priority band.

        This combines the two existing strategies:
          - Primary key:   -priority   (highest priority first)
          - Secondary key:  due_minutes (earliest deadline first within a band)

        Tasks with no due_time receive float("inf") as their time key so they
        fall to the end of their priority band, consistent with sort_by_time.

        Example ordering for mixed tasks:
          🔴 High  @ 09:00  →  1st   (P5, earliest in band)
          🔴 High  @ 14:00  →  2nd   (P5, later in band)
          🟡 Medium @ 08:00  →  3rd   (P3, time ignored until priority resolved)
          🟢 Low   (untimed) →  4th

        Args:
            tasks: Unsorted list of Task objects.

        Returns:
            A new list sorted priority-then-time, untimed tasks last within band.
        """
        return sorted(
            tasks,
            key=lambda t: (-t.priority, t.due_minutes or float("inf")),
        )

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
                if task.recur_day is None:
                    print(f"  WARNING: weekly task '{task.name}' has no recur_day set — skipped.")
                elif plan_date.weekday() == task.recur_day:
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
        Select the subset of tasks that maximises total priority score
        within budget using the 0/1 knapsack dynamic-programming algorithm.

        Why knapsack instead of greedy:
          A greedy approach locks in each task the moment it fits and can
          fill the budget with lower-priority tasks, leaving no room for a
          short high-priority task that appears later.  Knapsack considers
          every possible subset and returns the provably optimal selection.

        Complexity:
          Time:  O(n × budget)  — n tasks, each examined once per minute
          Space: O(n × budget)  — 2-D table for clean reconstruction
          For typical inputs (n ≤ 50, budget ≤ 480 min) this is < 25 000
          cells and runs in well under 1 ms.

        Algorithm:
          1. Build dp[i][w] = max priority achievable using the first i
             tasks with exactly w minutes or fewer available.
          2. Reconstruct the selected set by walking the table backwards:
             if dp[i][w] ≠ dp[i-1][w], task i was included.
          3. Return scheduled tasks in their original (sorted) order so the
             output respects the caller's chosen strategy.

        Args:
            tasks:  Pre-sorted list of Task objects (sort order is preserved
                    in the output but does not affect which tasks are chosen).
            budget: Available minutes (must be > 0).

        Returns:
            (scheduled, skipped) — two lists that together contain every
            input task exactly once.

        Raises:
            ValueError if budget <= 0.
        """
        if budget <= 0:
            raise ValueError(f"Budget must be > 0, got {budget}.")

        n = len(tasks)
        if n == 0:
            return [], []

        # Build DP table
        dp = [[0] * (budget + 1) for _ in range(n + 1)]
        for i, task in enumerate(tasks, 1):
            dur = task.duration_minutes
            for w in range(budget + 1):
                dp[i][w] = dp[i - 1][w]
                if w >= dur:
                    take = dp[i - 1][w - dur] + task.priority
                    if take > dp[i][w]:
                        dp[i][w] = take

        # Reconstruct selected indices (0-based)
        selected: set[int] = set()
        w = budget
        for i in range(n, 0, -1):
            if dp[i][w] != dp[i - 1][w]:
                selected.add(i - 1)
                w -= tasks[i - 1].duration_minutes

        # Preserve incoming sort order
        scheduled = [t for idx, t in enumerate(tasks) if idx in selected]
        skipped   = [t for idx, t in enumerate(tasks) if idx not in selected]
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

    def suggest_slot(
        self,
        duration_minutes: int,
        entries: list[ScheduledEntry],
        search_from: Optional[int] = None,
        day_end: int = 1439,
    ) -> Optional[str]:
        """
        Find the earliest gap in the day that can fit a task of duration_minutes
        without overlapping any already-scheduled timed entries.

        Algorithm (gap sweep):
          1. Collect occupied windows [(start_min, end_min)] from entries
             that have a due_time.  Untimed entries are ignored.
          2. Establish a cursor at search_from (default 0 = midnight).
          3. Sort windows by start_min, then scan consecutive pairs.
             For each window: if a gap of >= duration_minutes exists between
             the cursor and the window's start, return the cursor as "HH:MM".
             Otherwise advance the cursor to the window's end.
          4. After all windows, check the trailing gap to day_end.
          5. Return None if no gap fits.

        Args:
            duration_minutes: Length of the task to place (minutes > 0).
            entries:          Scheduled entries already in the plan.
            search_from:      Earliest minute to consider (0–1439).
                              Defaults to 0 (00:00) when None.
            day_end:          Last minute of the planning day (default 1439 = 23:59).

        Returns:
            "HH:MM" string of the earliest available slot, or None.

        Raises:
            ValueError if duration_minutes <= 0.
        """
        if duration_minutes <= 0:
            raise ValueError(f"duration_minutes must be > 0, got {duration_minutes}.")

        cursor = search_from if search_from is not None else 0

        # Collect and sort occupied windows for timed entries only
        windows: list[tuple[int, int]] = []
        for e in entries:
            start = e.task.due_minutes
            if start is None:
                continue
            windows.append((start, start + e.task.duration_minutes))
        windows.sort(key=lambda w: w[0])

        # Sweep gaps
        for start, end in windows:
            if start > cursor and start - cursor >= duration_minutes:
                hours, mins = divmod(cursor, 60)
                return f"{hours:02d}:{mins:02d}"
            cursor = max(cursor, end)

        # Check trailing gap after last window
        if day_end - cursor >= duration_minutes:
            hours, mins = divmod(cursor, 60)
            return f"{hours:02d}:{mins:02d}"

        return None
