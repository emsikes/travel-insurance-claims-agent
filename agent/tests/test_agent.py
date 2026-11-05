import contextlib
import time
from pathlib import Path

from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from agent import main
from backend.database import DB_PATH, init_db
from backend.main import app


def setup_module():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def teardown_module():
    if DB_PATH.exists():
        time.sleep(0.1)
        with contextlib.suppress(PermissionError):
            DB_PATH.unlink()


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


def test_get_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    claim = main.get_claim.invoke({"claim_id": "CLM-1001"})
    assert claim["claim_id"] == "CLM-1001"
    assert claim["customer_id"] == "CUS-3001"


def test_get_policy(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    policy = main.get_policy.invoke({"policy_id": "POL-2001"})
    assert policy["policy_id"] == "POL-2001"
    assert policy["plan"] == "premium"


def test_get_customer_pii_excluded(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    customer = main.get_customer.invoke({"customer_id": "CUS-3001"})
    assert customer["customer_id"] == "CUS-3001"
    assert customer["name"] == "Maya Patel"
    assert "email" not in customer
    assert "phone" not in customer
    assert "date_of_birth" not in customer
    assert "address" not in customer


def test_get_policy_wording(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    wording = main.get_policy_wording.invoke({})
    assert "UnderCover Travel Insurance" in wording


def test_update_claim_status(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    result = main.update_claim_status.invoke(
        {"claim_id": "CLM-1001", "status": "in_progress"}
    )
    assert result["status"] == "in_progress"


def test_record_decision(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    result = main.record_decision.invoke(
        {
            "claim_id": "CLM-1002",
            "decision": "approve",
            "payout": 500.0,
            "explanation": "Approved",
            "policy_reference": "Section 3",
        }
    )
    assert result["decision"] == "approve"
    assert result["payout"] == 500.0


def test_pay_claim(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    main.record_decision.invoke(
        {
            "claim_id": "CLM-1003",
            "decision": "approve",
            "payout": 800.0,
            "explanation": "Approved",
            "policy_reference": "Section 3",
        }
    )
    result = main.pay_claim.invoke({"claim_id": "CLM-1003", "amount": 800.0})
    assert result["status"] == "paid"


def test_run(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_claim", "args": {"claim_id": "CLM-1004"}, "id": "1"}
            ],
        ),
        AIMessage(content="Claim processed successfully."),
    ]
    result = main.run("CLM-1004", "thread-1", StubModel(messages=iter(replies)))
    assert result == "Claim processed successfully."


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_tool_error_returned_to_model(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    result = main.get_policy.invoke({"policy_id": "CLM-1001"})
    assert result.startswith("Error 404")
    assert "Policy not found" in result


def test_run_recovers_from_wrong_id(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    replies = [
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_policy", "args": {"policy_id": "CLM-1005"}, "id": "1"}
            ],
        ),
        AIMessage(
            content="",
            tool_calls=[
                {"name": "get_claim", "args": {"claim_id": "CLM-1005"}, "id": "2"}
            ],
        ),
        AIMessage(content="Recovered."),
    ]
    result = main.run("CLM-1005", "thread-2", StubModel(messages=iter(replies)))
    assert result == "Recovered."


def test_dashboard_shows_current_prompt():
    app_tsx = Path(__file__).parents[2] / "dashboard" / "src" / "App.tsx"
    assert main.SYSTEM_PROMPT in app_tsx.read_text(encoding="utf-8")
