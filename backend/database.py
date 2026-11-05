"""Database initialization and access."""

import json
import sqlite3
from pathlib import Path
from typing import Any

DB_PATH = Path("undercover.db")
DATA_DIR = Path("data")


def get_db() -> sqlite3.Connection:
    """Get a database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Initialize the database with schema and data."""
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            claim_id TEXT PRIMARY KEY,
            policy_id TEXT NOT NULL,
            customer_id TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            submitted_on TEXT NOT NULL,
            incident_date TEXT NOT NULL,
            incident_location TEXT NOT NULL,
            summary TEXT NOT NULL,
            story TEXT NOT NULL,
            items TEXT NOT NULL,
            amount_claimed REAL NOT NULL,
            documents TEXT NOT NULL,
            status TEXT DEFAULT 'waiting',
            decision TEXT,
            payout REAL,
            explanation TEXT,
            policy_reference TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policies (
            policy_id TEXT PRIMARY KEY,
            customer_id TEXT NOT NULL,
            plan TEXT NOT NULL,
            add_ons TEXT NOT NULL,
            purchased_on TEXT NOT NULL,
            sold_through TEXT NOT NULL,
            trip TEXT NOT NULL,
            travelers TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            address TEXT NOT NULL,
            customer_since TEXT NOT NULL,
            previous_claims TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS plans (
            data TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS company_settings (
            data TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS policy_wording (
            content TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS handlers (
            handler_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT NOT NULL,
            can_approve_over_limit INTEGER NOT NULL
        )
    """)

    conn.commit()
    load_data(conn)
    conn.close()


def load_data(conn: sqlite3.Connection) -> None:
    """Load data from JSON files into the database."""
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM claims")
    if cursor.fetchone()[0] > 0:
        return

    claims_file = DATA_DIR / "claims.json"
    with claims_file.open() as f:
        claims = json.load(f)
    for claim in claims:
        cursor.execute(
            """
            INSERT INTO claims (
                claim_id, policy_id, customer_id, claim_type,
                submitted_on, incident_date, incident_location,
                summary, story, items, amount_claimed, documents
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                claim["claim_id"],
                claim["policy_id"],
                claim["customer_id"],
                claim["claim_type"],
                claim["submitted_on"],
                claim["incident_date"],
                claim["incident_location"],
                claim["summary"],
                claim["story"],
                json.dumps(claim["items"]),
                claim["amount_claimed"],
                json.dumps(claim["documents"]),
            ),
        )

    policies_file = DATA_DIR / "policies.json"
    with policies_file.open() as f:
        policies = json.load(f)
    for policy in policies:
        cursor.execute(
            """
            INSERT INTO policies (
                policy_id, customer_id, plan, add_ons,
                purchased_on, sold_through, trip, travelers, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                policy["policy_id"],
                policy["customer_id"],
                policy["plan"],
                json.dumps(policy["add_ons"]),
                policy["purchased_on"],
                policy["sold_through"],
                json.dumps(policy["trip"]),
                json.dumps(policy["travelers"]),
                policy["status"],
            ),
        )

    customers_file = DATA_DIR / "customers.json"
    with customers_file.open() as f:
        customers = json.load(f)
    for customer in customers:
        cursor.execute(
            """
            INSERT INTO customers (
                customer_id, name, email, phone, date_of_birth,
                address, customer_since, previous_claims
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                customer["customer_id"],
                customer["name"],
                customer["email"],
                customer["phone"],
                customer["date_of_birth"],
                json.dumps(customer["address"]),
                customer["customer_since"],
                json.dumps(customer["previous_claims"]),
            ),
        )

    plans_file = DATA_DIR / "plans.json"
    with plans_file.open() as f:
        plans_data = f.read()
    cursor.execute("INSERT INTO plans (data) VALUES (?)", (plans_data,))

    company_file = DATA_DIR / "company.json"
    with company_file.open() as f:
        company_data = f.read()
    cursor.execute("INSERT INTO company_settings (data) VALUES (?)", (company_data,))

    policy_wording_file = DATA_DIR / "policy_wording.md"
    with policy_wording_file.open() as f:
        policy_wording = f.read()
    cursor.execute("INSERT INTO policy_wording (content) VALUES (?)", (policy_wording,))

    handlers_file = DATA_DIR / "handlers.json"
    with handlers_file.open() as f:
        handlers = json.load(f)
    for handler in handlers:
        cursor.execute(
            """
            INSERT INTO handlers (
                handler_id, name, role, email, can_approve_over_limit
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                handler["handler_id"],
                handler["name"],
                handler["role"],
                handler["email"],
                1 if handler["can_approve_over_limit"] else 0,
            ),
        )

    conn.commit()


def seed() -> dict[str, int]:
    """Rebuild the database from data/ and return how many rows each table holds."""
    conn = get_db()
    conn.executescript("""
        DROP TABLE IF EXISTS claims;
        DROP TABLE IF EXISTS policies;
        DROP TABLE IF EXISTS customers;
        DROP TABLE IF EXISTS plans;
        DROP TABLE IF EXISTS company_settings;
        DROP TABLE IF EXISTS policy_wording;
        DROP TABLE IF EXISTS handlers;
    """)
    conn.close()
    init_db()

    conn = get_db()
    counts = {
        "claims": conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0],
        "policies": conn.execute("SELECT COUNT(*) FROM policies").fetchone()[0],
        "customers": conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0],
        "handlers": conn.execute("SELECT COUNT(*) FROM handlers").fetchone()[0],
    }
    conn.close()
    return counts


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a database row to a dictionary."""
    return dict(row)
