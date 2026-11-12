"""The agent's settings, read from the environment, and its model."""

import os

from dotenv import load_dotenv
from langchain.agents.middleware import ModelRetryMiddleware
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:8000")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
DEFAULT_MODEL = "deepseek/deepseek-v4.1-flash"
MODEL_TIMEOUT_SECONDS = 120
BACKEND_TIMEOUT_SECONDS = 30
MAX_RETRIES = 2
RETRY_DELAY_SECONDS = 2.0


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or DeepSeek V4.1 Flash by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
        timeout=MODEL_TIMEOUT_SECONDS,
    )


def retry() -> ModelRetryMiddleware:
    """Retry timeouts and provider errors on a model call."""
    return ModelRetryMiddleware(
        max_retries=MAX_RETRIES,
        initial_delay=RETRY_DELAY_SECONDS,
        on_failure="error",
    )
