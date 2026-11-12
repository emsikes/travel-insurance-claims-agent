"""The claim agent's harness: a fresh subagent that works one claim, with its
steps recorded, retries, a recursion limit and a failure sent back to the queue."""

from dataclasses import dataclass
from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage

from agent import backend_api, config
from agent.claim_tools import TOOLS

RECURSION_LIMIT = 60
STEP_TEXT_LENGTH = 300


@dataclass
class WorkResult:
    """What working a claim came to: whether it started, and a line for the run."""

    started: bool
    line: str


def record_step(claim_id: str, attempt: int, kind: str, text: str) -> None:
    """Record a step on the claim."""
    backend_api.request(
        "POST",
        f"/api/claims/{claim_id}/steps",
        {"attempt": attempt, "kind": kind, "text": text},
    )


def describe(
    name: str, args: dict[str, Any], content: str, section: dict[str, Any] | None
) -> tuple[str, str]:
    """Describe a tool call as a step: its kind and a short text."""
    if section:
        heading = f"{section['number']}. {section['title']}"
        return "section_read", f"{section['document_title']} {heading}"
    shown = ", ".join(f"{key}={value}" for key, value in args.items())
    return "tool_call", f"{name}({shown}): {content}"[:STEP_TEXT_LENGTH]


class StepRecorder(AgentMiddleware):
    """Record every tool call the claim agent makes as a step on the claim."""

    def __init__(self, claim_id: str, attempt: int) -> None:
        super().__init__()
        self.claim_id = claim_id
        self.attempt = attempt

    def wrap_tool_call(self, request, handler):
        result = handler(request)
        message = result if isinstance(result, ToolMessage) else None
        kind, text = describe(
            request.tool_call["name"],
            request.tool_call["args"],
            str(message.content) if message else "",
            message.artifact if message else None,
        )
        record_step(self.claim_id, self.attempt, kind, text)
        return result


def run_claim(
    claim_id: str, thread_id: str, attempt: int, llm: BaseChatModel | None = None
) -> str:
    """Run a fresh claim agent on one claim in progress and return its reply."""
    agent = create_agent(
        llm or config.model(),
        tools=TOOLS,
        system_prompt=backend_api.instructions("claim"),
        middleware=(StepRecorder(claim_id, attempt), config.retry()),
    )
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}"}]},
        config={
            "configurable": {"thread_id": thread_id},
            "recursion_limit": RECURSION_LIMIT,
        },
    )
    return result["messages"][-1].text


def outcome(claim: dict[str, Any]) -> str:
    """Describe a decided claim in one line."""
    line = f"{claim['claim_id']}: {claim['decision']}, ${claim['payout']:,.2f}"
    if claim["status"] == "waiting_for_signoff":
        line += ", waiting for sign-off"
    return line


def fail(claim_id: str, attempt: int, error: str) -> WorkResult:
    """Record a failed attempt and say where the claim went."""
    record_step(claim_id, attempt, "error", error)
    result = backend_api.request(
        "POST", f"/api/claims/{claim_id}/fail", {"error": error}
    )
    where = (
        "left for a handler"
        if result["status"] == "needs_handler"
        else "back in the queue"
    )
    return WorkResult(True, f"{claim_id} failed (attempt {attempt}, {where}): {error}")


def work(
    claim_id: str, thread_prefix: str, llm: BaseChatModel | None = None
) -> WorkResult:
    """Start a waiting claim, work it with a fresh claim agent and report in a line."""
    started = backend_api.client().post(f"/api/claims/{claim_id}/start")
    if started.is_error:
        line = f"{claim_id} not started: {backend_api.error_text(started)}"
        return WorkResult(False, line)
    attempt = started.json()["attempts"] + 1
    try:
        reply = run_claim(
            claim_id, f"{thread_prefix}-{claim_id}-{attempt}", attempt, llm
        )
    except Exception as error:
        return fail(claim_id, attempt, f"{type(error).__name__}: {error}")

    claim = backend_api.request("GET", f"/api/claims/{claim_id}")
    if claim["status"] == "in_progress":
        return fail(claim_id, attempt, "finished without recording a decision")
    record_step(claim_id, attempt, "result", reply)
    return WorkResult(True, outcome(claim))
