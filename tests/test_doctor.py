from __future__ import annotations

from scripts.doctor import collect


def test_base_doctor_has_core_checks() -> None:
    checks = collect("base")
    names = {check.name for check in checks}
    assert "python>=3.10" in names
    assert "python-module:requests" in names
    assert "python-module:feedparser" in names

