"""Claims: reading them, their lifecycle from waiting to decided, and their steps."""

import json
import sqlite3
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import connect

MAX_ATTEMPTS = 2

router = APIRouter(prefix="/api/claims")


class Decision(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float
    explanation: str
    policy_reference: str


class Payment(BaseModel):
    amount: float


class Failure(BaseModel):
    error: str


class Step(BaseModel):
    attempt: int
    kind: Literal["tool_call", "section_read", "result", "error"]
    text: str


def now() -> str:
    """Return the current time in UTC as ISO 8601."""
    return datetime.now(UTC).isoformat()


def claim_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a claims row to a dictionary with its items and documents decoded."""
    claim = dict(row)
    claim["items"] = json.loads(claim["items"])
    claim["documents"] = json.loads(claim["documents"])
    return claim


def fetch_claim(conn: sqlite3.Connection, claim_id: str) -> dict[str, Any]:
    """Return a claim, or raise 404."""
    row = conn.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim_to_dict(row)


def approval_limit(conn: sqlite3.Connection) -> float:
    """Return the payout approval limit from the company settings."""
    row = conn.execute("SELECT data FROM company_settings").fetchone()
    return json.loads(row["data"])["payout_approval_limit"]


def record_failure(conn: sqlite3.Connection, claim: dict[str, Any]) -> dict[str, Any]:
    """Count a failed attempt: requeue the claim, or leave it for a handler."""
    result = {key: claim[key] for key in ("claim_id", "status", "attempts")}
    if claim["decision"] is not None:
        return result
    result["attempts"] += 1
    result["status"] = (
        "needs_handler" if result["attempts"] >= MAX_ATTEMPTS else "waiting"
    )
    conn.execute(
        "UPDATE claims SET status = ?, attempts = ? WHERE claim_id = ?",
        (result["status"], result["attempts"], claim["claim_id"]),
    )
    return result


@router.get("", operation_id="get_claims")
def get_claims() -> list[dict[str, Any]]:
    """Get all claims."""
    with connect() as conn:
        rows = conn.execute("SELECT * FROM claims").fetchall()
    return [claim_to_dict(row) for row in rows]


@router.get("/waiting", operation_id="get_waiting_claims")
def get_waiting_claims() -> list[dict[str, Any]]:
    """Get the waiting claims in brief, for the agent to plan its run."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT claim_id, summary, claim_type, amount_claimed, attempts "
            "FROM claims WHERE status = 'waiting'"
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str) -> dict[str, Any]:
    """Get a specific claim by ID."""
    with connect() as conn:
        return fetch_claim(conn, claim_id)


@router.post("/recover", operation_id="recover_claims")
def recover_claims() -> dict[str, list[str]]:
    """Count every undecided claim left in progress as a failed attempt."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM claims WHERE status = 'in_progress' AND decision IS NULL"
        ).fetchall()
        for row in rows:
            record_failure(conn, claim_to_dict(row))
    return {"recovered": [row["claim_id"] for row in rows]}


@router.post("/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str) -> dict[str, Any]:
    """Start work on a waiting claim."""
    with connect() as conn:
        claim = fetch_claim(conn, claim_id)
        started = conn.execute(
            "UPDATE claims SET status = 'in_progress' "
            "WHERE claim_id = ? AND status = 'waiting'",
            (claim_id,),
        )
        if started.rowcount == 0:
            raise HTTPException(
                status_code=409, detail=f"Claim is {claim['status']}, not waiting"
            )
    return {
        "claim_id": claim_id,
        "status": "in_progress",
        "attempts": claim["attempts"],
    }


@router.post("/{claim_id}/fail", operation_id="fail_claim")
def fail_claim(claim_id: str, failure: Failure) -> dict[str, Any]:
    """Record a failed attempt on a claim."""
    with connect() as conn:
        return record_failure(conn, fetch_claim(conn, claim_id))


@router.post("/{claim_id}/decide", operation_id="decide_claim")
def decide_claim(claim_id: str, decision: Decision) -> dict[str, Any]:
    """Record a decision on a claim in progress."""
    with connect() as conn:
        claim = fetch_claim(conn, claim_id)
        over_limit = decision.decision == "approve" and (
            decision.payout > approval_limit(conn)
        )
        status = "waiting_for_signoff" if over_limit else "decided"
        decided = conn.execute(
            "UPDATE claims SET decision = ?, payout = ?, explanation = ?, "
            "policy_reference = ?, status = ? "
            "WHERE claim_id = ? AND status = 'in_progress' AND decision IS NULL",
            (
                decision.decision,
                decision.payout,
                decision.explanation,
                decision.policy_reference,
                status,
                claim_id,
            ),
        )
        if decided.rowcount == 0 and claim["decision"] is not None:
            raise HTTPException(status_code=409, detail="Claim is already decided")
        if decided.rowcount == 0:
            raise HTTPException(
                status_code=409, detail=f"Claim is {claim['status']}, not in progress"
            )
    return {
        "claim_id": claim_id,
        "decision": decision.decision,
        "payout": decision.payout,
        "status": status,
    }


@router.post("/{claim_id}/pay", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: Payment) -> dict[str, Any]:
    """Pay an approved claim."""
    with connect() as conn:
        claim = fetch_claim(conn, claim_id)
        if claim["decision"] != "approve":
            raise HTTPException(
                status_code=400, detail="Claim must be approved before payment"
            )
        if payment.amount > approval_limit(conn):
            raise HTTPException(
                status_code=403, detail="Payment over limit requires sign-off"
            )
        paid = conn.execute(
            "UPDATE claims SET paid_amount = ? "
            "WHERE claim_id = ? AND paid_amount IS NULL",
            (payment.amount, claim_id),
        )
        if paid.rowcount == 0:
            raise HTTPException(status_code=409, detail="Claim is already paid")
    return {"claim_id": claim_id, "amount": payment.amount, "status": "paid"}


@router.post("/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: Step) -> dict[str, Any]:
    """Record a step the agent took on a claim."""
    created_at = now()
    with connect() as conn:
        fetch_claim(conn, claim_id)
        conn.execute(
            "INSERT INTO claim_steps (claim_id, attempt, kind, text, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (claim_id, step.attempt, step.kind, step.text, created_at),
        )
    return {"claim_id": claim_id, **step.model_dump(), "created_at": created_at}


@router.get("/{claim_id}/steps", operation_id="get_claim_steps")
def get_claim_steps(claim_id: str) -> list[dict[str, Any]]:
    """Get the steps the agent took on a claim, in order."""
    with connect() as conn:
        rows = conn.execute(
            "SELECT attempt, kind, text, created_at FROM claim_steps "
            "WHERE claim_id = ? ORDER BY step_id",
            (claim_id,),
        ).fetchall()
    return [dict(row) for row in rows]
