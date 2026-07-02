from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from scripts.hot_news_radar import Candidate, CoverageGap, dedupe_and_score, parse_html_candidate
from scripts.hot_news_radar import parse_datetime
from scripts.hot_news_radar import DEFAULT_GLOBAL_HOT_QUERIES, apply_default_profile, build_parser, google_news_regions
from scripts.hot_news_radar import main, needs_auth_guide, selected_sources, write_auth_session_guide
from scripts.telegram_notify import chunks, load_message


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


def test_empty_input_uses_default_global_hot_profile() -> None:
    args = build_parser().parse_args([])
    guides = apply_default_profile(args)
    assert args.mode == "global-hot"
    assert args.query == DEFAULT_GLOBAL_HOT_QUERIES
    assert guides.default_profile == "global-hot"
    assert "google-news-top" in selected_sources(args)
    assert len(google_news_regions(args)) > 1


def test_region_keeps_global_hot_profile_narrowed_to_user_region() -> None:
    args = build_parser().parse_args(["--region", "GB"])
    guides = apply_default_profile(args)
    assert args.mode == "global-hot"
    assert guides.default_profile == "global-hot"
    assert google_news_regions(args) == ["GB"]


def test_cli_writes_automation_and_telegram_guides(tmp_path) -> None:
    exit_code = main(
        [
            "--query",
            "AI agents",
            "--source",
            "rss",
            "--feed",
            "tests/fixtures/sample_feed.xml",
            "--automation-guide",
            "--telegram-guide",
            "--out",
            str(tmp_path),
        ]
    )
    assert exit_code == 0
    assert len(list(tmp_path.glob("*/automation-guide.md"))) == 1
    assert len(list(tmp_path.glob("*/telegram-delivery-guide.md"))) == 1
    brief = list(tmp_path.glob("*/brief.json"))[0].read_text(encoding="utf-8")
    assert "automation_guide" in brief
    assert "telegram_guide" in brief


def test_telegram_message_chunks_and_title(tmp_path) -> None:
    report = tmp_path / "radar-report.md"
    report.write_text("a" * 8000, encoding="utf-8")
    message = load_message(report, "Hot News Radar")
    parts = list(chunks(message, max_chars=3900))
    assert message.startswith("Hot News Radar")
    assert len(parts) == 3
    assert all(len(part) <= 3900 for part in parts)
