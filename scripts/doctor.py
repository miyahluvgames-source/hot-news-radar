#!/usr/bin/env python3
"""Environment doctor for Hot News Radar."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Check:
    name: str
    ok: bool
    detail: str
    repair: str = ""


def has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def command_version(command: list[str]) -> tuple[bool, str]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15)
        output = (result.stdout or result.stderr).strip().splitlines()
        detail = output[0] if output else f"exit {result.returncode}"
        return result.returncode == 0, detail
    except Exception as exc:
        return False, str(exc)


def base_checks() -> list[Check]:
    checks = [
        Check("python>=3.10", sys.version_info >= (3, 10), sys.version.split()[0], "Install Python 3.10 or newer."),
    ]
    for module in ("requests", "feedparser", "bs4", "dateutil"):
        checks.append(
            Check(
                f"python-module:{module}",
                has_module(module),
                "installed" if has_module(module) else "missing",
                "python -m pip install -r requirements.txt",
            )
        )
    return checks


def browser_checks() -> list[Check]:
    checks = [
        Check("python-module:playwright", has_module("playwright"), "installed" if has_module("playwright") else "missing", "python -m pip install -r requirements-browser.txt"),
    ]
    ok, detail = command_version([sys.executable, "-m", "playwright", "--version"])
    checks.append(Check("playwright-cli", ok, detail, "python -m pip install -r requirements-browser.txt && python -m playwright install chromium"))
    return checks


def provider_checks() -> list[Check]:
    key_name = "FIRECRAWL_API_KEY"
    return [
        Check(
            "provider-env:FIRECRAWL_API_KEY",
            bool(os.getenv(key_name)),
            "set" if os.getenv(key_name) else "not set",
            "Set FIRECRAWL_API_KEY only if you want optional Firecrawl-compatible search.",
        )
    ]


def docker_checks() -> list[Check]:
    docker = shutil.which("docker")
    if not docker:
        return [Check("docker", False, "missing", "Install Docker Desktop or use local Python mode.")]
    ok, detail = command_version(["docker", "--version"])
    return [Check("docker", ok, detail, "Start Docker Desktop or repair Docker installation.")]


def collect(profile: str) -> list[Check]:
    checks = base_checks()
    if profile in ("browser", "full"):
        checks.extend(browser_checks())
    if profile in ("providers", "full"):
        checks.extend(provider_checks())
    if profile == "full":
        checks.extend(docker_checks())
    return checks


def markdown(checks: list[Check], repair_plan: bool) -> str:
    lines = ["# Hot News Radar Doctor", "", "| Check | Status | Detail |", "| --- | --- | --- |"]
    for check in checks:
        lines.append(f"| {check.name} | {'PASS' if check.ok else 'MISSING'} | {check.detail} |")
    if repair_plan:
        repairs = [check.repair for check in checks if not check.ok and check.repair]
        if repairs:
            lines.extend(["", "## Repair Plan", ""])
            for repair in dict.fromkeys(repairs):
                lines.append(f"- `{repair}`")
        else:
            lines.extend(["", "No repair actions needed."])
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Hot News Radar dependencies.")
    parser.add_argument("--profile", choices=["base", "browser", "providers", "full"], default="base")
    parser.add_argument("--repair-plan", action="store_true")
    parser.add_argument("--format", choices=["json", "markdown"], default="json")
    args = parser.parse_args(argv)
    checks = collect(args.profile)
    payload: dict[str, Any] = {
        "profile": args.profile,
        "ok": all(check.ok for check in checks if not check.name.startswith("provider-env:")),
        "checks": [asdict(check) for check in checks],
        "repair_plan": list(dict.fromkeys(check.repair for check in checks if not check.ok and check.repair)) if args.repair_plan else [],
    }
    if args.format == "markdown":
        print(markdown(checks, args.repair_plan), end="")
    else:
        print(json.dumps(payload, indent=2))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

