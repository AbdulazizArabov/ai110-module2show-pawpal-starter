import streamlit as st
from pawpal_system import Owner, Pet, Task, Scheduler, DailyPlan, ScheduledEntry

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")

st.markdown(
    """
Welcome to the PawPal+ starter app.

This file is intentionally thin. It gives you a working Streamlit app so you can start quickly,
but **it does not implement the project logic**. Your job is to design the system and build it.

Use this app as your interactive demo once your backend classes/functions exist.
"""
)

with st.expander("Scenario", expanded=True):
    st.markdown(
        """
**PawPal+** is a pet care planning assistant. It helps a pet owner plan care tasks
for their pet(s) based on constraints like time, priority, and preferences.

You will design and implement the scheduling logic and connect it to this Streamlit UI.
"""
    )

with st.expander("What you need to build", expanded=True):
    st.markdown(
        """
At minimum, your system should:
- Represent pet care tasks (what needs to happen, how long it takes, priority)
- Represent the pet and the owner (basic info and preferences)
- Build a plan/schedule for a day that chooses and orders tasks based on constraints
- Explain the plan (why each task was chosen and when it happens)
"""
    )

st.divider()

# ---------------------------------------------------------------------------
# Owner setup — persists across reruns via session_state
# ---------------------------------------------------------------------------
st.subheader("Owner")
owner_name        = st.text_input("Your name", value="Jordan")
available_minutes = st.number_input("Available minutes per day", min_value=1, max_value=480, value=90)

if "owner" not in st.session_state:
    st.session_state.owner = Owner(owner_name, "", int(available_minutes))

# ---------------------------------------------------------------------------
# Add a Pet — calls Owner.add_pet()
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Add a Pet")

col1, col2, col3 = st.columns(3)
with col1:
    pet_name = st.text_input("Pet name", value="Mochi")
with col2:
    species = st.selectbox("Species", ["dog", "cat", "other"])
with col3:
    age = st.number_input("Age", min_value=0, max_value=30, value=3)

if st.button("Add pet"):
    pet = Pet(name=pet_name, species=species, age=int(age))
    st.session_state.owner.add_pet(pet)   # Owner.add_pet() called here
    st.success(f"{pet_name} added!")

# Show all pets currently registered
pets = st.session_state.owner.get_pets()  # Owner.get_pets() drives the UI
if pets:
    st.write("**Your pets:**")
    for p in pets:
        st.write(f"- {p.name} ({p.species}, age {p.age}) — {p.total_duration()} min of tasks")
else:
    st.info("No pets yet. Add one above.")

# ---------------------------------------------------------------------------
# Add a Task — calls Pet.add_task() on the selected pet
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Add a Task")

pet_names = [p.name for p in st.session_state.owner.get_pets()]

if not pet_names:
    st.info("Add a pet first before adding tasks.")
else:
    selected_pet_name = st.selectbox("Select pet", pet_names)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        task_title = st.text_input("Task title", value="Morning walk")
    with col2:
        category = st.selectbox("Category", ["walk", "feeding", "meds", "play", "grooming"])
    with col3:
        duration = st.number_input("Duration (min)", min_value=1, max_value=240, value=20)
    with col4:
        priority = st.selectbox("Priority (1–5)", [1, 2, 3, 4, 5], index=4)

    if st.button("Add task"):
        # Locate the chosen pet and call its add_task() method
        target_pet = next(p for p in st.session_state.owner.get_pets()
                          if p.name == selected_pet_name)
        task = Task(name=task_title, category=category,
                    duration_minutes=int(duration), priority=int(priority))
        target_pet.add_task(task)          # Pet.add_task() called here
        st.success(f"'{task_title}' added to {selected_pet_name}!")

    # Show tasks grouped by pet — driven by pet.get_tasks()
    st.markdown("**Current tasks by pet:**")
    any_tasks = False
    for p in st.session_state.owner.get_pets():
        if p.get_tasks():
            any_tasks = True
            st.write(f"**{p.name}** — {p.total_duration()} min total")
            st.table([
                {"task": t.name, "category": t.category,
                 "duration (min)": t.duration_minutes, "priority": t.priority}
                for t in p.get_tasks()
            ])
    if not any_tasks:
        st.info("No tasks yet.")

# ---------------------------------------------------------------------------
# Generate Schedule — calls Scheduler.generate_plan()
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Build Schedule")

if st.button("Generate schedule"):
    all_pets_have_tasks = any(p.get_tasks() for p in st.session_state.owner.get_pets())
    if not all_pets_have_tasks:
        st.warning("Add at least one task before generating a schedule.")
    else:
        scheduler = Scheduler(owner=st.session_state.owner, strategy="priority-first")
        plan      = scheduler.generate_plan()
        st.success("Schedule generated!")
        st.text(plan.summary())
