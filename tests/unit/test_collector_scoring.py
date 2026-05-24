from __future__ import annotations

from typing import Any, cast

import pytest

from app.contracts.errors import AppError
from app.github_collector.service import (
    GitHubApiMetadataClient,
    StaticTrendingPageFetcher,
    TrendingParser,
)
from app.main import Services
from app.scoring import ScoringService
from tests.helpers import candidate

HTML = """
<article class="Box-row">
  <h2><a href="/owner/repo"> owner / repo </a></h2>
  <p>AI coding tool.</p>
  <span itemprop="programmingLanguage">Python</span>
  <span>1,234 stars today</span>
</article>
"""


def test_trending_parser_extracts_required_fields() -> None:
    parsed = TrendingParser().parse(HTML, 10)[0]
    assert parsed.repoFullName == "owner/repo"
    assert parsed.repoUrl == "https://github.com/owner/repo"
    assert parsed.description == "AI coding tool."
    assert parsed.language == "Python"
    assert parsed.todayStars == 1234


def test_collector_contract_and_fallback(services: Services) -> None:
    result = services.collector.collect(limit=2)
    assert result["jobId"]
    assert len(result["candidates"]) == 2

    class BrokenFetcher:
        def fetch(self, language: str, since: str) -> str:
            raise AppError("GITHUB_TRENDING_FETCH_FAILED", "failed", True, {})

    services.collector.fetcher = BrokenFetcher()
    fallback = services.collector.collect(limit=1)
    assert fallback["candidates"][0]["repoFullName"] == "fallback/repo-1"


def test_collector_uses_parsed_candidate_when_metadata_enrichment_fails(
    services: Services,
) -> None:
    class BrokenMetadataClient:
        def enrich(self, parsed: object) -> object:
            raise AppError("GITHUB_API_FAILED", "failed", True, {})

        def fallback_search(self, limit: int) -> list[object]:
            raise AppError("GITHUB_API_FAILED", "failed", True, {})

    services.collector.fetcher = StaticTrendingPageFetcher(HTML)
    services.collector.metadata_client = BrokenMetadataClient()
    result = services.collector.collect(limit=1)
    first = cast(dict[str, Any], result["candidates"][0])
    assert first["repoFullName"] == "owner/repo"
    assert first["description"] == "AI coding tool."
    assert first["todayStars"] == 1234


def test_single_repo_falls_back_on_retryable_metadata_error(
    services: Services, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail_enrich(self: GitHubApiMetadataClient, parsed: object) -> object:
        raise AppError("GITHUB_API_FAILED", "failed", True, {})

    monkeypatch.setattr(GitHubApiMetadataClient, "enrich", fail_enrich)

    result = services.collector.fetch_single_repo("owner/repo")

    assert result.repoFullName == "owner/repo"
    assert result.repoUrl == "https://github.com/owner/repo"
    assert result.valid is True


def test_collector_rejects_non_daily(services: Services) -> None:
    with pytest.raises(AppError):
        services.collector.collect(since="weekly")


def test_scoring_filters_dedups_flags_and_explains(services: Services) -> None:
    candidates = [
        candidate("owner/a", stars=12000, today=320),
        candidate("owner/b", stars=8000, today=240),
        candidate("owner/c", stars=7000, today=180),
        candidate("owner/d", stars=6000, today=160),
        candidate("owner/e", stars=5000, today=150),
        candidate("owner/dup", stars=9000, today=260),
        candidate("owner/bad"),
    ]
    candidates[-1].description = ""
    candidates[0].createdAt = "2026-05-21T00:00:00Z"
    services.repository.add_dedup_record("owner/dup", "generated")
    result = ScoringService(services.repository).score_candidates("collect_1", candidates, 5)
    recommended = cast(list[dict[str, Any]], result["recommended"])
    assert 3 <= len(recommended) <= 5
    assert all(item["recommendReason"] for item in recommended)
    assert all(item["repoFullName"] != "owner/dup" for item in recommended)
    assert any("star_spike" in item["riskFlags"] for item in recommended)


def test_scoring_degraded_when_insufficient(services: Services) -> None:
    result = services.scoring.score_candidates("collect_1", [candidate("owner/only")], 5)
    assert result["degraded"] is True
