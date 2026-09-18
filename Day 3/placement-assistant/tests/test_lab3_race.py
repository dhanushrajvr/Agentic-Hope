"""Lab 3 — two runs booking the same slot; one wins cleanly.

TODO: write these tests yourself. Delete the skip line when you start.

1. test_two_workers_two_runs_one_slot
   Two students who are both eligible for TCS (22IT017 and 22CS045) each get a thread and a queued run.
   Each run applies to drive 2 and books slot 3 (build the model turns with PositionalMock).
   Use two RunStore and two PlacementDb connections on the same files (the db_files fixture), and one Worker
   per connection. Assert: both runs SUCCEED (losing a race is not a crash), exactly one book_interview_slot
   result is "booked", the other is the "slot_taken" error, and slot 3 holds exactly one student.

2. test_truly_concurrent_claims_have_one_winner
   Both students apply to drive 2. Read slot 3's version once. Start 8 threads, each with its OWN
   PlacementDb connection, held at a threading.Barrier, then all call claim_slot(3, student, version).
   Assert exactly one True, seven False, and the version went up by exactly one.
"""

import threading

from app.memory import RunStore
from app.placement_db import PlacementDb
from app.providers import ModelTurn, PositionalMock, ToolCall
from app.worker import Worker


def _turns_for(student_id: str, slot_id: int, drive_id: int):
    return [
        ModelTurn(
            text=None,
            tool_calls=[ToolCall("check_eligibility", {"student_id": student_id, "drive_id": drive_id})],
            tokens_in=120,
            tokens_out=12,
        ),
        ModelTurn(
            text=None,
            tool_calls=[ToolCall("apply_to_drive", {"student_id": student_id, "drive_id": drive_id})],
            tokens_in=140,
            tokens_out=15,
        ),
        ModelTurn(
            text=None,
            tool_calls=[ToolCall("book_interview_slot", {"student_id": student_id, "slot_id": slot_id})],
            tokens_in=180,
            tokens_out=18,
        ),
        ModelTurn(text="(mock) done", tokens_in=200, tokens_out=10),
    ]


def test_two_workers_two_runs_one_slot(db_files, clock):
    agent_path, placement_path = db_files
    store_a = RunStore(agent_path, clock)
    store_b = RunStore(agent_path, clock)
    place_a = PlacementDb(placement_path)
    place_b = PlacementDb(placement_path)

    thread_1 = store_a.create_thread("22IT017")
    thread_2 = store_b.create_thread("22CS045")
    run_1 = store_a.enqueue(thread_1, "Apply me to TCS and book slot 3.", "mock", max_attempts=3)
    run_2 = store_b.enqueue(thread_2, "Apply me to TCS and book slot 3.", "mock", max_attempts=3)

    worker_1 = Worker(store_a, place_a, PositionalMock(_turns_for("22IT017", 3, 2)), worker_id="w1")
    worker_2 = Worker(store_b, place_b, PositionalMock(_turns_for("22CS045", 3, 2)), worker_id="w2")

    outcomes = []

    def run_worker(worker):
        outcomes.append(worker.run_until_idle())

    threads = [
        threading.Thread(target=run_worker, args=(worker_1,)),
        threading.Thread(target=run_worker, args=(worker_2,)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    flat = [item for items in outcomes for item in items]
    assert sorted(item[1] for item in flat) == ["succeeded", "succeeded"]

    run_one_steps = store_a.get_run(run_1)["steps"]
    run_two_steps = store_b.get_run(run_2)["steps"]
    booking_results = [
        step["result"]
        for steps in (run_one_steps, run_two_steps)
        for step in steps
        if step.get("kind") == "tool" and step.get("tool_name") == "book_interview_slot"
    ]

    assert len(booking_results) == 2
    assert sum(1 for result in booking_results if result.get("status") == "booked") == 1
    assert sum(1 for result in booking_results if result.get("error") == "slot_taken") == 1

    slot_row = PlacementDb(placement_path).conn.execute(
        "SELECT count(*) FROM interview_slot WHERE id = 3 AND student_id IS NOT NULL"
    ).fetchone()[0]
    assert slot_row == 1


def test_truly_concurrent_claims_have_one_winner(db_files):
    _, placement_path = db_files
    placement = PlacementDb(placement_path)
    initial_version = placement.slot_version(3)
    assert initial_version == 0

    barrier = threading.Barrier(8)
    results = []

    def claimant(student_id: int):
        local = PlacementDb(placement_path)
        barrier.wait()
        results.append(local.claim_slot(3, student_id, initial_version))

    threads = [
        threading.Thread(target=claimant, args=(student_id,))
        for student_id in (1, 2, 1, 2, 1, 2, 1, 2)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert sum(results) == 1
    assert len(results) - sum(results) == 7
    assert PlacementDb(placement_path).slot_version(3) == 1

import pytest

pytest.skip("lab 3: write these tests", allow_module_level=True)
