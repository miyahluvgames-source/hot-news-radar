#!/usr/bin/env python3
"""Multi-source hot-topic radar for AI agents."""

from __future__ import annotations

import argparse
import calendar
import csv
import hashlib
import html
import json
import math
import os
import re
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus, urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as date_parser


USER_AGENT = "HotNewsRadar/1.0 (+https://github.com/miyahluvgames-source/hot-news-radar)"
DEFAULT_GLOBAL_HOT_QUERIES = [
    "breaking news",
    "world news",
    "global markets",
    "technology",
    "artificial intelligence",
    "science",
    "geopolitics",
]
DEFAULT_GLOBAL_HOT_REGIONS = ["US", "GB", "SG", "IN", "AU", "CA"]
BLOCKED_HINTS = (
    "captcha",
    "access denied",
    "checking your browser",
    "enable javascript",
    "sign in to continue",
    "login to continue",
    "something went wrong",
    "temporarily unavailable",
    "unusual traffic",
    "verify you are human",
)


@dataclass
class Candidate:
    title: str
    url: str
    source: str
    source_kind: str
    summary: str = ""
    published_at: str | None = None
    collected_at: str = ""
    evidence_class: str = "public_index"
    query: str = ""
    engagement: int = 0
    heat_score: float = 0.0
    trend_label: str = "watch"
    age_hours: float | None = None
    source_count: int = 1
    merged_sources: list[str] = field(default_factory=list)
    related_urls: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class SourceStatus:
    name: str
    status: str
    collected: int = 0
    message: str = ""


@dataclass
class CoverageGap:
    source: str
    url: str = ""
    reason: str = ""
    recovery: str = ""
    severity: str = "medium"


@dataclass
class AuthGuide:
    path: str = ""
    urls: list[str] = field(default_factory=list)
    required: bool = False


@dataclass
class RunGuides:
    default_profile: str = ""
    automation_guide_path: str = ""
    telegram_guide_path: str = ""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso_now() -> str:
    return utc_now().isoformat(timespec="seconds")


def safe_filename(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower())
    return cleaned.strip("-")[:80] or "run"


def parse_datetime(value: Any) -> str | None:
    if not value:
        return None
    if isinstance(value, time.struct_time):
        return datetime.fromtimestamp(calendar.timegm(value), timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat(timespec="seconds")
    if isinstance(value, str):
        try:
            dt = date_parser.parse(value)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
        except Exception:
            return None
    return None


def age_hours(published_at: str | None, now: datetime) -> float | None:
    if not published_at:
        return None
    try:
        dt = date_parser.parse(published_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0.0, (now - dt.astimezone(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return None


def text_fingerprint(title: str, url: str) -> str:
    parsed = urlparse(url)
    canonical = f"{parsed.netloc.lower()}{parsed.path.rstrip('/')}"
    if canonical and canonical != "":
        return hashlib.sha1(canonical.encode("utf-8")).hexdigest()
    normalized = re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()


def equivalent_url(left: str, right: str) -> bool:
    left_parsed = urlparse(left)
    right_parsed = urlparse(right)
    if not left_parsed.netloc or not right_parsed.netloc:
        return left.rstrip("/") == right.rstrip("/")
    left_key = f"{left_parsed.netloc.lower()}{left_parsed.path.rstrip('/')}"
    right_key = f"{right_parsed.netloc.lower()}{right_parsed.path.rstrip('/')}"
    return left_key == right_key


def query_terms(queries: list[str]) -> list[str]:
    terms: set[str] = set()
    for query in queries:
        for term in re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", query.lower()):
            terms.add(term)
    return sorted(terms)


def contains_blocked_hint(text: str) -> str | None:
    compact = re.sub(r"\s+", " ", text.lower())
    for hint in BLOCKED_HINTS:
        if hint in compact:
            return hint
    return None


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT, "Accept": "text/html,application/json,application/rss+xml,*/*"})
    return s


def google_news_language_code(language: str | None) -> str:
    if not language:
        return "en"
    return language.split("-")[0].lower() or "en"


def google_news_regions(args: argparse.Namespace) -> list[str]:
    if getattr(args, "region", ""):
        return [args.region.upper()]
    if getattr(args, "mode", "") == "global-hot":
        return DEFAULT_GLOBAL_HOT_REGIONS
    return ["US"]


def collect_google_news_top(args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    hl = args.language or "en-US"
    lang = google_news_language_code(hl)
    for gl in google_news_regions(args):
        per_region_limit = args.limit if args.region else max(5, min(args.limit, 12))
        ceid = f"{gl}:{lang}"
        feed_url = f"https://news.google.com/rss?hl={hl}&gl={gl}&ceid={ceid}"
        try:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False):
                gaps.append(CoverageGap(source="google-news-top", url=feed_url, reason=str(feed.bozo_exception), recovery="Retry later or switch to query-based Google News RSS."))
            for entry in feed.entries[:per_region_limit]:
                source_name = getattr(getattr(entry, "source", None), "title", "")
                out.append(
                    Candidate(
                        title=html.unescape(getattr(entry, "title", "")).strip(),
                        url=getattr(entry, "link", ""),
                        source=source_name or f"Google News Top Stories {gl}",
                        source_kind="google-news-top",
                        summary=BeautifulSoup(getattr(entry, "summary", ""), "html.parser").get_text(" ", strip=True),
                        published_at=parse_datetime(getattr(entry, "published_parsed", None) or getattr(entry, "published", None)),
                        collected_at=collected_at,
                        evidence_class="news_index",
                        query="",
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="google-news-top", url=feed_url, reason=str(exc), recovery="Retry later or use query-based sources, GDELT, or custom feeds."))
    regions = ",".join(google_news_regions(args))
    return out, SourceStatus(name="google-news-top", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates across {regions}"), gaps


def collect_google_news(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    hl = args.language or "en-US"
    gl = args.region or "US"
    ceid = f"{gl}:{google_news_language_code(hl)}"
    status = SourceStatus(name="google-news-rss", status="ok")
    for query in queries:
        encoded = quote_plus(f"{query} when:{max(1, int(args.lookback_hours // 24) or 1)}d")
        feed_url = f"https://news.google.com/rss/search?q={encoded}&hl={hl}&gl={gl}&ceid={ceid}"
        try:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False):
                gaps.append(CoverageGap(source="google-news-rss", url=feed_url, reason=str(feed.bozo_exception), recovery="Retry later or add direct RSS feeds for this topic."))
            for entry in feed.entries[: args.limit]:
                out.append(
                    Candidate(
                        title=html.unescape(getattr(entry, "title", "")).strip(),
                        url=getattr(entry, "link", ""),
                        source=getattr(getattr(entry, "source", None), "title", "Google News"),
                        source_kind="google-news",
                        summary=BeautifulSoup(getattr(entry, "summary", ""), "html.parser").get_text(" ", strip=True),
                        published_at=parse_datetime(getattr(entry, "published_parsed", None) or getattr(entry, "published", None)),
                        collected_at=collected_at,
                        evidence_class="news_index",
                        query=query,
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="google-news-rss", url=feed_url, reason=str(exc), recovery="Retry the feed or use GDELT, custom RSS, or a provider search adapter."))
    status.collected = len(out)
    status.status = "ok" if out else "partial"
    status.message = f"{len(out)} candidates"
    return out, status, gaps


def collect_gdelt(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    s = session()
    for query in queries:
        params = {
            "query": query,
            "mode": "ArtList",
            "format": "json",
            "maxrecords": str(min(args.limit, 100)),
            "sort": "DateDesc",
        }
        try:
            res = s.get("https://api.gdeltproject.org/api/v2/doc/doc", params=params, timeout=args.timeout)
            if res.status_code >= 400:
                gaps.append(CoverageGap(source="gdelt", url=res.url, reason=f"HTTP {res.status_code}", recovery="Retry later or narrow the query."))
                continue
            data = res.json()
            for item in data.get("articles", [])[: args.limit]:
                out.append(
                    Candidate(
                        title=item.get("title", "").strip(),
                        url=item.get("url", ""),
                        source=item.get("sourcecountry", "") or item.get("domain", "GDELT"),
                        source_kind="gdelt",
                        summary=item.get("seendate", ""),
                        published_at=parse_datetime(item.get("seendate")),
                        collected_at=collected_at,
                        evidence_class="news_index",
                        query=query,
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="gdelt", reason=str(exc), recovery="Retry later or use Google News RSS/custom feeds."))
    status = SourceStatus(name="gdelt", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates")
    return out, status, gaps


def collect_hacker_news(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    s = session()
    for query in queries:
        try:
            res = s.get(
                "https://hn.algolia.com/api/v1/search_by_date",
                params={"query": query, "tags": "story", "hitsPerPage": min(args.limit, 50)},
                timeout=args.timeout,
            )
            if res.status_code >= 400:
                gaps.append(CoverageGap(source="hacker-news", url=res.url, reason=f"HTTP {res.status_code}", recovery="Retry later or remove this lane for non-technical topics."))
                continue
            for item in res.json().get("hits", [])[: args.limit]:
                url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
                out.append(
                    Candidate(
                        title=item.get("title") or item.get("story_title") or "",
                        url=url,
                        source="Hacker News",
                        source_kind="hacker-news",
                        summary=f"{item.get('points') or 0} points, {item.get('num_comments') or 0} comments",
                        published_at=parse_datetime(item.get("created_at")),
                        collected_at=collected_at,
                        evidence_class="community_index",
                        query=query,
                        engagement=int(item.get("points") or 0) + int(item.get("num_comments") or 0),
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="hacker-news", reason=str(exc), recovery="Retry later or use another community lane."))
    status = SourceStatus(name="hacker-news", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates")
    return out, status, gaps


def collect_reddit(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    s = session()
    subreddits = args.subreddit or [None]
    for query in queries:
        for subreddit in subreddits:
            base = f"https://www.reddit.com/r/{subreddit}/search.json" if subreddit else "https://www.reddit.com/search.json"
            params = {"q": query, "sort": "new", "t": "day", "limit": min(args.limit, 50)}
            if subreddit:
                params["restrict_sr"] = "1"
            try:
                res = s.get(base, params=params, timeout=args.timeout)
                if res.status_code in (401, 403, 429):
                    gaps.append(CoverageGap(source="reddit", url=res.url, reason=f"HTTP {res.status_code}", recovery="Use an official API route, reduce rate, or review in a user-controlled browser session."))
                    continue
                if res.status_code >= 400:
                    gaps.append(CoverageGap(source="reddit", url=res.url, reason=f"HTTP {res.status_code}", recovery="Retry later or narrow by subreddit."))
                    continue
                data = res.json()
                for child in data.get("data", {}).get("children", [])[: args.limit]:
                    item = child.get("data", {})
                    permalink = item.get("permalink", "")
                    out.append(
                        Candidate(
                            title=item.get("title", ""),
                            url=f"https://www.reddit.com{permalink}" if permalink else item.get("url", ""),
                            source=f"r/{item.get('subreddit', 'reddit')}",
                            source_kind="reddit",
                            summary=item.get("selftext", "")[:500],
                            published_at=parse_datetime(datetime.fromtimestamp(item.get("created_utc", time.time()), timezone.utc)),
                            collected_at=collected_at,
                            evidence_class="community_index",
                            query=query,
                            engagement=int(item.get("score") or 0) + int(item.get("num_comments") or 0),
                        )
                    )
            except Exception as exc:
                gaps.append(CoverageGap(source="reddit", url=base, reason=str(exc), recovery="Retry later, narrow by subreddit, or review in a visible browser session."))
    status = SourceStatus(name="reddit", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates")
    return out, status, gaps


def collect_feeds(feeds: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    if not feeds:
        return out, SourceStatus(name="custom-feeds", status="skipped", message="no feeds provided"), gaps
    for feed_url in feeds:
        try:
            feed = feedparser.parse(feed_url)
            if getattr(feed, "bozo", False):
                gaps.append(CoverageGap(source="custom-feed", url=feed_url, reason=str(feed.bozo_exception), recovery="Check the feed URL or use direct page URLs."))
            title = getattr(feed.feed, "title", "") or urlparse(feed_url).netloc
            for entry in feed.entries[: args.limit]:
                out.append(
                    Candidate(
                        title=html.unescape(getattr(entry, "title", "")).strip(),
                        url=getattr(entry, "link", ""),
                        source=title,
                        source_kind="rss",
                        summary=BeautifulSoup(getattr(entry, "summary", ""), "html.parser").get_text(" ", strip=True),
                        published_at=parse_datetime(getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None) or getattr(entry, "published", None)),
                        collected_at=collected_at,
                        evidence_class="source_feed",
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="custom-feed", url=feed_url, reason=str(exc), recovery="Check whether the URL is RSS/Atom or provide a direct page URL."))
    return out, SourceStatus(name="custom-feeds", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates"), gaps


def parse_html_candidate(url: str, body: str, source_kind: str, collected_at: str) -> Candidate:
    soup = BeautifulSoup(body, "html.parser")
    title = ""
    if soup.title and soup.title.string:
        title = soup.title.string.strip()
    if not title:
        h1 = soup.find("h1")
        title = h1.get_text(" ", strip=True) if h1 else url
    description = ""
    meta = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
    if meta and meta.get("content"):
        description = meta["content"].strip()
    text = soup.get_text(" ", strip=True)
    published = None
    for selector in (
        {"property": "article:published_time"},
        {"name": "pubdate"},
        {"name": "date"},
        {"itemprop": "datePublished"},
    ):
        tag = soup.find("meta", attrs=selector)
        if tag and tag.get("content"):
            published = parse_datetime(tag.get("content"))
            break
    return Candidate(
        title=title[:300],
        url=url,
        source=urlparse(url).netloc,
        source_kind=source_kind,
        summary=(description or text[:500])[:500],
        published_at=published,
        collected_at=collected_at,
        evidence_class="open_web_http" if source_kind == "url" else "browser_rendered",
    )


def collect_urls(urls: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    if not urls:
        return out, SourceStatus(name="direct-urls", status="skipped", message="no urls provided"), gaps
    s = session()
    for url in urls:
        try:
            res = s.get(url, timeout=args.timeout, allow_redirects=True)
            if res.status_code in (401, 403):
                gaps.append(CoverageGap(source="direct-url", url=url, reason=f"HTTP {res.status_code}", recovery=browser_recovery(url), severity="high"))
                continue
            if res.status_code >= 400:
                gaps.append(CoverageGap(source="direct-url", url=url, reason=f"HTTP {res.status_code}", recovery="Retry later, check URL, or inspect visibly in a browser."))
                continue
            hint = contains_blocked_hint(res.text[:5000])
            if hint:
                gaps.append(CoverageGap(source="direct-url", url=url, reason=f"blocked or weak visible state hint: {hint}", recovery=browser_recovery(url), severity="high"))
                continue
            out.append(parse_html_candidate(res.url, res.text, "url", collected_at))
        except Exception as exc:
            gaps.append(CoverageGap(source="direct-url", url=url, reason=str(exc), recovery=browser_recovery(url), severity="high"))
    return out, SourceStatus(name="direct-urls", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates"), gaps


def browser_recovery(url: str) -> str:
    return (
        "Use the authenticated session guide. Open a user-controlled visible browser session when allowed, "
        "ask the user to complete login/MFA directly, confirm page title, URL, visible account context, and visible text, "
        "capture only non-sensitive screenshot/DOM/text evidence, and record whether login, permission, CAPTCHA, "
        f"paywall, or region access prevents collection. Target URL: {url}"
    )


def needs_auth_guide(gap: CoverageGap) -> bool:
    reason = f"{gap.reason} {gap.recovery}".lower()
    return any(
        marker in reason
        for marker in (
            "401",
            "403",
            "login",
            "sign in",
            "permission",
            "captcha",
            "paywall",
            "access denied",
            "verify you are human",
            "user-controlled visible browser",
            "authenticated session guide",
        )
    )


def write_auth_session_guide(path: Path, urls: list[str], collected_at: str) -> None:
    unique_urls = list(dict.fromkeys(urls))
    lines: list[str] = [
        "# Authenticated Source Session Guide",
        "",
        f"- Generated at: `{collected_at}`",
        "- Purpose: help an AI agent collect user-authorized evidence from login-gated or permission-gated pages without handling private credentials.",
        "",
        "## Hard Boundaries",
        "",
        "- The user enters passwords, passkeys, SSO prompts, and MFA codes directly.",
        "- The agent must not ask the user to reveal passwords, MFA codes, recovery codes, session cookies, API tokens, or private messages.",
        "- The agent must not bypass paywalls, CAPTCHAs, account permissions, rate limits, robots rules, or terms of service.",
        "- The agent captures only the minimum evidence needed for the task and redacts private account details when possible.",
        "- If access is denied after user login, record a coverage gap instead of forcing access.",
        "",
        "## Target URLs",
        "",
    ]
    if unique_urls:
        for url in unique_urls:
            lines.append(f"- {url}")
    else:
        lines.append("- No URL was supplied. Ask the user for the exact page URL before starting.")
    lines.extend(
        [
            "",
            "## Step-by-Step Flow",
            "",
            "1. Restate the task boundary: what page or topic will be inspected, what evidence is needed, and what must not be collected.",
            "2. Confirm authorization: ask the user to confirm they own or are allowed to access the account/page.",
            "3. Open a controlled visible browser session on the exact target domain. Show the user the domain before login.",
            "4. Pause and let the user complete login directly in the browser. The user handles password, SSO, passkey, CAPTCHA, and MFA prompts.",
            "5. Do not read, record, summarize, or screenshot credentials, MFA codes, recovery codes, account settings, private messages, or payment information.",
            "6. After login, ask the user to navigate to the exact page or confirm that the current page is ready for inspection.",
            "7. Confirm visible state: final URL, page title, account/workspace indicator if relevant, visible timestamp, and whether the page looks fully loaded.",
            "8. If the page shows an error, empty state, rate limit, permission warning, challenge, or paywall, retry once only when the user approves, then record a coverage gap.",
            "9. Capture evidence using the least invasive method: visible text, selected links, timestamps, counters, public post IDs, or a redacted screenshot.",
            "10. Redact or avoid private fields: email addresses, usernames not relevant to the task, balances, account IDs, customer data, private comments, and notification contents.",
            "11. Compare visible evidence against the task. Do not infer unseen data from a personalized feed or partial page.",
            "12. Write the result with source URL, collection time, evidence class `authenticated_visible_review`, and any remaining coverage gaps.",
            "13. Ask the user whether to keep the browser session open, log out, or close the window. Do not persist session state unless the user explicitly wants that environment to keep it.",
            "",
            "## Evidence Checklist",
            "",
            "- Final URL",
            "- Page title",
            "- Visible timestamp or publication time",
            "- Visible source/account/page identity",
            "- Relevant text or counters",
            "- Screenshot path only if a screenshot was necessary and safe",
            "- Collection time",
            "- Redactions performed",
            "- Coverage gaps or access limits",
            "",
            "## Stop Conditions",
            "",
            "- The user does not confirm authorization.",
            "- The page asks the agent to handle credentials or MFA directly.",
            "- The content is private and not necessary for the task.",
            "- The page blocks access with CAPTCHA, paywall, permission, or rate-limit controls that the user cannot or does not want to resolve.",
            "- The required evidence cannot be collected without exceeding the task boundary.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_automation_guide(path: Path, collected_at: str) -> None:
    lines = [
        "# Automation Guide",
        "",
        f"- Generated at: `{collected_at}`",
        "- Purpose: run Hot News Radar on a schedule and keep each run's report artifacts.",
        "",
        "## Standard Flow",
        "",
        "1. Define the recurring question: global hot news, topic scan, reputation scan, or custom feed scan.",
        "2. Choose the schedule: hourly for fast-moving incidents, daily for general news, weekly for slower research topics.",
        "3. Choose runtime: local Python, Docker, GitHub Actions, cron, systemd timer, Windows Task Scheduler, or the host agent's automation feature.",
        "4. Run `python scripts/doctor.py --profile full --repair-plan` before enabling the schedule.",
        "5. Use a stable output directory and keep artifacts by timestamp.",
        "6. If Telegram delivery is needed, create a bot, set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, run a dry run, then schedule the sender.",
        "7. If login-gated sources are required, do not run them unattended unless the user has explicitly configured an authorized browser/session workflow.",
        "8. Add Telegram delivery only after one successful manual radar run and one successful Telegram dry run.",
        "9. Monitor source health and coverage gaps; failed lanes should be visible in the output, not hidden.",
        "",
        "## Default Global Hot News",
        "",
        "When no topic or region is provided, this uses blended public top-news regions plus broad news, technology, AI, science, market, and geopolitics queries.",
        "",
        "```bash",
        "python scripts/hot_news_radar.py --out artifacts",
        "```",
        "",
        "## Topic Scan",
        "",
        "```bash",
        "python scripts/hot_news_radar.py --query \"AI agents\" --lookback-hours 24 --limit 30 --out artifacts",
        "```",
        "",
        "## Docker",
        "",
        "```bash",
        "docker run --rm \\",
        "  -v \"$PWD/artifacts:/app/artifacts\" \\",
        "  hot-news-radar:base \\",
        "  --out artifacts",
        "```",
        "",
        "## Cron Example",
        "",
        "```cron",
        "0 * * * * cd /path/to/hot-news-radar && /usr/bin/python3 scripts/hot_news_radar.py --out artifacts >> logs/hot-news-radar.log 2>&1",
        "```",
        "",
        "## Windows Task Scheduler Example",
        "",
        "Program: `python`",
        "",
        "Arguments: `scripts/hot_news_radar.py --out artifacts`",
        "",
        "Start in: the repository root.",
        "",
        "## GitHub Actions Example",
        "",
        "```yaml",
        "on:",
        "  schedule:",
        "    - cron: \"0 * * * *\"",
        "  workflow_dispatch:",
        "jobs:",
        "  radar:",
        "    runs-on: ubuntu-latest",
        "    steps:",
        "      - uses: actions/checkout@v4",
        "      - uses: actions/setup-python@v5",
        "        with:",
        "          python-version: \"3.12\"",
        "      - run: python -m pip install -r requirements.txt",
        "      - run: python scripts/hot_news_radar.py --out artifacts",
        "      - uses: actions/upload-artifact@v4",
        "        with:",
        "          name: hot-news-radar",
        "          path: artifacts",
        "```",
        "",
        "## Telegram Delivery",
        "",
        "Use `telegram-delivery-guide.md` and `scripts/telegram_notify.py` after a manual run succeeds.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_telegram_guide(path: Path, collected_at: str) -> None:
    lines = [
        "# Telegram Delivery Guide",
        "",
        f"- Generated at: `{collected_at}`",
        "- Purpose: send Hot News Radar reports to a Telegram chat after manual or automated runs.",
        "",
        "## Setup",
        "",
        "1. In Telegram, open `@BotFather`.",
        "2. Run `/newbot` and follow the prompts.",
        "3. Copy the bot token. Treat it as a secret.",
        "4. Open a chat with the bot and send a test message, or add the bot to a group/channel where it should post.",
        "5. Get the chat ID using one of these methods:",
        "   - Visit `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` after sending a message to the bot.",
        "   - For a group/channel, add the bot and inspect `chat.id` from `getUpdates`.",
        "   - Use a trusted chat-id helper only if you understand the privacy tradeoff.",
        "6. Store credentials as environment variables. Do not hard-code them in scripts, repos, logs, or screenshots.",
        "",
        "## Environment Variables",
        "",
        "```bash",
        "export TELEGRAM_BOT_TOKEN=\"...\"",
        "export TELEGRAM_CHAT_ID=\"...\"",
        "```",
        "",
        "PowerShell:",
        "",
        "```powershell",
        "$env:TELEGRAM_BOT_TOKEN = \"...\"",
        "$env:TELEGRAM_CHAT_ID = \"...\"",
        "```",
        "",
        "## Dry Run",
        "",
        "```bash",
        "python scripts/telegram_notify.py --file artifacts/<run>/radar-report.md --dry-run",
        "```",
        "",
        "## Send A Report",
        "",
        "```bash",
        "python scripts/telegram_notify.py --file artifacts/<run>/radar-report.md --title \"Hot News Radar\"",
        "```",
        "",
        "## Run Radar Then Send Latest Report",
        "",
        "```bash",
        "RUN_DIR=$(python scripts/hot_news_radar.py --out artifacts | tail -n 1)",
        "python scripts/telegram_notify.py --file \"$RUN_DIR/radar-report.md\" --title \"Hot News Radar\"",
        "```",
        "",
        "## Safety",
        "",
        "- Do not print bot tokens or chat IDs into shared logs.",
        "- Do not send private account data, credentials, cookies, tokens, or unrelated personal information.",
        "- For high-volume schedules, rate-limit messages and send summaries instead of every raw candidate.",
        "- If delivery fails, keep the local artifact and report the failure visibly.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def collect_playwright(urls: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    if args.browser_fallback != "playwright" or not urls:
        return out, SourceStatus(name="playwright-browser", status="skipped", message="not requested"), gaps
    try:
        from playwright.sync_api import sync_playwright
    except Exception as exc:
        return out, SourceStatus(name="playwright-browser", status="failed", message=str(exc)), [
            CoverageGap(source="playwright-browser", reason="Playwright is not installed.", recovery="Install requirements-browser.txt and run: python -m playwright install chromium")
        ]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        for url in urls:
            try:
                page.goto(url, wait_until="networkidle", timeout=args.timeout * 1000)
                text = page.locator("body").inner_text(timeout=args.timeout * 1000)
                title = page.title()
                hint = contains_blocked_hint(text[:5000])
                if hint:
                    gaps.append(CoverageGap(source="playwright-browser", url=url, reason=f"blocked or weak visible state hint: {hint}", recovery=browser_recovery(url), severity="high"))
                    continue
                html_body = f"<html><head><title>{html.escape(title)}</title></head><body>{html.escape(text[:5000])}</body></html>"
                out.append(parse_html_candidate(url, html_body, "browser", collected_at))
            except Exception as exc:
                gaps.append(CoverageGap(source="playwright-browser", url=url, reason=str(exc), recovery=browser_recovery(url), severity="high"))
        browser.close()
    return out, SourceStatus(name="playwright-browser", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates"), gaps


def collect_firecrawl(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    api_key = os.getenv(args.firecrawl_key_env)
    if not api_key:
        return out, SourceStatus(name="firecrawl", status="skipped", message=f"{args.firecrawl_key_env} not set"), gaps
    s = session()
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": USER_AGENT}
    for query in queries:
        try:
            res = s.post(
                "https://api.firecrawl.dev/v1/search",
                headers=headers,
                json={"query": query, "limit": min(args.limit, 10)},
                timeout=args.timeout,
            )
            if res.status_code >= 400:
                gaps.append(CoverageGap(source="firecrawl", reason=f"HTTP {res.status_code}: {res.text[:200]}", recovery="Check API key, quota, endpoint, and provider documentation."))
                continue
            data = res.json()
            items = data.get("data") or data.get("results") or []
            for item in items[: args.limit]:
                out.append(
                    Candidate(
                        title=item.get("title") or item.get("name") or item.get("url", ""),
                        url=item.get("url", ""),
                        source=urlparse(item.get("url", "")).netloc or "Firecrawl",
                        source_kind="firecrawl",
                        summary=item.get("description") or item.get("markdown", "")[:500],
                        published_at=parse_datetime(item.get("publishedDate") or item.get("date")),
                        collected_at=collected_at,
                        evidence_class="provider_search",
                        query=query,
                    )
                )
        except Exception as exc:
            gaps.append(CoverageGap(source="firecrawl", reason=str(exc), recovery="Check provider availability and retry with a narrower query."))
    return out, SourceStatus(name="firecrawl", status="ok" if out else "partial", collected=len(out), message=f"{len(out)} candidates"), gaps


def freshness_points(age: float | None) -> float:
    if age is None:
        return 8
    if age <= 1:
        return 35
    if age <= 6:
        return 30
    if age <= 24:
        return 24
    if age <= 72:
        return 16
    if age <= 168:
        return 9
    return 4


def relevance_points(candidate: Candidate, terms: list[str]) -> float:
    if not terms:
        return 15
    haystack = f"{candidate.title} {candidate.summary} {candidate.source}".lower()
    hits = sum(1 for term in terms if term in haystack)
    return min(25.0, 8.0 + (hits / max(1, len(terms))) * 17.0)


def authority_points(source_kind: str) -> float:
    table = {
        "google-news-top": 13,
        "google-news": 12,
        "gdelt": 12,
        "rss": 12,
        "url": 13,
        "browser": 11,
        "firecrawl": 12,
        "hacker-news": 8,
        "reddit": 6,
    }
    return table.get(source_kind, 7)


def engagement_points(engagement: int) -> float:
    if engagement <= 0:
        return 0
    return min(10.0, math.log10(engagement + 1) * 4.0)


def label(score: float) -> str:
    if score >= 75:
        return "hot"
    if score >= 58:
        return "rising"
    if score >= 42:
        return "watch"
    return "weak"


def dedupe_and_score(candidates: list[Candidate], queries: list[str], now: datetime) -> list[Candidate]:
    groups: dict[str, Candidate] = {}
    for candidate in candidates:
        if not candidate.title and not candidate.url:
            continue
        key = text_fingerprint(candidate.title, candidate.url)
        candidate.age_hours = age_hours(candidate.published_at, now)
        if not candidate.published_at:
            candidate.warnings.append("No source publication time found; collection time is not event freshness.")
        if key not in groups:
            candidate.merged_sources = [candidate.source]
            candidate.related_urls = [candidate.url] if candidate.url else []
            groups[key] = candidate
            continue
        existing = groups[key]
        existing.source_count += 1
        if candidate.source and candidate.source not in existing.merged_sources:
            existing.merged_sources.append(candidate.source)
        if candidate.url and candidate.url not in existing.related_urls:
            existing.related_urls.append(candidate.url)
        existing.engagement = max(existing.engagement, candidate.engagement)
        if candidate.age_hours is not None and (existing.age_hours is None or candidate.age_hours < existing.age_hours):
            existing.age_hours = candidate.age_hours
            existing.published_at = candidate.published_at
        if len(candidate.summary) > len(existing.summary):
            existing.summary = candidate.summary
    for candidate in groups.values():
        terms = query_terms([candidate.query]) if candidate.query else query_terms(queries)
        consensus = min(15.0, max(0, candidate.source_count - 1) * 5.0)
        score = (
            freshness_points(candidate.age_hours)
            + relevance_points(candidate, terms)
            + authority_points(candidate.source_kind)
            + consensus
            + engagement_points(candidate.engagement)
        )
        candidate.heat_score = round(min(100.0, score), 1)
        candidate.trend_label = label(candidate.heat_score)
    return sorted(groups.values(), key=lambda c: (c.heat_score, c.published_at or ""), reverse=True)


def filter_by_lookback(candidates: list[Candidate], lookback_hours: int) -> list[Candidate]:
    kept: list[Candidate] = []
    for candidate in candidates:
        if candidate.age_hours is None or candidate.age_hours <= lookback_hours:
            kept.append(candidate)
    return kept


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(path: Path, candidates: list[Candidate]) -> None:
    fields = ["heat_score", "trend_label", "title", "url", "source", "source_kind", "published_at", "age_hours", "source_count", "evidence_class", "summary"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for candidate in candidates:
            row = asdict(candidate)
            writer.writerow({field: row.get(field) for field in fields})


def write_report(path: Path, args: argparse.Namespace, candidates: list[Candidate], statuses: list[SourceStatus], gaps: list[CoverageGap], auth_guide: AuthGuide, run_guides: RunGuides, collected_at: str) -> None:
    lines: list[str] = []
    queries = ", ".join(args.query or [])
    lines.append("# Hot News Radar Report")
    lines.append("")
    lines.append(f"- Collected at: `{collected_at}`")
    lines.append(f"- Query: `{queries or 'URL/feed only'}`")
    lines.append(f"- Mode: `{args.mode}`")
    if run_guides.default_profile:
        lines.append(f"- Default profile: `{run_guides.default_profile}`")
    lines.append(f"- Lookback: `{args.lookback_hours} hours`")
    lines.append(f"- Candidate count: `{len(candidates)}`")
    lines.append("")
    lines.append("## Top Signals")
    lines.append("")
    if not candidates:
        lines.append("No candidates passed normalization. Check coverage gaps and broaden the source plan.")
    else:
        lines.append("| Score | Label | Title | Source | Time | Evidence |")
        lines.append("| ---: | --- | --- | --- | --- | --- |")
        for item in candidates[: args.limit]:
            title = item.title.replace("|", "\\|")
            link = f"[{title}]({item.url})" if item.url else title
            time_value = item.published_at or "unknown"
            lines.append(f"| {item.heat_score:.1f} | {item.trend_label} | {link} | {item.source} | {time_value} | {item.evidence_class} |")
    lines.append("")
    lines.append("## Source Health")
    lines.append("")
    lines.append("| Source | Status | Count | Message |")
    lines.append("| --- | --- | ---: | --- |")
    for status in statuses:
        lines.append(f"| {status.name} | {status.status} | {status.collected} | {status.message.replace('|', '/')} |")
    lines.append("")
    lines.append("## Coverage Gaps")
    lines.append("")
    if not gaps:
        lines.append("No coverage gaps recorded.")
    else:
        lines.append("| Severity | Source | URL | Reason | Recovery |")
        lines.append("| --- | --- | --- | --- | --- |")
        for gap in gaps:
            url = f"[link]({gap.url})" if gap.url else ""
            lines.append(f"| {gap.severity} | {gap.source} | {url} | {gap.reason.replace('|', '/')} | {gap.recovery.replace('|', '/')} |")
    lines.append("")
    if auth_guide.required:
        lines.append("## Authenticated Review")
        lines.append("")
        lines.append(f"- Guide: `{auth_guide.path or 'authenticated-session-guide.md'}`")
        lines.append("- Use this only for user-authorized pages. The user completes login, SSO, passkey, CAPTCHA, and MFA prompts directly.")
        lines.append("- Do not collect credentials, MFA codes, cookies, tokens, private messages, payment details, or unrelated account data.")
        lines.append("")
    if run_guides.automation_guide_path or run_guides.telegram_guide_path:
        lines.append("## Automation And Delivery")
        lines.append("")
        if run_guides.automation_guide_path:
            lines.append(f"- Automation guide: `{run_guides.automation_guide_path}`")
        if run_guides.telegram_guide_path:
            lines.append(f"- Telegram guide: `{run_guides.telegram_guide_path}`")
        lines.append("- Keep secrets in environment variables or the host secret store; do not commit bot tokens or chat IDs.")
        lines.append("")
    lines.append("## Detailed Candidates")
    lines.append("")
    for index, item in enumerate(candidates[: args.limit], 1):
        lines.append(f"### {index}. {item.title}")
        lines.append("")
        lines.append(f"- Score: `{item.heat_score:.1f}` / label `{item.trend_label}`")
        lines.append(f"- URL: {item.url or 'n/a'}")
        lines.append(f"- Source: `{item.source}` / kind `{item.source_kind}`")
        lines.append(f"- Published: `{item.published_at or 'unknown'}` / age hours `{item.age_hours if item.age_hours is not None else 'unknown'}`")
        lines.append(f"- Evidence class: `{item.evidence_class}`")
        lines.append(f"- Source count: `{item.source_count}`")
        if item.summary:
            lines.append(f"- Summary: {item.summary[:500]}")
        if item.warnings:
            lines.append(f"- Warnings: {'; '.join(item.warnings)}")
        lines.append("")
    lines.append("## Interpretation Notes")
    lines.append("")
    lines.append("- A heat score ranks attention priority; it is not truth verification.")
    lines.append("- Collection time is not the same as event time or publication time.")
    lines.append("- Blocked, login-gated, challenge, or error pages require visible/manual review before making claims.")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def selected_sources(args: argparse.Namespace) -> list[str]:
    if args.source:
        return args.source
    if args.mode == "global-hot":
        return ["google-news-top", "google-news", "gdelt", "hacker-news"]
    if args.mode == "news":
        return ["google-news", "gdelt"]
    if args.mode == "social":
        return ["reddit", "hacker-news"]
    if args.mode == "research":
        return ["google-news", "gdelt", "hacker-news"]
    if args.mode == "reputation":
        return ["google-news", "gdelt", "reddit"]
    return ["google-news", "gdelt", "hacker-news", "reddit"]


def apply_default_profile(args: argparse.Namespace) -> RunGuides:
    guides = RunGuides()
    if not args.query and not args.feed and not args.url:
        args.mode = "global-hot"
        args.query = list(DEFAULT_GLOBAL_HOT_QUERIES)
        guides.default_profile = "global-hot"
    return guides


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find, rank, and summarize fresh public signals.")
    parser.add_argument("--query", action="append", default=[], help="Topic or search query. Repeatable.")
    parser.add_argument("--mode", choices=["general", "global-hot", "news", "social", "research", "reputation"], default="general")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--freshness-hours", type=int, default=None, help="Alias for lookback-hours when callers prefer freshness wording.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--source", action="append", choices=["google-news-top", "google-news", "gdelt", "hacker-news", "reddit", "rss", "url", "firecrawl"], help="Source lane. Repeatable. Defaults by mode.")
    parser.add_argument("--feed", action="append", default=[], help="RSS or Atom feed URL. Repeatable.")
    parser.add_argument("--url", action="append", default=[], help="Direct page URL. Repeatable.")
    parser.add_argument("--subreddit", action="append", default=[], help="Restrict Reddit search to subreddit. Repeatable.")
    parser.add_argument("--language", default="en-US", help="Google News language, for example en-US.")
    parser.add_argument("--region", default="", help="Google News region, for example US. Default: blended global regions for global-hot, US otherwise.")
    parser.add_argument("--browser-fallback", choices=["off", "plan", "playwright"], default="plan")
    parser.add_argument("--auth-session-guide", action="store_true", help="Write a step-by-step guide for user-controlled login-gated source review.")
    parser.add_argument("--automation-guide", action="store_true", help="Write a scheduling guide for recurring radar runs.")
    parser.add_argument("--telegram-guide", action="store_true", help="Write a Telegram delivery setup guide for recurring reports.")
    parser.add_argument("--firecrawl-key-env", default="FIRECRAWL_API_KEY")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", default="artifacts")
    parser.add_argument("--min-score", type=float, default=0.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.freshness_hours is not None:
        args.lookback_hours = args.freshness_hours
    run_guides = apply_default_profile(args)
    collected_at = iso_now()
    now = utc_now()
    sources = selected_sources(args)
    all_candidates: list[Candidate] = []
    statuses: list[SourceStatus] = []
    gaps: list[CoverageGap] = []

    if "google-news-top" in sources:
        candidates, status, source_gaps = collect_google_news_top(args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "google-news" in sources and args.query:
        candidates, status, source_gaps = collect_google_news(args.query, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "gdelt" in sources and args.query:
        candidates, status, source_gaps = collect_gdelt(args.query, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "hacker-news" in sources and args.query:
        candidates, status, source_gaps = collect_hacker_news(args.query, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "reddit" in sources and args.query:
        candidates, status, source_gaps = collect_reddit(args.query, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "rss" in sources or args.feed:
        candidates, status, source_gaps = collect_feeds(args.feed, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "url" in sources or args.url:
        candidates, status, source_gaps = collect_urls(args.url, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if "firecrawl" in sources and args.query:
        candidates, status, source_gaps = collect_firecrawl(args.query, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)
    if args.browser_fallback == "plan":
        if args.url:
            planned = 0
            for url in args.url:
                if not any(equivalent_url(candidate.url, url) for candidate in all_candidates):
                    planned += 1
                    gaps.append(CoverageGap(source="browser-fallback-plan", url=url, reason="Direct HTTP evidence was unavailable or not requested.", recovery=browser_recovery(url), severity="medium"))
            statuses.append(SourceStatus(name="browser-fallback", status="planned" if planned else "skipped", message="visible browser recovery plan generated when needed" if planned else "direct URL evidence already available"))
        else:
            statuses.append(SourceStatus(name="browser-fallback", status="skipped", message="no direct URLs provided"))
    if args.browser_fallback == "playwright":
        candidates, status, source_gaps = collect_playwright(args.url, args, collected_at)
        all_candidates.extend(candidates)
        statuses.append(status)
        gaps.extend(source_gaps)

    ranked = dedupe_and_score(all_candidates, args.query, now)
    ranked = filter_by_lookback(ranked, args.lookback_hours)
    ranked = [candidate for candidate in ranked if candidate.heat_score >= args.min_score]
    ranked = ranked[: args.limit]

    run_dir = Path(args.out) / f"hot-news-radar-{safe_filename(collected_at)}"
    run_dir.mkdir(parents=True, exist_ok=True)
    auth_urls = [gap.url for gap in gaps if gap.url and needs_auth_guide(gap)]
    if args.auth_session_guide and args.url:
        auth_urls.extend(args.url)
    auth_guide = AuthGuide(required=bool(auth_urls or args.auth_session_guide), urls=list(dict.fromkeys(auth_urls)))
    if auth_guide.required:
        guide_path = run_dir / "authenticated-session-guide.md"
        write_auth_session_guide(guide_path, auth_guide.urls, collected_at)
        auth_guide.path = guide_path.as_posix()
    if args.automation_guide:
        guide_path = run_dir / "automation-guide.md"
        write_automation_guide(guide_path, collected_at)
        run_guides.automation_guide_path = guide_path.as_posix()
    if args.telegram_guide:
        guide_path = run_dir / "telegram-delivery-guide.md"
        write_telegram_guide(guide_path, collected_at)
        run_guides.telegram_guide_path = guide_path.as_posix()
    write_json(run_dir / "candidates.json", [asdict(candidate) for candidate in ranked])
    write_json(run_dir / "sources.json", [asdict(status) for status in statuses])
    write_json(run_dir / "coverage-gaps.json", [asdict(gap) for gap in gaps])
    write_json(
        run_dir / "brief.json",
        {
            "collected_at": collected_at,
            "query": args.query,
            "mode": args.mode,
            "lookback_hours": args.lookback_hours,
            "default_profile": run_guides.default_profile,
            "candidate_count": len(ranked),
            "top": [asdict(candidate) for candidate in ranked[:5]],
            "coverage_gap_count": len(gaps),
            "authenticated_session_guide": asdict(auth_guide),
            "automation_guide": run_guides.automation_guide_path,
            "telegram_guide": run_guides.telegram_guide_path,
        },
    )
    write_csv(run_dir / "candidates.csv", ranked)
    write_report(run_dir / "radar-report.md", args, ranked, statuses, gaps, auth_guide, run_guides, collected_at)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
