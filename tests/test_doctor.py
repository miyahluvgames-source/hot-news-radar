from __future__ import annotations

from scripts.doctor import collect
from scripts.doctor import main


def test_base_doctor_has_core_checks() -> None:
    checks = collect("base")
    names = {check.name for check in checks}
    assert "python>=3.10" in names
    assert "python-module:requests" in names
    assert "python-module:feedparser" in names


def test_telegram_doctor_reports_optional_delivery_checks(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)
    checks = collect("telegram")
    names = {check.name for check in checks}
    assert "env:TELEGRAM_BOT_TOKEN" in names
    assert "env:TELEGRAM_CHAT_ID" in names
    assert main(["--profile", "telegram", "--repair-plan"]) == 0
