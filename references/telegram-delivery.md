# Telegram Delivery

Use this reference when the user wants Hot News Radar reports sent to Telegram.

## Setup

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot`.
3. Choose a bot name and username.
4. Copy the bot token and store it as a secret.
5. Open a chat with the bot and send any test message, or add the bot to a group/channel.
6. Get the chat ID:
   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` after sending a message.
   - Find `chat.id` in the JSON response.
   - For channels or groups, make sure the bot has permission to post.
7. Store values in environment variables or the host secret manager.

## Environment Variables

```bash
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."
```

PowerShell:

```powershell
$env:TELEGRAM_BOT_TOKEN = "..."
$env:TELEGRAM_CHAT_ID = "..."
```

## Check Setup

```bash
python scripts/doctor.py --profile telegram --repair-plan --format markdown
```

## Dry Run

```bash
python scripts/telegram_notify.py --file artifacts/<run>/radar-report.md --dry-run
```

## Send A Report

```bash
python scripts/telegram_notify.py --file artifacts/<run>/radar-report.md --title "Hot News Radar"
```

## Automation Example

```bash
RUN_DIR=$(python scripts/hot_news_radar.py --out artifacts | tail -n 1)
python scripts/telegram_notify.py --file "$RUN_DIR/radar-report.md" --title "Hot News Radar"
```

## Safety

- Do not commit bot tokens or chat IDs.
- Do not print secrets into shared logs.
- Do not send private account data, credentials, cookies, tokens, or unrelated personal information.
- For frequent schedules, send summaries and preserve full artifacts locally.
- If Telegram delivery fails, keep the report artifact and show the failure in the automation log.

