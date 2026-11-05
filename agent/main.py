"""The UnderCover Agent."""

import os
from typing import Any

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
SYSTEM_PROMPT = """You are the UnderCover Agent, deciding travel insurance claims.

For each claim, follow these steps in order:
1. Set the claim's status to in_progress
2. Read the claim. It gives the policy_id (POL-...) and customer_id (CUS-...)
3. Read the policy, using the claim's policy_id
4. Read the customer's claim history, using the claim's customer_id
5. Read the policy wording
6. Analyze the claim against the policy wording
7. Make a decision: approve, decline, or refer
8. Calculate the payout if approving
9. Explain your decision in 2-3 sentences with the relevant policy section
10. Record your decision
11. Pay the claim if the payout is $1,000 or less

Never guess an id: take it from the claim. If a tool returns an error, correct it.

If the payout is over $1,000, record the decision but do not pay: it needs sign-off."""


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=10)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
    """Call the backend, returning errors as text so the model can correct itself."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Error {response.status_code}: {response.text}"
    return response.json()


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
def get_policy_wording() -> str:
    """Get the full policy wording."""
    with backend() as client:
        response = client.get("/api/policy-wording")
    response.raise_for_status()
    return response.json()["content"]


@tool
def update_claim_status(claim_id: str, status: str) -> dict | str:
    """Update a claim's status."""
    return call("POST", f"/api/claims/{claim_id}/status", {"status": status})


@tool
def record_decision(
    claim_id: str, decision: str, payout: float, explanation: str, policy_reference: str
) -> dict | str:
    """Record a decision on a claim: approve, decline or refer."""
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
    """Pay a claim with the specified amount."""
    return call("POST", f"/api/claims/{claim_id}/pay", {"amount": amount})


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim and return its final reply."""
    tools = [
        get_claim,
        get_policy,
        get_customer,
        get_policy_wording,
        update_claim_status,
        record_decision,
        pay_claim,
    ]
    agent = create_agent(llm or model(), tools=tools, system_prompt=SYSTEM_PROMPT)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": f"Decide claim {claim_id}"}]},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].text
