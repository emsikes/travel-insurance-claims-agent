import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import claim, queue_agent
from agent.tests.conftest import StubModel, decide_and_pay, stub, tool_call


@pytest.fixture(autouse=True)
def no_retries(monkeypatch):
    monkeypatch.setattr(claim, "MAX_RETRIES", 0)


def claim_models(scripts: dict[str, list[StubModel]]):
    return lambda claim_id: scripts[claim_id].pop(0)


def work(claim_id: str) -> AIMessage:
    return tool_call("work_claim", f"work-{claim_id}", claim_id=claim_id)


def failing() -> StubModel:
    return stub(failures=1)


def tool_results(model: StubModel) -> list[str]:
    return [str(m.content) for m in model.seen[-1] if isinstance(m, ToolMessage)]


def get(api, claim_id: str) -> dict:
    return api.get(f"/api/claims/{claim_id}").json()


def test_to_do_list_is_stored(api):
    todo = {"claim_id": "CLM-1001", "content": "CLM-1001: stolen bag"}
    queue = stub(
        tool_call("list_waiting_claims", "1"),
        tool_call("write_todos", "2", todos=[{**todo, "status": "to_do"}]),
        work("CLM-1001"),
        tool_call("write_todos", "3", todos=[{**todo, "status": "done"}]),
        AIMessage(content="One claim approved."),
    )
    summary = queue_agent.run_queue(
        1, queue, claim_models({"CLM-1001": [stub(*decide_and_pay("CLM-1001"))]})
    )

    assert summary == "One claim approved."
    run = api.get("/api/runs/latest").json()
    assert run["todos"] == [{**todo, "status": "done"}]
    assert run["status"] == "finished"
    assert run["summary"] == "One claim approved."
    assert "CLM-1001" in tool_results(queue)[0]


def test_a_to_do_item_need_not_be_a_claim(api):
    queue = stub(
        tool_call(
            "write_todos",
            "1",
            todos=[{"claim_id": "", "content": "x", "status": "to_do"}],
        ),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(0, queue)
    assert tool_results(queue) == ["Updated the to-do list."]


def test_the_cap_limits_the_run(api):
    queue = stub(
        work("CLM-1002"),
        work("CLM-1003"),
        work("CLM-1004"),
        AIMessage(content="Two claims worked."),
    )
    queue_agent.run_queue(
        2,
        queue,
        claim_models(
            {
                "CLM-1002": [stub(*decide_and_pay("CLM-1002"))],
                "CLM-1003": [stub(*decide_and_pay("CLM-1003"))],
            }
        ),
    )
    assert tool_results(queue)[-1] == (
        "CLM-1004 not started: the cap of 2 claims is reached"
    )
    assert get(api, "CLM-1002")["status"] == "decided"
    assert get(api, "CLM-1004")["status"] == "waiting"
    waiting = [c for c in api.get("/api/claims").json() if c["status"] == "waiting"]
    assert len(waiting) == 22


def test_a_claim_that_was_not_started_does_not_count_against_the_cap(api):
    queue = stub(
        work("CLM-1001"),
        work("CLM-1013"),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(
        1,
        queue,
        claim_models(
            {"CLM-1001": [stub()], "CLM-1013": [stub(*decide_and_pay("CLM-1013"))]}
        ),
    )
    assert tool_results(queue)[0].startswith("CLM-1001 not started")
    assert get(api, "CLM-1013")["status"] == "decided"


def test_a_failed_claim_does_not_stop_the_run(api):
    queue = stub(
        work("CLM-1005"),
        work("CLM-1006"),
        AIMessage(content="Done."),
        work("CLM-1005"),
        AIMessage(content="One decided, one left for a handler."),
    )
    summary = queue_agent.run_queue(
        2,
        queue,
        claim_models(
            {
                "CLM-1005": [failing(), failing()],
                "CLM-1006": [stub(*decide_and_pay("CLM-1006"))],
            }
        ),
    )
    assert summary == "One decided, one left for a handler."
    assert get(api, "CLM-1006")["status"] == "decided"
    assert api.get("/api/runs/latest").json()["status"] == "finished"


def test_a_failed_claim_goes_back_in_the_queue_and_is_tried_again(api):
    queue = stub(
        work("CLM-1008"),
        work("CLM-1008"),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(
        1,
        queue,
        claim_models({"CLM-1008": [failing(), stub(*decide_and_pay("CLM-1008"))]}),
    )
    first, second = tool_results(queue)
    assert first.startswith("CLM-1008 failed (attempt 1, back in the queue)")
    assert second == "CLM-1008: approve, $200.00"
    worked = get(api, "CLM-1008")
    assert worked["status"] == "decided"
    assert worked["attempts"] == 1


def test_a_claim_that_fails_twice_is_left_for_a_handler(api):
    queue = stub(
        work("CLM-1007"),
        work("CLM-1007"),
        AIMessage(content="Done."),
    )
    queue_agent.run_queue(1, queue, claim_models({"CLM-1007": [failing(), failing()]}))
    assert "left for a handler" in tool_results(queue)[-1]
    assert get(api, "CLM-1007")["status"] == "needs_handler"
    steps = api.get("/api/claims/CLM-1007/steps").json()
    assert [s["attempt"] for s in steps if s["kind"] == "error"] == [1, 2]


def test_the_agent_is_sent_back_for_missed_claims(api):
    queue = stub(
        work("CLM-1009"),
        AIMessage(content="Done too early."),
        work("CLM-1010"),
        AIMessage(content="All done."),
    )
    summary = queue_agent.run_queue(
        2,
        queue,
        claim_models(
            {
                "CLM-1009": [stub(*decide_and_pay("CLM-1009"))],
                "CLM-1010": [stub(*decide_and_pay("CLM-1010"))],
            }
        ),
    )
    assert summary == "All done."
    reminders = [
        m for m in queue.seen[-1] if isinstance(m, HumanMessage) and "Before" in m.text
    ]
    assert len(reminders) == 1
    assert "CLM-1004" in reminders[0].text
    assert get(api, "CLM-1010")["status"] == "decided"


def test_reminders_stop_after_three(api):
    queue = stub(*[AIMessage(content=f"Done {i}.") for i in range(4)])
    summary = queue_agent.run_queue(1, queue)
    assert summary == "Done 3."
    assert len(queue.seen) == 4


def test_missed_claims_lists_retries_then_claims_within_the_cap(api):
    run = queue_agent.QueueRun("RUN-x", 2, worked={"CLM-1004"})
    assert queue_agent.missed_claims(run) == ["CLM-1004", "CLM-1011"]


def test_no_claim_is_decided_or_paid_twice(api):
    decision = dict(
        claim_id="CLM-1011",
        explanation="Covered.",
        policy_reference="Policy wording 5",
    )
    claim_agent = stub(
        tool_call("record_decision", "1", decision="approve", payout=200.0, **decision),
        tool_call("record_decision", "2", decision="decline", payout=0.0, **decision),
        tool_call("pay_claim", "3", claim_id="CLM-1011", amount=200.0),
        tool_call("pay_claim", "4", claim_id="CLM-1011", amount=200.0),
        AIMessage(content="CLM-1011: approve, $200.00"),
    )
    queue = stub(work("CLM-1011"), AIMessage(content="Done."))
    queue_agent.run_queue(1, queue, claim_models({"CLM-1011": [claim_agent]}))

    results = tool_results(claim_agent)
    assert results[1].startswith("Error 409")
    assert results[3].startswith("Error 409")
    worked = get(api, "CLM-1011")
    assert (worked["decision"], worked["paid_amount"]) == ("approve", 200.0)


def test_the_run_is_finished_when_the_queue_agent_fails(api):
    with pytest.raises(RuntimeError):
        queue_agent.run_queue(0, stub(failures=1))
    run = api.get("/api/runs/latest").json()
    assert run["status"] == "finished"
    assert run["summary"] == "The run stopped before it finished."


def test_a_run_recovers_claims_left_in_progress(api):
    api.post("/api/claims/CLM-1012/start")
    queue_agent.run_queue(0, stub(AIMessage(content="Done.")))
    stuck = get(api, "CLM-1012")
    assert (stuck["status"], stuck["attempts"]) == ("waiting", 1)


def test_an_uncapped_run_is_capped_at_the_waiting_claims(api):
    queue_agent.run_queue(None, stub(*[AIMessage(content="Done.")] * 4))
    waiting = [c for c in api.get("/api/claims").json() if c["status"] == "waiting"]
    assert api.get("/api/runs/latest").json()["cap"] == len(waiting)
