from pawpal_system import Owner, Pet, Task, Scheduler

# --- Owner ---
jordan = Owner(name="Jordan", email="jordan@email.com", available_minutes_per_day=90)

# --- Pets ---
mochi = Pet(name="Mochi", species="dog", age=3)
luna  = Pet(name="Luna",  species="cat", age=5)

# --- Tasks for Mochi ---
mochi.add_task(Task(name="Morning walk",   category="walk",    duration_minutes=30, priority=5, due_time="08:00"))
mochi.add_task(Task(name="Breakfast",      category="feeding", duration_minutes=10, priority=4))

# --- Tasks for Luna ---
luna.add_task(Task(name="Medication dose", category="meds",    duration_minutes=5,  priority=5, due_time="09:00"))
luna.add_task(Task(name="Playtime",        category="play",    duration_minutes=20, priority=2))
luna.add_task(Task(name="Dinner",          category="feeding", duration_minutes=10, priority=4))

# --- Register pets with owner ---
jordan.add_pet(mochi)
jordan.add_pet(luna)

# --- Generate schedule ---
scheduler = Scheduler(owner=jordan, strategy="priority-first")
plan = scheduler.generate_plan()

# --- Print results ---
print("=" * 50)
print("         TODAY'S SCHEDULE")
print("=" * 50)
print(plan.summary())
print("=" * 50)
