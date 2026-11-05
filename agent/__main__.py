"""Command-line interface for the UnderCover Agent."""

import sys

import httpx

from agent.main import BACKEND_URL, run

THREAD_ID_ARG_INDEX = 2


def get_waiting_claims() -> list[dict]:
    """Fetch all claims with status 'waiting' from the backend."""
    with httpx.Client(base_url=BACKEND_URL, timeout=10) as client:
        response = client.get("/api/claims")
    response.raise_for_status()
    claims = response.json()
    return [c for c in claims if c.get("status") == "waiting"]


def main() -> None:
    """Run the agent from the command line."""
    if len(sys.argv) > 1 and sys.argv[1] in ["--help", "-h"]:
        print("Usage: uv run -m agent [CLAIM_ID] [THREAD_ID]", file=sys.stderr)
        print("\nExamples:", file=sys.stderr)
        print(
            "  uv run -m agent              # Process all waiting claims",
            file=sys.stderr,
        )
        print(
            "  uv run -m agent CLM-1001     # Process specific claim", file=sys.stderr
        )
        print(
            "  uv run -m agent CLM-1001 t1  # Process with custom thread ID",
            file=sys.stderr,
        )
        print("\nEnvironment variables:", file=sys.stderr)
        print(
            "  OPENROUTER_API_KEY - Required: Your OpenRouter API key", file=sys.stderr
        )
        print(
            "  MODEL_NAME - Optional: Model to use (default: openai/gpt-6-luna)",
            file=sys.stderr,
        )
        print(
            "\nNote: Backend must be running at http://localhost:8000", file=sys.stderr
        )
        sys.exit(0)

    try:
        # If no claim ID provided, process all waiting claims
        if len(sys.argv) < 2:  # noqa: PLR2004
            print("Fetching waiting claims from backend...")
            waiting_claims = get_waiting_claims()

            if not waiting_claims:
                print("No waiting claims found.")
                sys.exit(0)

            print(f"Found {len(waiting_claims)} waiting claim(s)\n")

            failed: list[str] = []
            for i, claim in enumerate(waiting_claims, 1):
                claim_id = claim["claim_id"]
                thread_id = f"cli-{claim_id}"
                print(f"[{i}/{len(waiting_claims)}] Processing {claim_id}...")
                try:
                    run(claim_id, thread_id)
                    print(f"{claim_id} processed\n")
                except Exception as e:
                    failed.append(claim_id)
                    print(f"{claim_id} failed: {e}\n", file=sys.stderr)

            done = len(waiting_claims) - len(failed)
            print(f"\nCompleted {done} of {len(waiting_claims)} claim(s)")
            if failed:
                print(f"Failed: {', '.join(failed)}", file=sys.stderr)
        else:
            # Process specific claim
            claim_id = sys.argv[1]
            thread_id = (
                sys.argv[THREAD_ID_ARG_INDEX]
                if len(sys.argv) > THREAD_ID_ARG_INDEX
                else f"cli-{claim_id}"
            )

            print(f"Processing claim {claim_id} with thread {thread_id}...")
            result = run(claim_id, thread_id)
            print(f"\nAgent response:\n{result}")

    except KeyboardInterrupt:
        print("\n\nInterrupted by user", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
