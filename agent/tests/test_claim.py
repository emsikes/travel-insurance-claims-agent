import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

from agent import backend_api, claim, claim_tools, config
from agent.tests.conftest import decide_and_pay, stub, tool_call
from backend.main import app

SECTION = {
    "number": 5,
    "title": "Baggage",
    "content": "## 5. Baggage",
    "document_title": "Policy wording",
}


def start(api, claim_id: str) -> None:
    api.post(f"/api/claims/{claim_id}/start")


def steps(api, claim_id: str) -> list[dict]:
    return api.get(f"/api/claims/{claim_id}/steps").json()


def test_get_claim(api):
    result = claim_tools.get_claim.invoke({"claim_id": "CLM-1001"})
    assert result["customer_id"] == "CUS-3001"


def test_get_policy(api):
    policy = claim_tools.get_policy.invoke({"policy_id": "POL-2001"})
    assert policy["plan"] == "premium"


def test_get_customer_pii_excluded(api):
    customer = claim_tools.get_customer.invoke({"customer_id": "CUS-3001"})
    assert customer["name"] == "Maya Patel"
    for field in ("email", "phone", "date_of_birth", "address"):
        assert field not in customer


def test_list_and_read_sections(api):
    sections = claim_tools.list_sections.invoke({"document": "claims_manual"})
    assert {"number": 9, "title": "Repeat claims"} in sections
    text = claim_tools.read_section.invoke({"document": "claims_manual", "number": 9})
    assert text.startswith("## 9. Repeat claims")


def test_tool_error_returned_to_model(api):
    result = claim_tools.get_policy.invoke({"policy_id": "CLM-1001"})
    assert result.startswith("Error 404")
    missing = claim_tools.read_section.invoke(
        {"document": "claims_manual", "number": 99}
    )
    assert missing.startswith("Error 404")


def test_harness_calls_raise_on_an_error(api):
    with pytest.raises(Exception, match="404 Not Found"):
        backend_api.request("GET", "/api/claims/CLM-9999")


def test_tools_cannot_read_whole_wording_or_set_a_status():
    names = {t.name for t in claim_tools.TOOLS}
    assert "get_policy_wording" not in names
    assert not [name for name in names if "status" in name or "start" in name]


def test_describe_section_read():
    kind, text = claim.describe(
        "read_section", {"document": "policy_wording", "number": 5}, "...", SECTION
    )
    assert (kind, text) == ("section_read", "Policy wording 5. Baggage")


def test_describe_tool_call_is_short():
    kind, text = claim.describe("get_claim", {"claim_id": "CLM-1"}, "x" * 1000, None)
    assert kind == "tool_call"
    assert text.startswith("get_claim(claim_id=CLM-1): x")
    assert len(text) == claim.STEP_TEXT_LENGTH


def test_run_claim_records_sections_read(api):
    start(api, "CLM-1002")
    model = stub(
        tool_call("list_sections", "1", document="claims_manual"),
        tool_call("read_section", "2", document="claims_manual", number=9),
        tool_call("read_section", "3", document="policy_wording", number=99),
        AIMessage(content="Done."),
    )
    assert claim.run_claim("CLM-1002", "t-1", 1, model) == "Done."

    recorded = steps(api, "CLM-1002")
    assert [s["kind"] for s in recorded] == ["tool_call", "section_read", "tool_call"]
    assert recorded[1]["text"] == "Claims manual 9. Repeat claims"
    assert recorded[2]["text"].startswith("read_section(")
    assert all(s["attempt"] == 1 for s in recorded)


def test_system_prompt_comes_from_the_backend(api):
    start(api, "CLM-1003")
    model = stub(AIMessage(content="Done."))
    claim.run_claim("CLM-1003", "t-2", 1, model)
    assert model.seen[0][0].content == api.get("/api/instructions").json()["claim"]


def test_provider_error_is_retried(api, monkeypatch):
    monkeypatch.setattr(config, "RETRY_DELAY_SECONDS", 0.01)
    start(api, "CLM-1004")
    model = stub(AIMessage(content="Recovered."), failures=1)
    assert claim.run_claim("CLM-1004", "t-3", 1, model) == "Recovered."
    assert len(model.seen) == 2


def test_pii_never_reaches_the_model(api):
    full = api.get("/api/customers/CUS-3001").json()
    start(api, "CLM-1005")
    model = stub(
        tool_call("get_customer", "1", customer_id="CUS-3001"),
        AIMessage(content="Done."),
    )
    claim.run_claim("CLM-1005", "t-4", 1, model)
    sent = str([m.content for messages in model.seen for m in messages])
    assert "Maya Patel" in sent
    for field in ("email", "phone", "date_of_birth"):
        assert full[field] not in sent
    assert full["address"]["street"] not in sent


def test_work_decides_and_pays(api):
    result = claim.work("CLM-1006", "run", stub(*decide_and_pay("CLM-1006")))
    assert result == claim.WorkResult(True, "CLM-1006: approve, $200.00")
    worked = api.get("/api/claims/CLM-1006").json()
    assert worked["status"] == "decided"
    assert worked["paid_amount"] == 200.0
    last = steps(api, "CLM-1006")[-1]
    assert (last["kind"], last["text"]) == ("result", "CLM-1006: approve, $200.00")


def test_work_uses_one_client_and_no_extra_requests(monkeypatch):
    sent: list[tuple[str, str]] = []

    class RecordingClient(TestClient):
        def request(self, method, url, *args, **kwargs):
            sent.append((method, str(url)))
            return super().request(method, url, *args, **kwargs)

    made: list[RecordingClient] = []

    def make_client(**kwargs) -> RecordingClient:
        made.append(RecordingClient(app))
        return made[-1]

    monkeypatch.setattr(backend_api.httpx, "Client", make_client)
    backend_api.client.cache_clear()
    try:
        claim.work("CLM-1012", "run", stub(*decide_and_pay("CLM-1012")))
    finally:
        backend_api.client.cache_clear()

    assert len(made) == 1
    steps_path = "/api/claims/CLM-1012/steps"
    assert sent == [
        ("POST", "/api/claims/CLM-1012/start"),
        ("GET", "/api/instructions"),
        ("POST", "/api/claims/CLM-1012/decide"),
        ("POST", steps_path),
        ("POST", "/api/claims/CLM-1012/pay"),
        ("POST", steps_path),
        ("GET", "/api/claims/CLM-1012"),
        ("POST", steps_path),
    ]


def test_work_over_limit_waits_for_signoff(api):
    replies = decide_and_pay("CLM-1007", 1500.0)
    result = claim.work("CLM-1007", "run", stub(replies[0], replies[2]))
    assert result.line == "CLM-1007: approve, $1,500.00, waiting for sign-off"


def test_work_failure_goes_back_in_the_queue(api, monkeypatch):
    monkeypatch.setattr(config, "MAX_RETRIES", 0)
    result = claim.work("CLM-1008", "run", stub(failures=1))
    assert result.line == (
        "CLM-1008 failed (attempt 1, back in the queue): RuntimeError: provider error"
    )
    assert api.get("/api/claims/CLM-1008").json()["status"] == "waiting"
    assert steps(api, "CLM-1008")[-1]["kind"] == "error"


def test_work_without_a_decision_is_a_failure(api):
    result = claim.work("CLM-1009", "run", stub(AIMessage(content="Hmm.")))
    assert "finished without recording a decision" in result.line
    assert api.get("/api/claims/CLM-1009").json()["attempts"] == 1


def test_work_on_a_claim_that_is_not_waiting(api):
    claim.work("CLM-1010", "run", stub(*decide_and_pay("CLM-1010")))
    result = claim.work("CLM-1010", "run", stub())
    assert not result.started
    assert result.line.startswith("CLM-1010 not started: Error 409")


def test_a_looping_claim_agent_is_stopped(api, monkeypatch):
    monkeypatch.setattr(claim, "RECURSION_LIMIT", 6)
    loop = [tool_call("get_claim", str(i), claim_id="CLM-1011") for i in range(10)]
    result = claim.work("CLM-1011", "run", stub(*loop))
    assert "GraphRecursionError" in result.line
    assert api.get("/api/claims/CLM-1011").json()["status"] == "waiting"
