import contextlib
import time

from fastapi.testclient import TestClient

from backend.database import DB_PATH, init_db
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


def test_update_claim_status():
    response = client.post(
        "/api/claims/CLM-1001/status", json={"status": "in_progress"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-1001"
    assert data["status"] == "in_progress"

    response = client.get("/api/claims/CLM-1001")
    assert response.json()["status"] == "in_progress"


def test_update_claim_status_not_found():
    response = client.post(
        "/api/claims/CLM-9999/status", json={"status": "in_progress"}
    )
    assert response.status_code == 404


def test_decide_claim_approve_under_limit():
    response = client.post(
        "/api/claims/CLM-1002/decide",
        json={
            "decision": "approve",
            "payout": 500.0,
            "explanation": "Claim approved under limit",
            "policy_reference": "Section 3",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-1002"
    assert data["decision"] == "approve"
    assert data["payout"] == 500.0
    assert data["status"] == "decided"


def test_decide_claim_approve_over_limit():
    response = client.post(
        "/api/claims/CLM-1003/decide",
        json={
            "decision": "approve",
            "payout": 1500.0,
            "explanation": "Claim approved but over limit",
            "policy_reference": "Section 3",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-1003"
    assert data["decision"] == "approve"
    assert data["payout"] == 1500.0
    assert data["status"] == "waiting_for_signoff"


def test_decide_claim_decline():
    response = client.post(
        "/api/claims/CLM-1004/decide",
        json={
            "decision": "decline",
            "payout": 0.0,
            "explanation": "Claim declined",
            "policy_reference": "Section 2",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "decline"
    assert data["status"] == "decided"


def test_decide_claim_refer():
    response = client.post(
        "/api/claims/CLM-1005/decide",
        json={
            "decision": "refer",
            "payout": 0.0,
            "explanation": "Needs manual review",
            "policy_reference": "Section 1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "refer"
    assert data["status"] == "decided"


def test_pay_claim_under_limit():
    client.post(
        "/api/claims/CLM-1006/decide",
        json={
            "decision": "approve",
            "payout": 800.0,
            "explanation": "Approved",
            "policy_reference": "Section 3",
        },
    )
    response = client.post("/api/claims/CLM-1006/pay", json={"amount": 800.0})
    assert response.status_code == 200
    data = response.json()
    assert data["claim_id"] == "CLM-1006"
    assert data["amount"] == 800.0
    assert data["status"] == "paid"


def test_pay_claim_over_limit_without_signoff():
    client.post(
        "/api/claims/CLM-1007/decide",
        json={
            "decision": "approve",
            "payout": 1200.0,
            "explanation": "Approved but needs sign-off",
            "policy_reference": "Section 3",
        },
    )
    response = client.post("/api/claims/CLM-1007/pay", json={"amount": 1200.0})
    assert response.status_code == 403


def test_pay_claim_not_decided():
    response = client.post("/api/claims/CLM-1008/pay", json={"amount": 500.0})
    assert response.status_code == 400


def test_pay_claim_not_found():
    response = client.post("/api/claims/CLM-9999/pay", json={"amount": 500.0})
    assert response.status_code == 404
