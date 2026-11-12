"""What claims are decided against: policies, customers, plans, settings, the
policy wording and claims manual, and the agent's instructions."""

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from backend.database import DOCUMENTS, connect

INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"

router = APIRouter(prefix="/api")


@router.get("/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy by ID with plan details and add-ons."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM policies WHERE policy_id = ?", (policy_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")
    policy = dict(row)
    for key in ("add_ons", "trip", "travelers"):
        policy[key] = json.loads(policy[key])
    return policy


@router.get("/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get customer with claim history."""
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = dict(row)
    customer["address"] = json.loads(customer["address"])
    customer["previous_claims"] = json.loads(customer["previous_claims"])
    return customer


@router.get("/customers/{customer_id}/agent", operation_id="get_customer_for_agent")
def get_customer_for_agent(customer_id: str) -> dict[str, Any]:
    """Get customer data for agent without PII."""
    with connect() as conn:
        row = conn.execute(
            "SELECT customer_id, name, customer_since, previous_claims "
            "FROM customers WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")
    customer = dict(row)
    customer["previous_claims"] = json.loads(customer["previous_claims"])
    return customer


@router.get("/plans", operation_id="get_plans")
def get_plans() -> dict[str, Any]:
    """Get all plans with limits and add-ons."""
    with connect() as conn:
        return json.loads(conn.execute("SELECT data FROM plans").fetchone()["data"])


@router.get("/company-settings", operation_id="get_company_settings")
def get_company_settings() -> dict[str, Any]:
    """Get company settings including approval limit."""
    with connect() as conn:
        row = conn.execute("SELECT data FROM company_settings").fetchone()
    return json.loads(row["data"])


@router.get("/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[dict[str, Any]]:
    """List the numbered sections of the policy wording or the claims manual."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT number, title FROM documents WHERE document = ? ORDER BY number",
            (document,),
        ).fetchall()
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")
    return [dict(row) for row in rows]


@router.get("/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: str, number: int) -> dict[str, Any]:
    """Read one section of the policy wording or the claims manual."""
    with connect() as conn:
        row = conn.execute(
            "SELECT number, title, content FROM documents "
            "WHERE document = ? AND number = ?",
            (document, number),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    return {**dict(row), "document_title": DOCUMENTS[document][1]}


@router.get("/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions for running the queue and working a claim."""
    return {
        name: (INSTRUCTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")
        for name in ("queue", "claim")
    }
