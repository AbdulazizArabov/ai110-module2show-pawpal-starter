from pawpal_system import Owner, Pet, Task, Scheduler

# ---------------------------------------------------------------------------
# Setup — deliberately overlapping tasks to trigger both conflict types
# ---------------------------------------------------------------------------
jordan = Owner(name="Jordan", email="jordan@email.com", available_minutes_per_day=180)

mochi = Pet(name="Mochi", species="dog", age=3)
luna  = Pet(name="Luna",  species="cat", age=5)

# --- Mochi's tasks ---
# Two tasks for the SAME PET at the same time → [SAME PET] conflict
mochi.add_task(Task(name="Morning walk",  category="walk",    duration_minutes=30, priority=5, due_time="08:00"))
mochi.add_task(Task(name="Breakfast",     category="feeding", duration_minutes=10, priority=4, due_time="08:15"))  # starts inside Morning walk → SAME PET overlap

# A task that ends before Luna's task starts → no conflict expected
mochi.add_task(Task(name="Grooming",      category="grooming",duration_minutes=20, priority=2, due_time="11:00"))

# --- Luna's tasks ---
# Overlaps Mochi's Morning walk → [DIFFERENT PETS] conflict
luna.add_task(Task(name="Medication dose",category="meds",    duration_minutes=5,  priority=5, due_time="08:10"))

# Exactly back-to-back with Grooming (ends 11:20, this starts 11:20) → NO conflict
luna.add_task(Task(name="Playtime",       category="play",    duration_minutes=20, priority=3, due_time="11:20"))

jordan.add_pet(mochi)
jordan.add_pet(luna)

# ---------------------------------------------------------------------------
# Run scheduler — warnings print automatically inside generate_plan
# ---------------------------------------------------------------------------
scheduler = Scheduler(owner=jordan, strategy="time-first")

print("=" * 60)
print("  Generating schedule — conflicts print as WARNING lines")
print("=" * 60)
plan = scheduler.generate_plan()

# ---------------------------------------------------------------------------
# Print the full plan (conflicts also appear at the bottom of summary)
# ---------------------------------------------------------------------------
print()
print(plan.summary())

# ---------------------------------------------------------------------------
# Show the stored conflict list directly for verification
# ---------------------------------------------------------------------------
print("\n" + "=" * 60)
print(f"  plan.conflicts contains {len(plan.conflicts)} conflict(s):")
print("=" * 60)
for i, c in enumerate(plan.conflicts, 1):
    print(f"  {i}. {c}")

print()
print("No exception was raised — detection is lightweight (warn only).")
