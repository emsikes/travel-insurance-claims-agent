"""The agents' one client for the UnderCover backend."""

from functools import cache
from typing import Any

import httpx

from agent.config import BACKEND_TIMEOUT_SECONDS, BACKEND_URL


@cache
def client() -> httpx.Client:
    """Return the client shared by every call, so connections are reused."""
    return httpx.Client(base_url=BACKEND_URL, timeout=BACKEND_TIMEOUT_SECONDS)


def error_text(response: httpx.Response) -> str:
    """Describe an error response in a line."""
    return f"Error {response.status_code}: {response.text}"


def request(method: str, path: str, body: Any = None) -> Any:
    """Call the backend for the harness: raise on an error, else return the JSON."""
    response = client().request(method, path, json=body)
    response.raise_for_status()
    return response.json()


def for_model(method: str, path: str, body: Any = None) -> Any:
    """Call the backend for a tool: return errors as text the model can act on."""
    response = client().request(method, path, json=body)
    return error_text(response) if response.is_error else response.json()


def instructions(name: str) -> str:
    """Get the agent's instructions for the queue or for a claim."""
    return request("GET", "/api/instructions")[name]
