"""Runs of the agent over the queue, with their to-do lists and summaries."""

import json
import sqlite3
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.claims import now
from backend.database import connect

router = APIRouter(prefix="/api/runs")


class RunStart(BaseModel):
    cap: int


class Todo(BaseModel):
    claim_id: str
    content: str
    status: Literal["to_do", "in_progress", "done", "left_for_handler"]


class Summary(BaseModel):
    summary: str


def fetch_run(conn: sqlite3.Connection, run_id: str) -> dict[str, Any]:
    """Return a run with its todos decoded, or raise 404."""
    row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    return {**dict(row), "todos": json.loads(row["todos"])}


@router.post("", operation_id="start_run")
def start_run(start: RunStart) -> dict[str, Any]:
    """Start a run of the agent over the queue, capped at a number of claims."""
    run_id = f"RUN-{uuid4().hex[:8]}"
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, cap, status, todos, started_at) "
            "VALUES (?, ?, 'running', '[]', ?)",
            (run_id, start.cap, now()),
        )
        return fetch_run(conn, run_id)


@router.put("/{run_id}/todos", operation_id="update_todos")
def update_todos(run_id: str, todos: list[Todo]) -> dict[str, Any]:
    """Replace a run's to-do list."""
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET todos = ? WHERE run_id = ?",
            (json.dumps([todo.model_dump() for todo in todos]), run_id),
        )
        return fetch_run(conn, run_id)


@router.post("/{run_id}/finish", operation_id="finish_run")
def finish_run(run_id: str, summary: Summary) -> dict[str, Any]:
    """Finish a run with its summary for the handlers."""
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET summary = ?, status = 'finished' WHERE run_id = ?",
            (summary.summary, run_id),
        )
        return fetch_run(conn, run_id)


@router.get("/latest", operation_id="get_latest_run")
def get_latest_run() -> dict[str, Any] | None:
    """Get the most recent run, or null if there has been none."""
    with connect() as conn:
        row = conn.execute(
            "SELECT run_id FROM runs ORDER BY started_at DESC LIMIT 1"
        ).fetchone()
        return fetch_run(conn, row["run_id"]) if row else None
