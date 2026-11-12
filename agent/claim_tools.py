"""The claim agent's tools: each one is a thin wrapper over one backend operation.

The business rules live in the backend, which enforces them, and in the claim
instructions, which explain them. These tools only reach the API."""

from typing import Any

from langchain_core.tools import tool

from agent.backend_api import for_model


@tool
def get_claim(claim_id: str) -> dict | str:
    """Get a claim by its claim_id, such as CLM-1001."""
    return for_model("GET", f"/api/claims/{claim_id}")


@tool
def get_policy(policy_id: str) -> dict | str:
    """Get a policy by its policy_id, such as POL-2001, taken from the claim."""
    return for_model("GET", f"/api/policies/{policy_id}")


@tool
def get_customer(customer_id: str) -> dict | str:
    """Get a customer's claim history by customer_id, such as CUS-3001."""
    return for_model("GET", f"/api/customers/{customer_id}/agent")


@tool
def list_sections(document: str) -> list | str:
    """List the numbered sections of a document: policy_wording or claims_manual."""
    return for_model("GET", f"/api/documents/{document}/sections")


@tool(response_format="content_and_artifact")
def read_section(document: str, number: int) -> tuple[str, dict[str, Any] | None]:
    """Read one numbered section of policy_wording or claims_manual."""
    section = for_model("GET", f"/api/documents/{document}/sections/{number}")
    if isinstance(section, str):
        return section, None
    return section["content"], section


@tool
def record_decision(
    claim_id: str, decision: str, payout: float, explanation: str, policy_reference: str
) -> dict | str:
    """Record the decision on a claim: approve, decline or refer."""
    return for_model(
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
    """Pay an approved claim. Payouts over the approval limit wait for sign-off."""
    return for_model("POST", f"/api/claims/{claim_id}/pay", {"amount": amount})


TOOLS = [
    get_claim,
    get_policy,
    get_customer,
    list_sections,
    read_section,
    record_decision,
    pay_claim,
]
