# Automation

Use this reference when the user wants Hot News Radar to run on a schedule.

## Default Behavior

If the user does not provide a query, URL, feed, region, or source, run the default `global-hot` profile:

```bash
python scripts/hot_news_radar.py --out artifacts
```

This searches recent global hot news across blended public top-news regions plus broad news, technology, AI, science, market, and geopolitics queries. Users can narrow it with `--query`, `--region`, `--language`, `--mode`, `--source`, `--feed`, or `--url`.

## Standard Automation Flow

1. Define the task: global hot news, topic scan, reputation scan, research scan, or custom feed scan.
2. Choose the schedule:
   - 15-60 minutes for breaking incidents,
   - daily for general briefings,
   - weekly for slow research topics.
3. Run a manual test first.
4. Run `python scripts/doctor.py --profile full --repair-plan`.
5. Decide where reports should be stored.
6. Decide whether Telegram delivery is needed.
7. If Telegram delivery is needed, create a bot, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, run a dry run, then schedule the sender.
8. If login-gated pages are required, use `--auth-session-guide`; do not run unattended credential flows.
9. Make failures visible: source health and coverage gaps should be preserved.

## Recommended Commands

Default global briefing:

```bash
python scripts/hot_news_radar.py --out artifacts
```

Topic briefing:

```bash
python scripts/hot_news_radar.py --query "AI agents" --lookback-hours 24 --limit 30 --out artifacts
```

Generate setup guides:

```bash
python scripts/hot_news_radar.py --automation-guide --telegram-guide --out artifacts
```

## Cron

```cron
0 * * * * cd /path/to/hot-news-radar && /usr/bin/python3 scripts/hot_news_radar.py --out artifacts >> logs/hot-news-radar.log 2>&1
```

## Windows Task Scheduler

Use:

- Program: `python`
- Arguments: `scripts/hot_news_radar.py --out artifacts`
- Start in: repository root

## GitHub Actions

Use repository or organization secrets for Telegram tokens. Do not commit secrets.

```yaml
on:
  schedule:
    - cron: "0 * * * *"
  workflow_dispatch:
jobs:
  radar:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: python -m pip install -r requirements.txt
      - run: python scripts/hot_news_radar.py --out artifacts
      - uses: actions/upload-artifact@v4
        with:
          name: hot-news-radar
          path: artifacts
```
