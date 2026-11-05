import contextlib
import json
import time

from backend import seed as seed_cli
from backend.database import DATA_DIR, DB_PATH, get_db, init_db, seed


def setup_module():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def teardown_module():
    if DB_PATH.exists():
        time.sleep(0.1)
        with contextlib.suppress(PermissionError):
            DB_PATH.unlink()


def count_in(file_name: str) -> int:
    with (DATA_DIR / file_name).open() as f:
        return len(json.load(f))


def claim_status(claim_id: str) -> str:
    conn = get_db()
    row = conn.execute(
        "SELECT status FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    conn.close()
    return row["status"]


def test_seed_resets_changed_claims():
    conn = get_db()
    conn.execute("UPDATE claims SET status = 'decided' WHERE claim_id = 'CLM-1001'")
    conn.commit()
    conn.close()
    assert claim_status("CLM-1001") == "decided"

    seed()

    assert claim_status("CLM-1001") == "waiting"


def test_seed_counts_match_data():
    assert seed() == {
        "claims": count_in("claims.json"),
        "policies": count_in("policies.json"),
        "customers": count_in("customers.json"),
        "handlers": count_in("handlers.json"),
    }


def test_seed_works_without_a_database():
    DB_PATH.unlink()

    counts = seed()

    assert counts["claims"] == count_in("claims.json")


def test_main_prints_counts(capsys):
    seed_cli.main()

    out = capsys.readouterr().out
    assert f"Seeded {count_in('claims.json')} claims" in out
    assert DB_PATH.name in out
