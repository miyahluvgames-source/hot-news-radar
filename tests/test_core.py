from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts.hot_news_radar import Candidate, CoverageGap, dedupe_and_score, parse_html_candidate
from scripts.hot_news_radar import parse_datetime
from scripts.hot_news_radar import main, needs_auth_guide, write_auth_session_guide


def test_dedupe_and_score_merges_sources() -> None:
    now = datetime(2026, 7, 2, 0, 0, tzinfo=timezone.utc)
    candidates = [
        Candidate(
            title="AI agents gain new browser automation tools",
            url="https://example.com/story",
            source="Example",
            source_kind="rss",
            published_at="2026-07-01T23:00:00+00:00",
            collected_at="2026-07-02T00:00:00+00:00",
            query="AI agents",
        ),
        Candidate(
            title="AI agents gain new browser automation tools",
            url="https://example.com/story",
            source="Mirror",
            source_kind="google-news",
            published_at="2026-07-01T23:05:00+00:00",
            collected_at="2026-07-02T00:00:00+00:00",
            query="AI agents",
            engagement=50,
        ),
    ]
    ranked = dedupe_and_score(candidates, ["AI agents"], now)
    assert len(ranked) == 1
    assert ranked[0].source_count == 2
    assert "Mirror" in ranked[0].merged_sources
    assert ranked[0].heat_score > 70


def test_parse_html_candidate_extracts_title_description_and_time() -> None:
    body = Path("tests/fixtures/sample_page.html").read_text(encoding="utf-8")
    candidate = parse_html_candidate("https://example.com/tool", body, "url", "2026-07-02T00:00:00+00:00")
    assert candidate.title == "Launch page for a public AI tool"
    assert "public AI tool launch" in candidate.summary
    assert candidate.published_at == "2026-07-01T11:00:00+00:00"


def test_parse_datetime_struct_time_uses_utc() -> None:
    import feedparser

    parsed = feedparser.parse("tests/fixtures/sample_feed.xml")
    assert parse_datetime(parsed.entries[0].published_parsed) == "2026-07-01T12:00:00+00:00"


def test_auth_session_guide_contains_safety_boundaries(tmp_path) -> None:
    guide = tmp_path / "authenticated-session-guide.md"
    write_auth_session_guide(guide, ["https://example.com/private"], "2026-07-02T00:00:00+00:00")
    text = guide.read_text(encoding="utf-8")
    assert "The user enters passwords" in text
    assert "MFA codes" in text
    assert "cookies" in text
    assert "coverage gap" in text
    assert "https://example.com/private" in text


def test_cli_writes_auth_session_guide(tmp_path) -> None:
    exit_code = main(
        [
            "--query",
            "AI agents",
            "--source",
            "rss",
            "--feed",
            "tests/fixtures/sample_feed.xml",
            "--auth-session-guide",
            "--out",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    guides = list(tmp_path.glob("*/authenticated-session-guide.md"))
    assert len(guides) == 1
    brief = list(tmp_path.glob("*/brief.json"))[0].read_text(encoding="utf-8")
    assert "authenticated_session_guide" in brief
    assert "\\" not in brief


def test_auth_gap_detection_catches_login_or_permission() -> None:
    assert needs_auth_guide(CoverageGap(source="url", url="https://example.com", reason="HTTP 403"))
    assert needs_auth_guide(CoverageGap(source="url", url="https://example.com", reason="sign in to continue"))
