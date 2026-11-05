"""The UnderCover backend."""

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.database import get_db, init_db, row_to_dict


class StatusUpdate(BaseModel):
    status: str


class Decision(BaseModel):
    decision: str
    payout: float
    explanation: str
    policy_reference: str


class Payment(BaseModel):
    amount: float


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    init_db()
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="get_claims")
def get_claims() -> list[dict[str, Any]]:
    """Get all claims."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims")
    rows = cursor.fetchall()
    conn.close()

    claims = []
    for row in rows:
        claim = row_to_dict(row)
        claim["items"] = json.loads(claim["items"])
        claim["documents"] = json.loads(claim["documents"])
        claims.append(claim)
    return claims


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get a specific claim by ID."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = row_to_dict(row)
    claim["items"] = json.loads(claim["items"])
    claim["documents"] = json.loads(claim["documents"])
    return claim


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str) -> dict[str, Any]:
    """Get a policy by ID with plan details and add-ons."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Policy not found")

    policy = row_to_dict(row)
    policy["add_ons"] = json.loads(policy["add_ons"])
    policy["trip"] = json.loads(policy["trip"])
    policy["travelers"] = json.loads(policy["travelers"])
    return policy


@app.get("/api/customers/{customer_id}", operation_id="get_customer")
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get customer with claim history."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = row_to_dict(row)
    customer["address"] = json.loads(customer["address"])
    customer["previous_claims"] = json.loads(customer["previous_claims"])
    return customer


@app.get("/api/customers/{customer_id}/agent", operation_id="get_customer_for_agent")
def get_customer_for_agent(customer_id: str) -> dict[str, Any]:
    """Get customer data for agent without PII."""
    conn = get_db()
    cursor = conn.cursor()
    query = """
        SELECT customer_id, name, customer_since, previous_claims
        FROM customers WHERE customer_id = ?
    """
    cursor.execute(query, (customer_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer = row_to_dict(row)
    customer["previous_claims"] = json.loads(customer["previous_claims"])
    return customer


@app.get("/api/plans", operation_id="get_plans")
def get_plans() -> dict[str, Any]:
    """Get all plans with limits and add-ons."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM plans")
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Plans not found")

    return json.loads(row["data"])


@app.get("/api/company-settings", operation_id="get_company_settings")
def get_company_settings() -> dict[str, Any]:
    """Get company settings including approval limit."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT data FROM company_settings")
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Company settings not found")

    return json.loads(row["data"])


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording() -> dict[str, str]:
    """Get the policy wording text."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT content FROM policy_wording")
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Policy wording not found")

    return {"content": row["content"]}


@app.post("/api/claims/{claim_id}/status", operation_id="update_claim_status")
def update_claim_status(claim_id: str, update: StatusUpdate) -> dict[str, str]:
    """Update a claim's status."""
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE claims SET status = ? WHERE claim_id = ?",
        (update.status, claim_id),
    )
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found")
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, "status": update.status}


@app.post("/api/claims/{claim_id}/decide", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found")

    cursor.execute("SELECT data FROM company_settings")
    settings_row = cursor.fetchone()
    if not settings_row:
        conn.close()
        raise HTTPException(status_code=500, detail="Company settings not found")

    settings = json.loads(settings_row["data"])
    approval_limit = settings["payout_approval_limit"]

    if decision.decision == "approve" and decision.payout > approval_limit:
        status = "waiting_for_signoff"
    elif decision.decision in ("approve", "decline", "refer"):
        status = "decided"
    else:
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid decision")

    cursor.execute(
        """
        UPDATE claims
        SET decision = ?, payout = ?, explanation = ?,
            policy_reference = ?, status = ?
        WHERE claim_id = ?
        """,
        (
            decision.decision,
            decision.payout,
            decision.explanation,
            decision.policy_reference,
            status,
            claim_id,
        ),
    )
    conn.commit()
    conn.close()

    return {
        "claim_id": claim_id,
        "decision": decision.decision,
        "payout": decision.payout,
        "status": status,
    }


@app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay a claim."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM claims WHERE claim_id = ?", (claim_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found")

    claim = row_to_dict(row)

    if claim["status"] not in ("decided", "waiting_for_signoff"):
        conn.close()
        raise HTTPException(
            status_code=400, detail="Claim must be decided before payment"
        )

    cursor.execute("SELECT data FROM company_settings")
    settings_row = cursor.fetchone()
    if not settings_row:
        conn.close()
        raise HTTPException(status_code=500, detail="Company settings not found")

    settings = json.loads(settings_row["data"])
    approval_limit = settings["payout_approval_limit"]

    if payment.amount > approval_limit and claim["status"] == "waiting_for_signoff":
        conn.close()
        raise HTTPException(
            status_code=403, detail="Payment over limit requires sign-off"
        )

    if payment.amount > approval_limit and claim["status"] != "waiting_for_signoff":
        conn.close()
        raise HTTPException(
            status_code=403, detail="Payment over limit requires sign-off"
        )

    cursor.execute(
        "UPDATE claims SET status = 'decided' WHERE claim_id = ?", (claim_id,)
    )
    conn.commit()
    conn.close()

    return {"claim_id": claim_id, "amount": payment.amount, "status": "paid"}
