# PawPal+ (Module 2 Project)

You are building **PawPal+**, a Streamlit app that helps a pet owner plan care tasks for their pet.

## Scenario

A busy pet owner needs help staying consistent with pet care. They want an assistant that can:

- Track pet care tasks (walks, feeding, meds, enrichment, grooming, etc.)
- Consider constraints (time available, priority, owner preferences)
- Produce a daily plan and explain why it chose that plan

Your job is to design the system first (UML), then implement the logic in Python, then connect it to the Streamlit UI.

## What you will build

Your final app should:

- Let a user enter basic owner + pet info
- Let a user add/edit tasks (duration + priority at minimum)
- Generate a daily schedule/plan based on constraints and priorities
- Display the plan clearly (and ideally explain the reasoning)
- Include tests for the most important scheduling behaviors

## Smarter Scheduling

Beyond the basic priority-first plan, PawPal+ includes several algorithmic improvements built directly into `pawpal_system.py`:

### Earliest Deadline First (`sort_by_time`)
Tasks with a `due_time` are sorted chronologically using the classic EDF algorithm. The sort key is `Task.due_minutes` — a cached property that converts `"HH:MM"` into minutes since midnight once, avoiding repeated string parsing. Tasks without a deadline receive `float("inf")` and naturally fall to the end. Activate it with `Scheduler(strategy="time-first")`.

### Filtering (`filter_tasks`)
Tasks can be filtered by pet name, completion status, or both — without generating a full plan. Useful for displaying a single pet's pending tasks in the UI or checking what has already been done today.

### Recurring Tasks (`expand_recurring`)
Tasks marked `recurrence="daily"` or `recurrence="weekly"` are treated as templates. Each time a plan is generated, fresh copies are created with `is_complete=False` so the original is never mutated. Weekly tasks only appear on the matching day of the week (`recur_day=0` for Monday through `6` for Sunday).

### Auto-scheduling Next Occurrence (`mark_task_complete`)
Completing a recurring task via `Scheduler.mark_task_complete()` automatically creates the next instance using Python's `timedelta`:
- Daily → `due_date = today + timedelta(days=1)`
- Weekly → `due_date = today + timedelta(weeks=1)`

The new instance is added directly to the pet's task list, ready for the next plan.

### Conflict Detection (`detect_conflicts`)
After scheduling, the planner checks every pair of timed tasks for overlapping windows using a lightweight sweep. Each conflict is labelled `[SAME PET]` or `[DIFFERENT PETS]`, includes the exact overlap duration in minutes, and prints as a `WARNING` line. The scheduler never crashes — conflicts are informational, not errors.

---

## Getting started

### Setup

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Suggested workflow

1. Read the scenario carefully and identify requirements and edge cases.
2. Draft a UML diagram (classes, attributes, methods, relationships).
3. Convert UML into Python class stubs (no logic yet).
4. Implement scheduling logic in small increments.
5. Add tests to verify key behaviors.
6. Connect your logic to the Streamlit UI in `app.py`.
7. Refine UML so it matches what you actually built.
