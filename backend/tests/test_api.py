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


def test_get_claims():
    response = client.get("/api/claims")
    assert response.status_code == 200
    claims = response.json()
    assert isinstance(claims, list)
    assert len(claims) == 25
    assert claims[0]["claim_id"] == "CLM-1001"


def test_get_claim():
    response = client.get("/api/claims/CLM-1001")
    assert response.status_code == 200
    claim = response.json()
    assert claim["claim_id"] == "CLM-1001"
    assert claim["policy_id"] == "POL-2001"
    assert claim["customer_id"] == "CUS-3001"
    assert isinstance(claim["items"], list)
    assert isinstance(claim["documents"], list)


def test_get_claim_not_found():
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404


def test_get_policy():
    response = client.get("/api/policies/POL-2001")
    assert response.status_code == 200
    policy = response.json()
    assert policy["policy_id"] == "POL-2001"
    assert policy["customer_id"] == "CUS-3001"
    assert policy["plan"] == "premium"
    assert isinstance(policy["add_ons"], list)
    assert isinstance(policy["trip"], dict)
    assert isinstance(policy["travelers"], list)


def test_get_policy_not_found():
    response = client.get("/api/policies/POL-9999")
    assert response.status_code == 404


def test_get_customer():
    response = client.get("/api/customers/CUS-3001")
    assert response.status_code == 200
    customer = response.json()
    assert customer["customer_id"] == "CUS-3001"
    assert customer["name"] == "Maya Patel"
    assert "email" in customer
    assert "phone" in customer
    assert "date_of_birth" in customer
    assert isinstance(customer["address"], dict)
    assert isinstance(customer["previous_claims"], list)


def test_get_customer_for_agent():
    response = client.get("/api/customers/CUS-3001/agent")
    assert response.status_code == 200
    customer = response.json()
    assert customer["customer_id"] == "CUS-3001"
    assert customer["name"] == "Maya Patel"
    assert "email" not in customer
    assert "phone" not in customer
    assert "date_of_birth" not in customer
    assert "address" not in customer
    assert isinstance(customer["previous_claims"], list)


def test_get_customer_not_found():
    response = client.get("/api/customers/CUS-9999")
    assert response.status_code == 404


def test_get_plans():
    response = client.get("/api/plans")
    assert response.status_code == 200
    data = response.json()
    assert "plans" in data
    assert "add_ons" in data
    assert len(data["plans"]) == 3


def test_get_company_settings():
    response = client.get("/api/company-settings")
    assert response.status_code == 200
    settings = response.json()
    assert settings["payout_approval_limit"] == 1000.0


def test_get_policy_wording():
    response = client.get("/api/policy-wording")
    assert response.status_code == 200
    data = response.json()
    assert "content" in data
    assert "UnderCover Travel Insurance" in data["content"]
