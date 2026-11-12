"""What the UnderCover Agent's queue agent and claim agent share."""

from typing import Any

import httpx

from agent.config import BACKEND_TIMEOUT_SECONDS, BACKEND_URL, model

__all__ = ["call", "instructions", "model"]


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=BACKEND_TIMEOUT_SECONDS)


def call(method: str, path: str, body: Any = None) -> Any:
    """Call the backend, returning errors as text so the model can correct itself."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Error {response.status_code}: {response.text}"
    return response.json()


def instructions(name: str) -> str:
    """Get the agent's instructions for the queue or for a claim from the backend."""
    with backend() as client:
        response = client.get("/api/instructions")
    response.raise_for_status()
    return response.json()[name]
