"""Rebuild the database from data/, with: uv run -m backend.seed"""

from backend.database import DB_PATH, seed


def main() -> None:
    """Rebuild the database and say what it holds."""
    counts = seed()
    print(
        f"Seeded {counts['claims']} claims, {counts['policies']} policies, "
        f"{counts['customers']} customers and {counts['handlers']} handlers "
        f"into {DB_PATH.name}"
    )


if __name__ == "__main__":
    main()
