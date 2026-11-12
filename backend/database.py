"""The database: its schema, its connections and loading it from data/."""

import json
import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "undercover.db"
DATA_DIR = ROOT / "data"
DOCUMENTS = {
    "policy_wording": ("policy_wording.md", "Policy wording"),
    "claims_manual": ("claims_manual.md", "Claims manual"),
}
SECTION_HEADING = re.compile(r"^## (\d+)\. (.+)$", re.MULTILINE)

TABLES = {
    "claims": """
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
        policy_reference TEXT,
        attempts INTEGER NOT NULL DEFAULT 0,
        paid_amount REAL
    """,
    "policies": """
        policy_id TEXT PRIMARY KEY,
        customer_id TEXT NOT NULL,
        plan TEXT NOT NULL,
        add_ons TEXT NOT NULL,
        purchased_on TEXT NOT NULL,
        sold_through TEXT NOT NULL,
        trip TEXT NOT NULL,
        travelers TEXT NOT NULL,
        status TEXT NOT NULL
    """,
    "customers": """
        customer_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        phone TEXT NOT NULL,
        date_of_birth TEXT NOT NULL,
        address TEXT NOT NULL,
        customer_since TEXT NOT NULL,
        previous_claims TEXT NOT NULL
    """,
    "plans": "data TEXT NOT NULL",
    "company_settings": "data TEXT NOT NULL",
    "handlers": """
        handler_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        email TEXT NOT NULL,
        can_approve_over_limit INTEGER NOT NULL
    """,
    "documents": """
        document TEXT NOT NULL,
        number INTEGER NOT NULL,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        PRIMARY KEY (document, number)
    """,
    "claim_steps": """
        step_id INTEGER PRIMARY KEY AUTOINCREMENT,
        claim_id TEXT NOT NULL,
        attempt INTEGER NOT NULL,
        kind TEXT NOT NULL,
        text TEXT NOT NULL,
        created_at TEXT NOT NULL
    """,
    "runs": """
        run_id TEXT PRIMARY KEY,
        cap INTEGER NOT NULL,
        status TEXT NOT NULL,
        todos TEXT NOT NULL,
        summary TEXT,
        started_at TEXT NOT NULL
    """,
}


def get_db() -> sqlite3.Connection:
    """Open a database connection whose rows read like dictionaries."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    """Open a connection, commit if the block succeeds, and always close it."""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    """Create any missing tables and load data/ into an empty database."""
    with connect() as conn:
        for name, columns in TABLES.items():
            conn.execute(f"CREATE TABLE IF NOT EXISTS {name} ({columns})")
        if conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] == 0:
            load_data(conn)


def split_sections(text: str) -> list[tuple[int, str, str]]:
    """Split a document at its numbered ## headings into (number, title, content)."""
    headings = list(SECTION_HEADING.finditer(text))
    ends = [h.start() for h in headings[1:]] + [len(text)]
    return [
        (int(h.group(1)), h.group(2).strip(), text[h.start() : end].strip())
        for h, end in zip(headings, ends, strict=True)
    ]


def read_json(file_name: str) -> list[dict]:
    """Read one of the JSON files in data/."""
    with (DATA_DIR / file_name).open() as f:
        return json.load(f)


def load_data(conn: sqlite3.Connection) -> None:
    """Load the business data from data/, never data/evals/."""
    conn.executemany(
        "INSERT INTO claims (claim_id, policy_id, customer_id, claim_type, "
        "submitted_on, incident_date, incident_location, summary, story, items, "
        "amount_claimed, documents) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                c["claim_id"],
                c["policy_id"],
                c["customer_id"],
                c["claim_type"],
                c["submitted_on"],
                c["incident_date"],
                c["incident_location"],
                c["summary"],
                c["story"],
                json.dumps(c["items"]),
                c["amount_claimed"],
                json.dumps(c["documents"]),
            )
            for c in read_json("claims.json")
        ],
    )
    conn.executemany(
        "INSERT INTO policies (policy_id, customer_id, plan, add_ons, purchased_on, "
        "sold_through, trip, travelers, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                p["policy_id"],
                p["customer_id"],
                p["plan"],
                json.dumps(p["add_ons"]),
                p["purchased_on"],
                p["sold_through"],
                json.dumps(p["trip"]),
                json.dumps(p["travelers"]),
                p["status"],
            )
            for p in read_json("policies.json")
        ],
    )
    conn.executemany(
        "INSERT INTO customers (customer_id, name, email, phone, date_of_birth, "
        "address, customer_since, previous_claims) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            (
                c["customer_id"],
                c["name"],
                c["email"],
                c["phone"],
                c["date_of_birth"],
                json.dumps(c["address"]),
                c["customer_since"],
                json.dumps(c["previous_claims"]),
            )
            for c in read_json("customers.json")
        ],
    )
    conn.executemany(
        "INSERT INTO handlers (handler_id, name, role, email, can_approve_over_limit) "
        "VALUES (?, ?, ?, ?, ?)",
        [
            (
                h["handler_id"],
                h["name"],
                h["role"],
                h["email"],
                int(h["can_approve_over_limit"]),
            )
            for h in read_json("handlers.json")
        ],
    )
    for table, file_name in (
        ("plans", "plans.json"),
        ("company_settings", "company.json"),
    ):
        text = (DATA_DIR / file_name).read_text(encoding="utf-8")
        conn.execute(f"INSERT INTO {table} (data) VALUES (?)", (text,))  # noqa: S608
    for document, (file_name, _) in DOCUMENTS.items():
        text = (DATA_DIR / file_name).read_text(encoding="utf-8")
        conn.executemany(
            "INSERT INTO documents (document, number, title, content) "
            "VALUES (?, ?, ?, ?)",
            [(document, *section) for section in split_sections(text)],
        )


def seed() -> dict[str, int]:
    """Rebuild the database from data/ and return how many rows each table holds."""
    with connect() as conn:
        for name in TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {name}")
    init_db()
    with connect() as conn:
        return {
            name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]  # noqa: S608
            for name in ("claims", "policies", "customers", "handlers")
        }
