import sys

import pytest

from agent import __main__ as cli


def test_cli_continues_after_a_failed_claim(monkeypatch, capsys):
    claims = [{"claim_id": "CLM-1"}, {"claim_id": "CLM-2"}]
    processed = []

    def fake_run(claim_id, thread_id):
        if claim_id == "CLM-1":
            raise RuntimeError("boom")
        processed.append(claim_id)
        return "done"

    monkeypatch.setattr(cli, "get_waiting_claims", lambda: claims)
    monkeypatch.setattr(cli, "run", fake_run)
    monkeypatch.setattr(sys, "argv", ["agent"])
    cli.main()
    out = capsys.readouterr()
    assert processed == ["CLM-2"]
    assert "Completed 1 of 2 claim(s)" in out.out
    assert "CLM-1 failed: boom" in out.err


def test_cli_single_claim(monkeypatch, capsys):
    monkeypatch.setattr(
        cli, "run", lambda claim_id, thread_id: f"{claim_id} {thread_id}"
    )
    monkeypatch.setattr(sys, "argv", ["agent", "CLM-9", "t1"])
    cli.main()
    assert "CLM-9 t1" in capsys.readouterr().out


def test_cli_no_waiting_claims(monkeypatch):
    monkeypatch.setattr(cli, "get_waiting_claims", lambda: [])
    monkeypatch.setattr(sys, "argv", ["agent"])
    with pytest.raises(SystemExit) as exit_info:
        cli.main()
    assert exit_info.value.code == 0
