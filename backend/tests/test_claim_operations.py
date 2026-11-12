import contextlib
import time

from fastapi.testclient import TestClient

from backend.database import DB_PATH, get_db, init_db, seed
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


def decide(claim_id: str, decision: str, payout: float):
    return client.post(
        f"/api/claims/{claim_id}/decide",
        json={
            "decision": decision,
            "payout": payout,
            "explanation": "Reason",
            "policy_reference": "Section 3",
        },
    )


def start_and_decide(claim_id: str, decision: str, payout: float):
    client.post(f"/api/claims/{claim_id}/start")
    return decide(claim_id, decision, payout)


def fail(claim_id: str):
    return client.post(f"/api/claims/{claim_id}/fail", json={"error": "timeout"})


def claim(claim_id: str) -> dict:
    return client.get(f"/api/claims/{claim_id}").json()


def test_start_claim():
    response = client.post("/api/claims/CLM-1001/start")
    assert response.status_code == 200
    assert claim("CLM-1001")["status"] == "in_progress"


def test_start_claim_twice_is_refused():
    client.post("/api/claims/CLM-1010/start")
    response = client.post("/api/claims/CLM-1010/start")
    assert response.status_code == 409


def test_start_claim_not_found():
    assert client.post("/api/claims/CLM-9999/start").status_code == 404


def test_status_endpoint_is_gone():
    response = client.post("/api/claims/CLM-1001/status", json={"status": "waiting"})
    assert response.status_code in (404, 405)


def test_decide_claim_approve_under_limit():
    response = start_and_decide("CLM-1002", "approve", 500.0)
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "approve"
    assert data["payout"] == 500.0
    assert data["status"] == "decided"


def test_decide_claim_approve_over_limit():
    response = start_and_decide("CLM-1003", "approve", 1500.0)
    assert response.json()["status"] == "waiting_for_signoff"


def test_decide_claim_decline():
    response = start_and_decide("CLM-1004", "decline", 0.0)
    assert response.json()["decision"] == "decline"
    assert response.json()["status"] == "decided"


def test_decide_claim_refer():
    response = start_and_decide("CLM-1005", "refer", 0.0)
    assert response.json()["status"] == "decided"


def test_decide_claim_invalid_decision():
    response = start_and_decide("CLM-1011", "maybe", 0.0)
    assert response.status_code == 400


def test_decide_claim_twice_is_refused():
    start_and_decide("CLM-1012", "decline", 0.0)
    response = decide("CLM-1012", "approve", 900.0)
    assert response.status_code == 409
    assert claim("CLM-1012")["decision"] == "decline"


def test_decide_claim_not_in_progress_is_refused():
    response = decide("CLM-1013", "approve", 100.0)
    assert response.status_code == 409
    assert claim("CLM-1013")["decision"] is None


def test_decide_claim_not_found():
    assert decide("CLM-9999", "approve", 1.0).status_code == 404


def test_pay_claim_under_limit():
    start_and_decide("CLM-1006", "approve", 800.0)
    response = client.post("/api/claims/CLM-1006/pay", json={"amount": 800.0})
    assert response.status_code == 200
    assert response.json()["status"] == "paid"
    assert claim("CLM-1006")["paid_amount"] == 800.0


def test_pay_claim_twice_is_refused():
    start_and_decide("CLM-1014", "approve", 300.0)
    client.post("/api/claims/CLM-1014/pay", json={"amount": 300.0})
    response = client.post("/api/claims/CLM-1014/pay", json={"amount": 300.0})
    assert response.status_code == 409
    assert claim("CLM-1014")["paid_amount"] == 300.0


def test_pay_claim_over_limit_without_signoff():
    start_and_decide("CLM-1007", "approve", 1200.0)
    response = client.post("/api/claims/CLM-1007/pay", json={"amount": 1200.0})
    assert response.status_code == 403
    assert claim("CLM-1007")["paid_amount"] is None


def test_pay_claim_not_decided():
    response = client.post("/api/claims/CLM-1008/pay", json={"amount": 500.0})
    assert response.status_code == 400


def test_pay_declined_claim_is_refused():
    start_and_decide("CLM-1015", "decline", 0.0)
    response = client.post("/api/claims/CLM-1015/pay", json={"amount": 10.0})
    assert response.status_code == 400


def test_pay_claim_not_found():
    response = client.post("/api/claims/CLM-9999/pay", json={"amount": 500.0})
    assert response.status_code == 404


def test_first_failure_requeues_and_second_leaves_for_handler():
    client.post("/api/claims/CLM-1016/start")
    first = fail("CLM-1016").json()
    assert first == {"claim_id": "CLM-1016", "status": "waiting", "attempts": 1}

    client.post("/api/claims/CLM-1016/start")
    second = fail("CLM-1016").json()
    assert second["status"] == "needs_handler"
    assert second["attempts"] == 2
    assert client.post("/api/claims/CLM-1016/start").status_code == 409


def test_failing_a_decided_claim_changes_nothing():
    start_and_decide("CLM-1017", "decline", 0.0)
    result = fail("CLM-1017").json()
    assert result["status"] == "decided"
    assert result["attempts"] == 0
    assert claim("CLM-1017")["decision"] == "decline"


def test_fail_claim_not_found():
    assert fail("CLM-9999").status_code == 404


def test_recover_claims_requeues_stuck_claims():
    client.post("/api/claims/CLM-1018/start")
    response = client.post("/api/claims/recover")
    assert "CLM-1018" in response.json()["recovered"]
    assert "CLM-1002" not in response.json()["recovered"]
    stuck = claim("CLM-1018")
    assert stuck["status"] == "waiting"
    assert stuck["attempts"] == 1


def test_seed_resets_attempts_and_payments():
    conn = get_db()
    conn.execute("UPDATE claims SET attempts = 2, paid_amount = 5 WHERE 1 = 1")
    conn.commit()
    conn.close()
    seed()
    reset = claim("CLM-1001")
    assert reset["attempts"] == 0
    assert reset["paid_amount"] is None
