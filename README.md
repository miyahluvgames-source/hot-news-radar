# Hot News Radar

![Hot News Radar cover](assets/hot-news-radar-cover.png)

**Hot News Radar** helps AI agents find, verify, rank, and summarize fresh public signals across news, feeds, social surfaces, research pages, and user-provided URLs.

The core rule:

> Fast discovery is useful only when freshness, provenance, and gaps are visible.

## What It Does

| Layer | Output |
| --- | --- |
| Query plan | Topic, mode, lookback window, source mix, language, region |
| Fast discovery | Google News RSS, GDELT, RSS/Atom feeds, Hacker News, Reddit public search, direct URLs |
| Optional providers | Firecrawl-compatible search when an API key is available |
| Fallback strategy | Browser-render plan or optional Playwright rendering for dynamic pages |
| Evidence ledger | Normalized candidates, source status, coverage gaps, warnings |
| Ranking | Heat score from freshness, relevance, source quality, cross-source consensus, and engagement |
| Report | `radar-report.md`, `candidates.json`, `coverage-gaps.json`, `sources.json`, `brief.json`, `candidates.csv` |

It is designed for broad public use: breaking news, product research, market monitoring, reputation scanning, creator discovery, incident awareness, competitor observation, policy tracking, and community listening.

## Pipeline

```text
topic / query / URL
  -> plan source mix
  -> collect fast public signals
  -> detect blocked or weak evidence
  -> normalize candidates
  -> deduplicate and merge related sources
  -> score freshness, relevance, consensus, authority, engagement
  -> write report, ledger, coverage gaps, and next-step recovery plan
```

## Quick Start: Prompt Install

Paste this into an AI agent that can access GitHub and write local files:

```text
Install Hot News Radar from this public repository:
https://github.com/miyahluvgames-source/hot-news-radar

If you can persist skills in this environment:
1. Clone or download the repository.
2. Install it as a skill named hot-news-radar in the appropriate skill directory for this agent.
3. Include SKILL.md, references, scripts, agents, requirements, Dockerfile, and README.
4. Do not copy .git, artifacts, caches, generated outputs, virtual environments, or temporary files.
5. From the repository root, run python scripts/doctor.py --profile full --repair-plan.
6. If dependencies, tools, provider keys, browser rendering, or Docker are missing, show me the repair options first and ask before changing the system.

If you cannot persist skills:
1. Load SKILL.md and the relevant references for this chat only.
2. Tell me clearly that this is a session-only setup.

Return:
- install mode: persistent or session-only
- installed path, if available
- doctor status
- missing dependencies
- recommended repair plan
- one safe test command or test task I can run next
```

## Local Use

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Check the environment:

```bash
python scripts/doctor.py --profile base --repair-plan
```

Run a general hot-topic radar:

```bash
python scripts/hot_news_radar.py --query "AI agents" --lookback-hours 24 --limit 25
```

Run a crypto and AI focused scan:

```bash
python scripts/hot_news_radar.py \
  --query "crypto AI" \
  --query "agentic AI" \
  --mode news \
  --lookback-hours 12 \
  --limit 40
```

Add custom feeds:

```bash
python scripts/hot_news_radar.py \
  --query "semiconductor export controls" \
  --feed "https://hnrss.org/newest?q=semiconductor" \
  --feed "https://www.theverge.com/rss/index.xml"
```

Inspect direct URLs and generate a browser recovery plan when pages are blocked or dynamic:

```bash
python scripts/hot_news_radar.py \
  --query "product launch" \
  --url "https://example.com/launch" \
  --browser-fallback plan
```

Use optional Playwright rendering for pages that require JavaScript but do not require bypassing access controls:

```bash
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python scripts/hot_news_radar.py \
  --url "https://example.com/live-page" \
  --browser-fallback playwright
```

Enable optional Firecrawl-compatible search when you have a provider key:

```bash
export FIRECRAWL_API_KEY="..."
python scripts/hot_news_radar.py --query "open source AI browser automation" --source firecrawl
```

## Docker

Docker provides a reproducible runtime for users who do not want to manage local Python dependencies manually.

Build the default image:

```bash
docker build --target final -t hot-news-radar:base .
```

Run a scan:

```bash
docker run --rm \
  -v "$PWD/artifacts:/app/artifacts" \
  hot-news-radar:base \
  --query "AI agents" \
  --lookback-hours 24 \
  --out artifacts
```

Build the optional browser image:

```bash
docker build --target browser -t hot-news-radar:browser .
```

Run browser rendering inside Docker:

```bash
docker run --rm \
  -v "$PWD/artifacts:/app/artifacts" \
  hot-news-radar:browser \
  --url "https://example.com/live-page" \
  --browser-fallback playwright \
  --out artifacts
```

## Source Strategy

Hot News Radar uses a source ladder instead of relying on one scraper:

1. **Low-friction public indexes**: RSS, Google News RSS, GDELT, public APIs.
2. **Community signals**: Hacker News and Reddit public endpoints when relevant.
3. **User-provided feeds and URLs**: direct evidence supplied by the user.
4. **Provider APIs**: optional Firecrawl-compatible search and extraction.
5. **Browser rendering**: recovery path for JavaScript-heavy pages, visible-state checks, and dynamic content.
6. **Manual or authenticated review**: for pages that require a user-controlled login session, CAPTCHA, paywall, or permission gate.

The skill does not bypass access controls, paywalls, CAPTCHAs, robots rules, or terms of service. When a page requires authentication or visible review, the report records a coverage gap and gives a safe recovery plan.

## Scoring

Each candidate receives a 0-100 heat score:

| Factor | Weight |
| --- | ---: |
| Freshness | 35 |
| Query relevance | 25 |
| Source authority | 15 |
| Cross-source consensus | 15 |
| Engagement signal | 10 |

The score is a prioritization aid, not proof that a story is true. The report shows the evidence class and coverage gaps so an agent can decide what needs deeper verification.

## Artifact Layout

Each run writes a timestamped folder under `artifacts/`:

```text
artifacts/hot-news-radar-<timestamp>/
├── radar-report.md
├── candidates.json
├── candidates.csv
├── sources.json
├── coverage-gaps.json
└── brief.json
```

## Repository Contents

```text
.
├── SKILL.md
├── README.md
├── agents/openai.yaml
├── scripts/
│   ├── hot_news_radar.py
│   └── doctor.py
├── references/
│   ├── browser-fallbacks.md
│   ├── github-research-notes.md
│   ├── prompt-pack.md
│   ├── scoring.md
│   └── source-strategy.md
├── tests/
├── Dockerfile
├── requirements.txt
├── requirements-browser.txt
└── .github/workflows/ci.yml
```

## Reference Projects

The design borrows public, generalizable ideas from these open-source projects:

- [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl): search, scrape, and structured web context for agents.
- [firecrawl/firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server): MCP-oriented search and scrape workflows.
- [browser-use/browser-use](https://github.com/browser-use/browser-use): browser automation for AI agents.
- [browser-use/browser-harness](https://github.com/browser-use/browser-harness): direct browser harness and self-healing browser tasks.
- [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research): iterative deep research flow with search and extraction.
- [oxylabs/google-news-scraper](https://github.com/oxylabs/google-news-scraper) and [lewisdonovan/google-news-scraper](https://github.com/lewisdonovan/google-news-scraper): fast news discovery patterns.

## Safety Boundaries

- Do not use this skill to bypass login, paywall, CAPTCHA, permission, or anti-abuse controls.
- Do not treat a blocked page, error page, or script failure as negative evidence.
- Do not publish claims from a single weak source without labeling uncertainty.
- Record collection time separately from event time and source publication time.
- Prefer official or primary sources for high-stakes claims.

