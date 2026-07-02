# Source Strategy

Hot News Radar uses a source ladder so one blocked or noisy lane does not control the result.

## Default Lanes

| Lane | Best For | Limits |
| --- | --- | --- |
| Google News Top Stories | No-input global hot briefing and regional top-news checks | Aggregator surface; use as a discovery lane, not final verification |
| Google News RSS | Fast mainstream news discovery | Aggregated timestamps can lag or differ from original source time |
| GDELT | Broad global news and policy/event monitoring | May include duplicates and weak summaries |
| RSS/Atom | Official sites, blogs, release feeds, niche communities | Only as good as the feed the user provides |
| Hacker News | Technology, AI, developer, startup narratives | Narrow community and engagement bias |
| Reddit public search | Community sentiment and early reactions | Rate limits, noisy language, API changes |
| Direct URL | User-provided source evidence | HTTP fetch may miss JavaScript or authenticated content |
| Firecrawl-compatible provider | Search/extract fallback when key is available | External provider dependency, quota, and changing API formats |
| Browser rendering | Dynamic page recovery and visible-state review | Must respect access controls and user authorization |
| Authenticated visible review | User-authorized login-gated pages | User completes login directly; capture only task-relevant evidence |

## Currentness Rules

1. Do not treat collection time as publication time.
2. Prefer a source-published timestamp over aggregator timestamps.
3. If only collection time is available, mark the item with a warning.
4. If a topic is old but renewed by a fresh source, record both the original event and renewal source.
5. If a source lane fails, record a coverage gap instead of claiming the topic has no activity.

## Query Planning

Use multiple query shapes for broad topics:

- exact topic name,
- common abbreviation,
- product or entity names,
- negative or risk terms,
- geography or language modifiers,
- relevant community terms.

Keep the first run narrow enough to inspect. Expand only after seeing source health and duplicates.
