"""The queue agent's harness: one run over the waiting claims, with a to-do list,
a cap, one fresh claim agent per claim and a check for missed claims."""

from collections.abc import Callable
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Literal

from langchain.agents import AgentState, create_agent
from langchain.agents.middleware import AgentMiddleware, hook_config
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.tools import BaseTool, tool
from pydantic import BaseModel

from agent import backend_api, claim, config

MAX_REMINDERS = 3
RECURSION_LIMIT = 500
TODO_STATUS = {
    "decided": "done",
    "waiting_for_signoff": "done",
    "needs_handler": "left_for_handler",
}


class Todo(BaseModel):
    claim_id: str
    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


@dataclass
class QueueRun:
    """One run over the queue: its id, its cap and the claims it has worked."""

    run_id: str
    cap: int
    claim_llm: Callable[[str], BaseChatModel] | None = None
    worked: set[str] = field(default_factory=set)
    reminders: int = 0
    lock: Lock = field(default_factory=Lock)


def waiting_claims() -> list[dict[str, Any]]:
    """Get the claims waiting in the queue, in brief."""
    return backend_api.request("GET", "/api/claims/waiting")


def queue_tools(run: QueueRun) -> list[BaseTool]:
    """Build the queue agent's tools for one run."""

    @tool
    def list_waiting_claims() -> list[dict[str, Any]]:
        """List the waiting claims with their summary, type and amount claimed."""
        return waiting_claims()

    @tool
    def write_todos(todos: list[Todo]) -> str:
        """Replace the run's to-do list, which the handlers see on the dashboard."""
        result = backend_api.for_model(
            "PUT",
            f"/api/runs/{run.run_id}/todos",
            [todo.model_dump() for todo in todos],
        )
        return result if isinstance(result, str) else "Updated the to-do list."

    @tool
    def work_claim(claim_id: str) -> str:
        """Hand a waiting claim to a fresh claim agent and get its result in a line."""
        with run.lock:
            if claim_id not in run.worked and len(run.worked) >= run.cap:
                return f"{claim_id} not started: the cap of {run.cap} claims is reached"
            run.worked.add(claim_id)
        llm = run.claim_llm(claim_id) if run.claim_llm else None
        result = claim.work(claim_id, run.run_id, llm)
        if not result.started:
            with run.lock:
                run.worked.discard(claim_id)
        return result.line

    return [list_waiting_claims, write_todos, work_claim]


def missed_claims(run: QueueRun) -> list[str]:
    """Waiting claims the run should still work: unworked ones within its cap and
    ones that failed once in this run."""
    waiting = [c["claim_id"] for c in waiting_claims()]
    retries = [c for c in waiting if c in run.worked]
    room = run.cap - len(run.worked)
    unworked = [c for c in waiting if c not in run.worked][: max(room, 0)]
    return retries + unworked


class MissedClaimCheck(AgentMiddleware):
    """Send the queue agent back to work when it tries to finish too early."""

    def __init__(self, run: QueueRun) -> None:
        super().__init__()
        self.run = run

    @hook_config(can_jump_to=["model"])
    def after_model(self, state: AgentState, runtime: Any) -> dict[str, Any] | None:
        last = state["messages"][-1]
        if not isinstance(last, AIMessage) or last.tool_calls:
            return None
        if self.run.reminders >= MAX_REMINDERS:
            return None
        missed = missed_claims(self.run)
        if not missed:
            return None
        self.run.reminders += 1
        reminder = (
            f"Before you finish: these claims are still waiting and within your cap, "
            f"so work them: {', '.join(missed)}. Then update the to-do list and "
            "write your summary."
        )
        return {"messages": [HumanMessage(reminder)], "jump_to": "model"}


def run_queue(
    cap: int | None = None,
    llm: BaseChatModel | None = None,
    claim_llm: Callable[[str], BaseChatModel] | None = None,
) -> str:
    """Work the waiting claims, up to cap of them, and return the summary."""
    backend_api.request("POST", "/api/claims/recover")
    if cap is None:
        cap = len(waiting_claims())
    started = backend_api.request("POST", "/api/runs", {"cap": cap})
    run = QueueRun(started["run_id"], cap, claim_llm)
    agent = create_agent(
        llm or config.model(),
        tools=queue_tools(run),
        system_prompt=backend_api.instructions("queue"),
        middleware=(MissedClaimCheck(run), config.retry()),
    )
    summary = "The run stopped before it finished."
    try:
        result = agent.invoke(
            {
                "messages": [
                    {
                        "role": "user",
                        "content": f"Work the waiting claims, up to {cap} of them.",
                    }
                ]
            },
            config={
                "configurable": {"thread_id": run.run_id},
                "recursion_limit": RECURSION_LIMIT,
            },
        )
        summary = result["messages"][-1].text
    finally:
        backend_api.request(
            "POST", f"/api/runs/{run.run_id}/finish", {"summary": summary}
        )
    return summary


def run_one(claim_id: str, llm: BaseChatModel | None = None) -> str:
    """Work one named claim as a run capped at one claim, and return its result."""
    summary = backend_api.request("GET", f"/api/claims/{claim_id}")["summary"]
    run_id = backend_api.request("POST", "/api/runs", {"cap": 1})["run_id"]
    todos_path = f"/api/runs/{run_id}/todos"
    todo = {"claim_id": claim_id, "content": f"{claim_id}: {summary}"}
    backend_api.request("PUT", todos_path, [{**todo, "status": "in_progress"}])
    line = "The run stopped before it finished."
    try:
        line = claim.work(claim_id, run_id, llm).line
    finally:
        status = backend_api.request("GET", f"/api/claims/{claim_id}")["status"]
        todo["status"] = TODO_STATUS.get(status, "to_do")
        backend_api.request("PUT", todos_path, [todo])
        backend_api.request("POST", f"/api/runs/{run_id}/finish", {"summary": line})
    return line
