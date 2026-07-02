# Prompt Pack

## General Hot Topic Scan

```text
Use Hot News Radar to find the strongest public signals for:
<topic>

Window: last 24 hours.
Return top findings with source links, heat scores, evidence class, and coverage gaps.
Do not treat collection time as publication time.
```

## Default Global Hot News

```text
Use Hot News Radar with no query to run the default global-hot profile.

Use the blended global top-news source mix unless I specify a region or language.
Return the strongest recent global news signals, source links, heat scores, evidence classes, and coverage gaps.
```

## Reputation Scan

```text
Use Hot News Radar in reputation mode for:
<brand / product / person>

Look for public news, social discussion, complaints, praise, incidents, and policy or platform changes.
Separate verified findings from weak signals.
Show coverage gaps and sources that need visible review.
```

## Research Scan

```text
Use Hot News Radar in research mode for:
<technology / policy / market / product>

Find recent public sources, cluster the narratives, rank what matters, and list which claims still need primary-source verification.
```

## Custom Feeds

```text
Use Hot News Radar with these feeds:
<feed URLs>

Summarize what is new, deduplicate repeated items, and flag stale or missing publication times.
```

## Authenticated Page Review

```text
Use Hot News Radar for this login-gated page:
<URL>

Generate an authenticated session guide first.
Walk me through the process step by step.
I will complete login, SSO, CAPTCHA, and MFA directly in the visible browser.
Do not ask me to reveal passwords, MFA codes, cookies, tokens, or private account data.
Capture only task-relevant evidence and report any coverage gaps.
```

## Recurring Telegram Briefing

```text
Set up Hot News Radar as a recurring briefing.

Use the default global-hot profile unless I provide a narrower topic.
Generate the automation guide and Telegram delivery guide.
Walk me through BotFather setup, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, dry-run testing, and the final scheduled command.
Do not store or print my bot token in the repository or public logs.
```
