from pawpal_system import Task, Pet


def test_mark_done_sets_complete():
    task = Task(name="Morning walk", category="walk", duration_minutes=30, priority=5)
    task.mark_done()
    assert task.is_complete is True


def test_add_task_increases_pet_task_count():
    pet = Pet(name="Mochi", species="dog", age=3)
    task = Task(name="Breakfast", category="feeding", duration_minutes=10, priority=4)
    pet.add_task(task)
    assert len(pet.get_tasks()) == 1
