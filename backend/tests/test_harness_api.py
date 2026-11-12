import contextlib
import time

from fastapi.testclient import TestClient

from backend.database import DB_PATH, get_db, init_db, split_sections
from backend.main import app


def setup_module():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def teardown_module():
    if DB_PATH.exists():
        time.sleep(0.1)
        with contextlib.suppress(PermissionError):
            DB_PATH.unlink()


client = TestClient(app)


def test_split_sections():
    text = "# Title\n\nIntro.\n\n## 1. First\n\nOne.\n\n## 2. Second\n\nTwo.\n"
    assert split_sections(text) == [
        (1, "First", "## 1. First\n\nOne."),
        (2, "Second", "## 2. Second\n\nTwo."),
    ]


def test_claims_manual_sections():
    sections = client.get("/api/documents/claims_manual/sections").json()
    assert len(sections) == 14
    assert {"number": 9, "title": "Repeat claims"} in sections
    assert {"number": 10, "title": "Meals without receipts"} in sections


def test_policy_wording_sections():
    sections = client.get("/api/documents/policy_wording/sections").json()
    assert len(sections) == 12
    assert sections[0] == {"number": 1, "title": "Your plan"}


def test_read_section():
    section = client.get("/api/documents/claims_manual/sections/9").json()
    assert section["title"] == "Repeat claims"
    assert section["content"].startswith("## 9. Repeat claims")
    assert "## 10." not in section["content"]
    assert "Meals without receipts" not in section["content"]


def test_unknown_document_or_section():
    assert client.get("/api/documents/evals/sections").status_code == 404
    response = client.get("/api/documents/claims_manual/sections/99")
    assert response.status_code == 404


def test_steps_in_order():
    for text in ("Read the claim", "Claims manual 9. Repeat claims"):
        response = client.post(
            "/api/claims/CLM-1001/steps",
            json={"attempt": 1, "kind": "tool_call", "text": text},
        )
        assert response.status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [s["text"] for s in steps] == [
        "Read the claim",
        "Claims manual 9. Repeat claims",
    ]
    assert steps[0]["attempt"] == 1


def test_step_on_unknown_claim():
    response = client.post(
        "/api/claims/CLM-9999/steps",
        json={"attempt": 1, "kind": "error", "text": "boom"},
    )
    assert response.status_code == 404


def test_step_with_unknown_kind():
    response = client.post(
        "/api/claims/CLM-1001/steps",
        json={"attempt": 1, "kind": "thinking", "text": "hmm"},
    )
    assert response.status_code == 422


def test_run_with_todos():
    run = client.post("/api/runs", json={"cap": 5}).json()
    assert run["status"] == "running"
    assert run["todos"] == []
    todos = [
        {"claim_id": "CLM-1001", "content": "Work CLM-1001", "status": "done"},
        {"claim_id": "", "content": "Write the summary", "status": "to_do"},
    ]
    response = client.put(f"/api/runs/{run['run_id']}/todos", json=todos)
    assert response.status_code == 200

    latest = client.get("/api/runs/latest").json()
    assert latest["run_id"] == run["run_id"]
    assert latest["cap"] == 5
    assert latest["todos"] == todos


def test_todo_with_unknown_status():
    run = client.post("/api/runs", json={"cap": 1}).json()
    response = client.put(
        f"/api/runs/{run['run_id']}/todos",
        json=[{"claim_id": "CLM-1", "content": "x", "status": "skipped"}],
    )
    assert response.status_code == 422


def test_finish_run():
    run = client.post("/api/runs", json={"cap": 2}).json()
    finished = client.post(
        f"/api/runs/{run['run_id']}/finish", json={"summary": "Two claims done."}
    ).json()
    assert finished["status"] == "finished"
    assert finished["summary"] == "Two claims done."


def test_unknown_run():
    response = client.put("/api/runs/RUN-nope/todos", json=[])
    assert response.status_code == 404


def test_no_runs_yet():
    conn = get_db()
    conn.execute("DELETE FROM runs")
    conn.commit()
    conn.close()
    response = client.get("/api/runs/latest")
    assert response.status_code == 200
    assert response.json() is None


def test_instructions():
    instructions = client.get("/api/instructions").json()
    assert set(instructions) == {"queue", "claim"}
    assert instructions["queue"]
    assert instructions["claim"]
