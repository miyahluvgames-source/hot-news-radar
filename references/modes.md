# Modes

Hot News Radar should feel useful even when the user gives very little direction.

## Mode Table

| Mode | Trigger | Default Sources | Use When |
| --- | --- | --- | --- |
| `global-hot` | No query/feed/URL, or user asks for latest global hot news | Google News Top, Google News search, GDELT, Hacker News | Broad daily/hourly global briefing |
| `general` | User provides a topic but no special intent | Google News, GDELT, Hacker News, Reddit | Mixed news and community scan |
| `news` | User asks for latest news or media coverage | Google News, GDELT | News-first scan |
| `social` | User asks for public reaction or community chatter | Reddit, Hacker News | Community and discussion scan |
| `research` | User asks for background and source discovery | Google News, GDELT, Hacker News | Research lead generation |
| `reputation` | User asks about a brand, product, person, or incident | Google News, GDELT, Reddit | Public reputation and risk scan |
| custom feeds | User supplies `--feed` | RSS/Atom | Official/niche source monitoring |
| direct URL | User supplies `--url` | HTTP fetch and optional browser fallback | Specific source inspection |
| authenticated review | User has an authorized login-gated page | Auth guide plus visible browser | Permissioned evidence review |
| automation | User asks for recurring runs | Automation guide | Scheduled briefings and monitors |
| Telegram delivery | User asks to send output to Telegram | Telegram guide and sender script | Personal or team delivery |

## Default Global-Hot Profile

When the user provides no target, the CLI applies:

```bash
python scripts/hot_news_radar.py --out artifacts
```

Internally it uses a blended public top-news region set:

- US,
- GB,
- SG,
- IN,
- AU,
- CA.

It also uses broad queries:

- breaking news,
- world news,
- global markets,
- technology,
- artificial intelligence,
- science,
- geopolitics.

The profile is intentionally broad. If the user supplies `--region`, the top-news lane narrows to that region. For better precision, ask the user to narrow by topic, region, language, source, or time window after the first run.

## Escalation Rules

- If the user asks "what is hot right now", use `global-hot`.
- If they mention a brand or person, use `reputation`.
- If they mention "what people are saying", use `social`.
- If they mention "sources for a report", use `research`.
- If they mention "send this every day/hour", use `automation`.
- If they mention Telegram, read `telegram-delivery.md`.
- If a page requires login, read `authenticated-sources.md`.
