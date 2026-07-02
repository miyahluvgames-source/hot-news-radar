# GitHub Research Notes

Hot News Radar is a standalone public skill. It does not vendor these projects, but it borrows general design lessons from their public patterns.

## Reference Projects

Star counts were observed on 2026-07-02 and are only a rough popularity signal.

| Project | Useful Pattern Adopted |
| --- | --- |
| [firecrawl/firecrawl](https://github.com/firecrawl/firecrawl) | 142k+ stars; treat search, scrape, and structured extraction as separate provider-adapter stages |
| [browser-use/browser-use](https://github.com/browser-use/browser-use) | 102k+ stars; use browser automation as an agent-visible action surface when static fetch is insufficient |
| [dzhng/deep-research](https://github.com/dzhng/deep-research) | 19k+ stars; keep iterative research loops understandable and easy to inspect |
| [browser-use/browser-harness](https://github.com/browser-use/browser-harness) | 15k+ stars; prefer direct, inspectable browser state for dynamic tasks that need visible recovery |
| [firecrawl/firecrawl-mcp-server](https://github.com/firecrawl/firecrawl-mcp-server) | 6k+ stars; make web context usable by AI agents through clear tool contracts |
| [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | 6k+ stars; split broad research into iterative search, extraction, and synthesis |
| [oxylabs/google-news-scraper](https://github.com/oxylabs/google-news-scraper) | 3k+ stars; use news discovery as a quick first-pass signal source |
| [lewisdonovan/google-news-scraper](https://github.com/lewisdonovan/google-news-scraper) | Lightweight normalized article objects from news queries |

## Resulting Design Choices

- Source adapters are independent and can fail without collapsing the whole run.
- Every run writes machine-readable evidence and human-readable reports.
- Browser fallback is explicit and safe; it does not claim to bypass access controls.
- Provider APIs are optional, not required.
- Coverage gaps are first-class output.
