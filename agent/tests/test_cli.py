import pytest

from agent import __main__ as cli


def test_cli_works_the_queue(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_queue", lambda cap: f"summary, cap {cap}")
    cli.main([])
    assert "summary, cap None" in capsys.readouterr().out


def test_cli_caps_the_run(monkeypatch, capsys):
    monkeypatch.setattr(cli, "run_queue", lambda cap: f"summary, cap {cap}")
    cli.main(["--cap", "5"])
    assert "summary, cap 5" in capsys.readouterr().out


def test_cli_works_one_claim(monkeypatch, capsys):
    monkeypatch.setattr(cli, "work", lambda claim_id, prefix: f"{claim_id} {prefix}")
    cli.main(["CLM-1009"])
    assert "CLM-1009 cli" in capsys.readouterr().out


def test_cli_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "--cap" in out
    assert "CLM-1001" in out
