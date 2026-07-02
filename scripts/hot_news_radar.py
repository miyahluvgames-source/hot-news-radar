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
import sys
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


def collect_google_news(queries: list[str], args: argparse.Namespace, collected_at: str) -> tuple[list[Candidate], SourceStatus, list[CoverageGap]]:
    out: list[Candidate] = []
    gaps: list[CoverageGap] = []
    hl = args.language or "en-US"
    gl = args.region or "US"
    ceid = f"{gl}:en"
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
        "Use a user-controlled visible browser session when allowed, confirm the page title and visible text, "
        "capture a screenshot or DOM text, and record whether login, permission, CAPTCHA, or paywall prevents access. "
        f"Target URL: {url}"
    )


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
    terms = query_terms(queries)
    for candidate in groups.values():
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


def write_report(path: Path, args: argparse.Namespace, candidates: list[Candidate], statuses: list[SourceStatus], gaps: list[CoverageGap], collected_at: str) -> None:
    lines: list[str] = []
    queries = ", ".join(args.query or [])
    lines.append("# Hot News Radar Report")
    lines.append("")
    lines.append(f"- Collected at: `{collected_at}`")
    lines.append(f"- Query: `{queries or 'URL/feed only'}`")
    lines.append(f"- Mode: `{args.mode}`")
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
    if args.mode == "news":
        return ["google-news", "gdelt"]
    if args.mode == "social":
        return ["reddit", "hacker-news"]
    if args.mode == "research":
        return ["google-news", "gdelt", "hacker-news"]
    if args.mode == "reputation":
        return ["google-news", "gdelt", "reddit"]
    return ["google-news", "gdelt", "hacker-news", "reddit"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Find, rank, and summarize fresh public signals.")
    parser.add_argument("--query", action="append", default=[], help="Topic or search query. Repeatable.")
    parser.add_argument("--mode", choices=["general", "news", "social", "research", "reputation"], default="general")
    parser.add_argument("--lookback-hours", type=int, default=24)
    parser.add_argument("--freshness-hours", type=int, default=None, help="Alias for lookback-hours when callers prefer freshness wording.")
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--source", action="append", choices=["google-news", "gdelt", "hacker-news", "reddit", "rss", "url", "firecrawl"], help="Source lane. Repeatable. Defaults by mode.")
    parser.add_argument("--feed", action="append", default=[], help="RSS or Atom feed URL. Repeatable.")
    parser.add_argument("--url", action="append", default=[], help="Direct page URL. Repeatable.")
    parser.add_argument("--subreddit", action="append", default=[], help="Restrict Reddit search to subreddit. Repeatable.")
    parser.add_argument("--language", default="en-US", help="Google News language, for example en-US.")
    parser.add_argument("--region", default="US", help="Google News region, for example US.")
    parser.add_argument("--browser-fallback", choices=["off", "plan", "playwright"], default="plan")
    parser.add_argument("--firecrawl-key-env", default="FIRECRAWL_API_KEY")
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--out", default="artifacts")
    parser.add_argument("--min-score", type=float, default=0.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.freshness_hours is not None:
        args.lookback_hours = args.freshness_hours
    if not args.query and not args.feed and not args.url:
        print("Provide at least one --query, --feed, or --url.", file=sys.stderr)
        return 2
    collected_at = iso_now()
    now = utc_now()
    sources = selected_sources(args)
    all_candidates: list[Candidate] = []
    statuses: list[SourceStatus] = []
    gaps: list[CoverageGap] = []

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
            "candidate_count": len(ranked),
            "top": [asdict(candidate) for candidate in ranked[:5]],
            "coverage_gap_count": len(gaps),
        },
    )
    write_csv(run_dir / "candidates.csv", ranked)
    write_report(run_dir / "radar-report.md", args, ranked, statuses, gaps, collected_at)
    print(str(run_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
