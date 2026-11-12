"""Run the UnderCover Agent from the command line."""

import argparse

from agent.claim import work
from agent.queue_agent import run_queue


def main(argv: list[str] | None = None) -> None:
    """Work the whole queue, a run capped at a number of claims, or one named claim."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent",
        description="Run the UnderCover Agent. The backend must be running.",
        epilog=(
            "examples: 'uv run -m agent' works the whole queue, "
            "'uv run -m agent --cap 5' works five claims, "
            "'uv run -m agent CLM-1001' works one claim"
        ),
    )
    parser.add_argument("claim_id", nargs="?", help="work only this claim")
    parser.add_argument("--cap", type=int, help="work at most this many claims")
    args = parser.parse_args(argv)

    if args.claim_id:
        print(work(args.claim_id, "cli").line)
    else:
        print(run_queue(args.cap))


if __name__ == "__main__":
    main()
