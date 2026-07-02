#!/usr/bin/env python3
"""Send a Hot News Radar report to Telegram."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Iterable

import requests


MAX_TELEGRAM_TEXT = 3900


def chunks(text: str, max_chars: int = MAX_TELEGRAM_TEXT) -> Iterable[str]:
    remaining = text.strip()
    while remaining:
        if len(remaining) <= max_chars:
            yield remaining
            break
        split_at = remaining.rfind("\n", 0, max_chars)
        if split_at < max_chars // 2:
            split_at = max_chars
        yield remaining[:split_at].strip()
        remaining = remaining[split_at:].strip()


def load_message(path: Path, title: str) -> str:
    text = path.read_text(encoding="utf-8")
    if title:
        return f"{title}\n\n{text}"
    return text


def send_message(token: str, chat_id: str, text: str, parse_mode: str | None, api_base: str) -> dict:
    payload = {
        "chat_id": chat_id,
        "text": text,
        "disable_web_page_preview": True,
    }
    if parse_mode:
        payload["parse_mode"] = parse_mode
    response = requests.post(f"{api_base}/bot{token}/sendMessage", json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Send a Hot News Radar report to Telegram.")
    parser.add_argument("--file", required=True, help="Report file to send, usually radar-report.md.")
    parser.add_argument("--title", default="", help="Optional message title.")
    parser.add_argument("--token-env", default="TELEGRAM_BOT_TOKEN")
    parser.add_argument("--chat-id-env", default="TELEGRAM_CHAT_ID")
    parser.add_argument("--api-base", default="https://api.telegram.org")
    parser.add_argument("--parse-mode", choices=["Markdown", "HTML", "none"], default="none")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    path = Path(args.file)
    if not path.exists():
        print(f"Report file not found: {path}", file=sys.stderr)
        return 2
    message = load_message(path, args.title)
    parts = list(chunks(message))
    if args.dry_run:
        print(f"Would send {len(parts)} Telegram message chunk(s) from {path}.")
        return 0

    token = os.getenv(args.token_env)
    chat_id = os.getenv(args.chat_id_env)
    if not token or not chat_id:
        print(
            f"Missing {args.token_env} or {args.chat_id_env}. "
            "See references/telegram-delivery.md or generate --telegram-guide.",
            file=sys.stderr,
        )
        return 2
    parse_mode = None if args.parse_mode == "none" else args.parse_mode
    for index, part in enumerate(parts, 1):
        result = send_message(token, chat_id, part, parse_mode, args.api_base)
        message_id = result.get("result", {}).get("message_id", "unknown")
        print(f"sent chunk {index}/{len(parts)} message_id={message_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
