import importlib

from agent import config


def test_urls_come_from_the_environment(monkeypatch):
    monkeypatch.setattr("dotenv.load_dotenv", lambda **kwargs: None)
    monkeypatch.setenv("BACKEND_URL", "http://backend.test:9000")
    monkeypatch.setenv("OPENROUTER_BASE_URL", "http://router.test/v1")
    try:
        reloaded = importlib.reload(config)
        assert reloaded.BACKEND_URL == "http://backend.test:9000"
        assert reloaded.OPENROUTER_BASE_URL == "http://router.test/v1"
    finally:
        monkeypatch.undo()
        importlib.reload(config)


def test_model_defaults_to_deepseek(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    default = config.model()
    assert default.model_name == "deepseek/deepseek-v4.1-flash"
    assert default.reasoning_effort == "low"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert config.model().model_name == "openrouter/free"
    assert config.model().reasoning_effort is None
