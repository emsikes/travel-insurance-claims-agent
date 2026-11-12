"""The claim agent: a fresh subagent that works one claim."""

from typing import Any

from langchain.agents import create_agent
from langchain.agents.middleware import (
    AgentMiddleware,
    ModelRetryMiddleware,
)
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolMessage
from langchain_core.tools import tool

from agent.main import call, instructions, model

DOCUMENT_TITLES = {"policy_wording": "Policy wording", "claims_manual": "Claims manual"}
RECURSION_LIMIT = 60
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2.0
STEP_TEXT_LENGTH = 300


@tool
def get_claim(claim_id: str) -> dict | str:
    """Get a claim by its claim_id, such as CLM-1001."""
    return call("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> dict | str:
    """Get a policy by its policy_id, such as POL-2001, taken from the claim."""
    return call("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> dict | str:
    """Get a customer's claim history by customer_id, such as CUS-3001."""
    return call("GET", f"/api/customers/{customer_id}/agent")


@tool
def list_sections(document: str) -> list | str:
    """List the numbered sections of a document: policy_wording or claims_manual."""
    return call("GET", f"/api/documents/{document}/sections")


@tool
def read_section(document: str, number: int) -> str:
    """Read one numbered section of policy_wording or claims_manual."""
    section = call("GET", f"/api/documents/{document}/sections/{number}")
    return section if isinstance(section, str) else section["content"]


@tool
def record_decision(
    claim_id: str, decision: str, payout: float, explanation: str, policy_reference: str
) -> dict | str:
    """Record the decision on a claim: approve, decline or refer."""
    return call(
        "POST",
        f"/api/claims/{claim_id}/decide",
        {
            "decision": decision,
            "payout": payout,
            "explanation": explanation,
            "policy_reference": policy_reference,
        },
    )


@tool
def pay_claim(claim_id: str, amount: float) -> dict | str:
    """Pay an approved claim with a payout of $1,000 or less."""
    return call("POST", f"/api/claims/{claim_id}/pay", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    record_decision,
    pay_claim,
]


def record_step(claim_id: str, attempt: int, kind: str, text: str) -> None:
    """Record a step on the claim."""
    call(
        "POST",
        f"/api/claims/{claim_id}/steps",
        {"attempt": attempt, "kind": kind, "text": text},
    )


def describe(name: str, args: dict[str, Any], result: str) -> tuple[str, str]:
    """Describe a tool call as a step: its kind and a short text."""
    if name == "read_section" and not result.startswith("Error"):
        heading = result.splitlines()[0].removeprefix("## ")
        return "section_read", f"{DOCUMENT_TITLES[args['document']]} {heading}"
    shown = ", ".join(f"{key}={value}" for key, value in args.items())
    return "tool_call", f"{name}({shown}): {result}"[:STEP_TEXT_LENGTH]


class StepRecorder(AgentMiddleware):
    """Record every tool call the claim agent makes as a step on the claim."""

    def __init__(self, claim_id: str, attempt: int) -> None:
        super().__init__()
        self.claim_id = claim_id
        self.attempt = attempt

    def wrap_tool_call(self, request, handler):
        result = handler(request)
        content = str(result.content) if isinstance(result, ToolMessage) else ""
        kind, text = describe(
            request.tool_call["name"], request.tool_call["args"], content
        )
        record_step(self.claim_id, self.attempt, kind, text)
        return result


def run_claim(
    claim_id: str, thread_id: str, attempt: int, llm: BaseChatModel | None = None
) -> str:
    """Run a fresh claim agent on one claim in progress and return its reply."""
    agent = create_agent(
        llm or model(),
        tools=TOOLS,
        system_prompt=instructions("claim"),
        middleware=(
            StepRecorder(claim_id, attempt),
            ModelRetryMiddleware(
                max_retries=MAX_RETRIES,
                initial_delay=RETRY_DELAY_SECONDS,
                on_failure="error",
            ),
        ),
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


def fail(claim_id: str, attempt: int, error: str) -> str:
    """Record a failed attempt and say where the claim went."""
    record_step(claim_id, attempt, "error", error)
    result = call("POST", f"/api/claims/{claim_id}/fail", {"error": error})
    if result["status"] == "needs_handler":
        where = "left for a handler"
    else:
        where = "back in the queue"
    return f"{claim_id} failed (attempt {attempt}, {where}): {error}"


def work(claim_id: str, thread_prefix: str, llm: BaseChatModel | None = None) -> str:
    """Start a waiting claim, work it with a fresh claim agent and report in a line."""
    started = call("POST", f"/api/claims/{claim_id}/start")
    if isinstance(started, str):
        return f"{claim_id} not started: {started}"
    attempt = call("GET", f"/api/claims/{claim_id}")["attempts"] + 1
    try:
        reply = run_claim(
            claim_id, f"{thread_prefix}-{claim_id}-{attempt}", attempt, llm
        )
    except Exception as error:
        return fail(claim_id, attempt, f"{type(error).__name__}: {error}")

    claim = call("GET", f"/api/claims/{claim_id}")
    if claim["status"] == "in_progress":
        return fail(claim_id, attempt, "finished without recording a decision")
    record_step(claim_id, attempt, "result", reply)
    return outcome(claim)
