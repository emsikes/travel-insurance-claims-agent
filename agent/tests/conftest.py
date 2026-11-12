import contextlib
import time

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage
from pydantic import Field

from agent import main
from backend.database import DB_PATH, init_db
from backend.main import app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies and keeps what it was sent."""

    seen: list = Field(default_factory=list)
    failures: int = 0

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(messages)
        if self.failures:
            self.failures -= 1
            raise RuntimeError("provider error")
        return super()._generate(messages, stop, run_manager, **kwargs)


def stub(*replies: AIMessage, failures: int = 0) -> StubModel:
    return StubModel(messages=iter(replies), failures=failures)


def tool_call(name: str, call_id: str, **args) -> AIMessage:
    return AIMessage(
        content="", tool_calls=[{"name": name, "args": args, "id": call_id}]
    )


def decide_and_pay(claim_id: str, payout: float = 200.0) -> list[AIMessage]:
    return [
        tool_call(
            "record_decision",
            f"{claim_id}-d",
            claim_id=claim_id,
            decision="approve",
            payout=payout,
            explanation="Covered.",
            policy_reference="Policy wording 5",
        ),
        tool_call("pay_claim", f"{claim_id}-p", claim_id=claim_id, amount=payout),
        AIMessage(content=f"{claim_id}: approve, ${payout:,.2f}"),
    ]


@pytest.fixture(scope="module", autouse=True)
def fresh_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    yield
    time.sleep(0.1)
    with contextlib.suppress(PermissionError):
        DB_PATH.unlink()


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)
