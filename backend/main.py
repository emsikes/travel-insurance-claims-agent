"""The UnderCover backend."""

import json
import sqlite3
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from backend.database import get_db, init_db, row_to_dict


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


MAX_ATTEMPTS = 2


class Failure(BaseModel):
    error: str


def fetch_claim(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim's row, or raise 404."""
    row = conn.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Claim not found")
    return row_to_dict(row)


def approval_limit(conn: sqlite3.Connection) -> float:
    """Return the payout approval limit from the company settings."""
    row = conn.execute("SELECT data FROM company_settings").fetchone()
    return json.loads(row["data"])["payout_approval_limit"]


def record_failure(conn: sqlite3.Connection, claim: dict[str, Any]) -> dict[str, Any]:
    """Count a failed attempt: requeue the claim, or leave it for a handler."""
    if claim["decision"] is not None:
        return {
            "claim_id": claim["claim_id"],
            "status": claim["status"],
            "attempts": claim["attempts"],
        }
    attempts = claim["attempts"] + 1
    status = "needs_handler" if attempts >= MAX_ATTEMPTS else "waiting"
    conn.execute(
        "UPDATE claims SET status = ?, attempts = ? WHERE claim_id = ?",
        (status, attempts, claim["claim_id"]),
    )
    return {"claim_id": claim["claim_id"], "status": status, "attempts": attempts}


@app.post("/api/claims/recover", operation_id="recover_claims")
def recover_claims() -> dict[str, list[str]]:
    """Count every undecided claim left in progress as a failed attempt."""
    conn = get_db()
    rows = conn.execute(
        "SELECT * FROM claims WHERE status = 'in_progress' AND decision IS NULL"
    ).fetchall()
    for row in rows:
        record_failure(conn, row_to_dict(row))
    conn.commit()
    conn.close()
    return {"recovered": [row["claim_id"] for row in rows]}


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str) -> dict[str, str]:
    """Start work on a waiting claim."""
    conn = get_db()
    claim = fetch_claim(conn, claim_id)
    cursor = conn.execute(
        "UPDATE claims SET status = 'in_progress' "
        "WHERE claim_id = ? AND status = 'waiting'",
        (claim_id,),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(
            status_code=409, detail=f"Claim is {claim['status']}, not waiting"
        )
    return {"claim_id": claim_id, "status": "in_progress"}


@app.post("/api/claims/{claim_id}/fail", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: Failure) -> dict[str, Any]:
    """Record a failed attempt on a claim."""
    conn = get_db()
    result = record_failure(conn, fetch_claim(conn, claim_id))
    conn.commit()
    conn.close()
    return result


@app.post("/api/claims/{claim_id}/decide", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim in progress."""
    conn = get_db()
    claim = fetch_claim(conn, claim_id)
    if decision.decision not in ("approve", "decline", "refer"):
        conn.close()
        raise HTTPException(status_code=400, detail="Invalid decision")

    over_limit = decision.decision == "approve" and decision.payout > approval_limit(
        conn
    )
    status = "waiting_for_signoff" if over_limit else "decided"
    cursor = conn.execute(
        """
        UPDATE claims
        SET decision = ?, payout = ?, explanation = ?, policy_reference = ?, status = ?
        WHERE claim_id = ? AND status = 'in_progress' AND decision IS NULL
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
    if cursor.rowcount == 0:
        if claim["decision"] is not None:
            raise HTTPException(status_code=409, detail="Claim is already decided")
        raise HTTPException(
            status_code=409, detail=f"Claim is {claim['status']}, not in progress"
        )

    return {
        "claim_id": claim_id,
        "decision": decision.decision,
        "payout": decision.payout,
        "status": status,
    }


@app.post("/api/claims/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay an approved claim."""
    conn = get_db()
    claim = fetch_claim(conn, claim_id)
    if claim["decision"] != "approve":
        conn.close()
        raise HTTPException(
            status_code=400, detail="Claim must be approved before payment"
        )
    if payment.amount > approval_limit(conn):
        conn.close()
        raise HTTPException(
            status_code=403, detail="Payment over limit requires sign-off"
        )

    cursor = conn.execute(
        "UPDATE claims SET paid_amount = ? WHERE claim_id = ? AND paid_amount IS NULL",
        (payment.amount, claim_id),
    )
    conn.commit()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=409, detail="Claim is already paid")

    return {"claim_id": claim_id, "amount": payment.amount, "status": "paid"}


INSTRUCTIONS_DIR = Path(__file__).parent / "instructions"


class Step(BaseModel):
    attempt: int
    kind: Literal["tool_call", "section_read", "result", "error"]
    text: str


class RunStart(BaseModel):
    cap: int


class Todo(BaseModel):
    claim_id: str
    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


class Summary(BaseModel):
    summary: str


def now() -> str:
    """Return the current time in UTC as ISO 8601."""
    return datetime.now(UTC).isoformat()


@app.get("/api/documents/{document}/sections", operation_id="list_sections")
def list_sections(document: str) -> list[dict[str, Any]]:
    """List the numbered sections of the policy wording or the claims manual."""
    conn = get_db()
    rows = conn.execute(
        "SELECT number, title FROM documents WHERE document = ? ORDER BY number",
        (document,),
    ).fetchall()
    conn.close()
    if not rows:
        raise HTTPException(status_code=404, detail="Document not found")
    return [row_to_dict(row) for row in rows]


@app.get("/api/documents/{document}/sections/{number}", operation_id="read_section")
def read_section(document: str, number: int) -> dict[str, Any]:
    """Read one section of the policy wording or the claims manual."""
    conn = get_db()
    row = conn.execute(
        "SELECT number, title, content FROM documents "
        "WHERE document = ? AND number = ?",
        (document, number),
    ).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="Section not found")
    return row_to_dict(row)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record a step the agent took on a claim."""
    conn = get_db()
    fetch_claim(conn, claim_id)
    created_at = now()
    conn.execute(
        "INSERT INTO claim_steps (claim_id, attempt, kind, text, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (claim_id, step.attempt, step.kind, step.text, created_at),
    )
    conn.commit()
    conn.close()
    return {"claim_id": claim_id, **step.model_dump(), "created_at": created_at}


@app.get("/api/claims/{claim_id}/steps", operation_id="get_claim_steps")
def get_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """Get the steps the agent took on a claim, in order."""
    conn = get_db()
    rows = conn.execute(
        "SELECT attempt, kind, text, created_at FROM claim_steps "
        "WHERE claim_id = ? ORDER BY step_id",
        (claim_id,),
    ).fetchall()
    conn.close()
    return [row_to_dict(row) for row in rows]


def run_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a runs row to a dictionary with its todos decoded."""
    run = row_to_dict(row)
    run["todos"] = json.loads(run["todos"])
    return run


@app.post("/api/runs", operation_id="start_run")
def start_run(start: RunStart) -> dict[str, Any]:
    """Start a run of the agent over the queue, capped at a number of claims."""
    run_id = f"RUN-{uuid4().hex[:8]}"
    conn = get_db()
    conn.execute(
        "INSERT INTO runs (run_id, cap, status, todos, started_at) "
        "VALUES (?, ?, 'running', '[]', ?)",
        (run_id, start.cap, now()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    return run_to_dict(row)


def update_run(run_id: str, column: str, value: str) -> dict[str, Any]:
    """Set one column of a run, or raise 404."""
    conn = get_db()
    cursor = conn.execute(
        f"UPDATE runs SET {column} = ? WHERE run_id = ?",  # noqa: S608
        (value, run_id),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    conn.close()
    if cursor.rowcount == 0:
        raise HTTPException(status_code=404, detail="Run not found")
    return run_to_dict(row)


@app.put("/api/runs/{run_id}/todos", operation_id="update_todos")
def update_todos(run_id: str, todos: list[Todo]) -> dict[str, Any]:
    """Replace a run's to-do list."""
    return update_run(
        run_id, "todos", json.dumps([todo.model_dump() for todo in todos])
    )


@app.post("/api/runs/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: str, summary: Summary) -> dict[str, Any]:
    """Finish a run with its summary for the handlers."""
    update_run(run_id, "summary", summary.summary)
    return update_run(run_id, "status", "finished")


@app.get("/api/runs/latest", operation_id="get_latest_run")
def get_latest_run() -> dict[str, Any] | None:
    """Get the most recent run, or null if there has been none."""
    conn = get_db()
    row = conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
    conn.close()
    return run_to_dict(row) if row else None


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> dict[str, str]:
    """Get the agent's instructions for running the queue and working a claim."""
    return {
        name: (INSTRUCTIONS_DIR / f"{name}.md").read_text(encoding="utf-8")
        for name in ("queue", "claim")
    }
