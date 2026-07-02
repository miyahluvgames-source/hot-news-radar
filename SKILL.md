---
name: hot-news-radar
description: Find, verify, rank, and summarize fresh public news, trend, research, social, and reputation signals. Use when the user asks for hot topics, latest news, emerging narratives, public sentiment, source discovery, coverage gaps, or fast multi-source monitoring across the web.
metadata:
  short-description: Multi-source hot-topic radar for AI agents
---

# Hot News Radar

Use this skill when a user wants current or recent public signals: breaking news, hot topics, trend discovery, social/reputation monitoring, public-source research, competitor observation, policy tracking, product launch monitoring, or community sentiment.

## Operating Rules

1. Separate **discovery** from **verification**. Fast source collection finds candidates; evidence checks decide what can be claimed.
2. Track three times when possible: event time, source publication time, and collection time.
3. Record coverage gaps. A failed source, blocked page, login gate, CAPTCHA, JS-only page, or error page is not evidence of absence.
4. Do not bypass access controls, paywalls, CAPTCHAs, robots rules, or terms of service.
5. Prefer primary or authoritative sources for high-stakes claims.
6. For authorized login-gated pages, guide the user through a visible session; the user handles credentials and MFA directly.
7. If the user asks for "latest", run live collection or state that the answer is not live-verified.

## Quick Workflow

1. Clarify the target only when necessary: topic, geography, language, time window, and source type.
2. If the user gives no target, run default global hot news:

   ```bash
   python scripts/hot_news_radar.py --out artifacts
   ```

3. Run the CLI when deterministic collection is useful:

   ```bash
   python scripts/hot_news_radar.py --query "AI agents" --lookback-hours 24 --limit 25
   ```

4. For custom sources, add feeds or URLs:

   ```bash
   python scripts/hot_news_radar.py --query "topic" --feed "https://example.com/rss" --url "https://example.com/page"
   ```

5. If a page is blocked, dynamic, or login-gated, use `--browser-fallback plan` first. Use `--browser-fallback playwright` only for pages that can be safely rendered without bypassing access controls.
6. If the user is authorized to access a login-gated page, add `--auth-session-guide` and follow `authenticated-session-guide.md` step by step.
7. If the user asks for recurring runs, add `--automation-guide`; if they want Telegram delivery, add `--telegram-guide` and read `references/telegram-delivery.md`.
8. Read `radar-report.md`, `coverage-gaps.json`, and `candidates.json` before summarizing.
9. Report top findings with source links, heat score, evidence class, and remaining gaps.

## When To Read References

- Read `references/source-strategy.md` when choosing source lanes for a new domain.
- Read `references/modes.md` when selecting default, global, social, research, reputation, automation, or delivery behavior.
- Read `references/browser-fallbacks.md` when pages are blocked, dynamic, logged-in, or inconsistent.
- Read `references/authenticated-sources.md` before guiding a user through a logged-in account or workspace.
- Read `references/automation.md` when a user asks for a recurring run, monitor, scheduled briefing, or automation.
- Read `references/telegram-delivery.md` when a user wants reports delivered to Telegram.
- Read `references/scoring.md` when adjusting ranking or explaining heat scores.
- Read `references/prompt-pack.md` for user-facing prompt templates.
- Read `references/github-research-notes.md` when explaining the public open-source design influences.

## Doctor

Use the doctor before installing or debugging:

```bash
python scripts/doctor.py --profile base --repair-plan
python scripts/doctor.py --profile full --repair-plan --format markdown
```

The doctor prints missing dependencies and repair commands. It does not silently modify the user's machine.

## Output Contract

Every serious run should produce:

- `radar-report.md`: readable report with top candidates, source health, and gaps.
- `candidates.json`: normalized evidence ledger.
- `coverage-gaps.json`: failed, partial, blocked, or skipped source details.
- `sources.json`: adapter status.
- `brief.json`: compact summary for downstream agents.

When answering the user, include:

- what was searched,
- time window,
- strongest findings,
- evidence links,
- what failed or still needs visible/manual review.
- whether an authenticated session was used, without exposing account secrets or unrelated private data.
