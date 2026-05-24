from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, cast
from uuid import uuid4

from bs4 import BeautifulSoup

from app.contracts.errors import AppError
from app.contracts.schemas import Candidate
from app.storage.repository import SQLiteRepository


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class ParsedTrendingRepo:
    repoFullName: str
    repoUrl: str
    description: str
    language: str
    todayStars: int


class TrendingParser:
    def parse(self, html: str, limit: int) -> list[ParsedTrendingRepo]:
        soup = BeautifulSoup(html, "html.parser")
        articles = soup.select("article.Box-row")
        if not articles:
            raise AppError(
                "GITHUB_TRENDING_PARSE_FAILED", "No trending repositories found", True, {}
            )
        repos: list[ParsedTrendingRepo] = []
        for article in articles[:limit]:
            link = article.select_one("h2 a")
            if link is None or not link.get("href"):
                continue
            href = str(link["href"]).strip()
            full_name = href.strip("/").replace(" ", "")
            description_node = article.select_one("p")
            language_node = article.select_one("[itemprop='programmingLanguage']")
            text = article.get_text(" ", strip=True)
            match = re.search(r"([\d,]+)\s+stars?\s+today", text, flags=re.IGNORECASE)
            today_stars = int(match.group(1).replace(",", "")) if match else 0
            repos.append(
                ParsedTrendingRepo(
                    repoFullName=full_name,
                    repoUrl=f"https://github.com/{full_name}",
                    description=description_node.get_text(" ", strip=True)
                    if description_node
                    else "",
                    language=language_node.get_text(" ", strip=True) if language_node else "",
                    todayStars=today_stars,
                )
            )
        if not repos:
            raise AppError(
                "GITHUB_TRENDING_PARSE_FAILED", "Trending parser produced no repos", True, {}
            )
        return repos


class TrendingPageFetcher(Protocol):
    def fetch(self, language: str, since: str) -> str: ...


class StaticTrendingPageFetcher:
    def __init__(self, html: str) -> None:
        self.html = html

    def fetch(self, language: str, since: str) -> str:
        if since != "daily":
            raise AppError(
                "INVALID_TRENDING_SINCE",
                "MVP only supports daily trending",
                False,
                {"since": since},
            )
        return self.html


class GitHubTrendingPageFetcher:
    def fetch(self, language: str, since: str) -> str:
        if since != "daily":
            raise AppError(
                "INVALID_TRENDING_SINCE",
                "MVP only supports daily trending",
                False,
                {"since": since},
            )
        path = "" if language == "all" else f"/{language}"
        url = f"https://github.com/trending{path}?since={since}"
        request = urllib.request.Request(url, headers={"User-Agent": "github-daily-video-mvp"})
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                html = response.read().decode("utf-8", errors="replace")
                return str(html)
        except (urllib.error.URLError, TimeoutError) as exc:
            raise AppError(
                "GITHUB_TRENDING_FETCH_FAILED",
                "GitHub Trending fetch failed",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc


class GitHubMetadataClient(Protocol):
    def enrich(self, parsed: ParsedTrendingRepo) -> Candidate: ...

    def fallback_search(self, limit: int) -> list[Candidate]: ...


class MockGitHubMetadataClient:
    def __init__(self, overrides: dict[str, dict[str, object]] | None = None) -> None:
        self.overrides = overrides or {}

    def enrich(self, parsed: ParsedTrendingRepo) -> Candidate:
        extra = self.overrides.get(parsed.repoFullName, {})
        readme = str(
            extra.get(
                "readmeText", f"{parsed.repoFullName} helps developers build AI tooling workflows."
            )
        )
        return Candidate(
            repoFullName=parsed.repoFullName,
            repoUrl=parsed.repoUrl,
            description=str(extra.get("description", parsed.description)),
            language=str(extra.get("language", parsed.language)),
            topics=_string_list(extra.get("topics", ["ai", "developer-tools"])),
            stars=_int_value(extra.get("stars", 12000)),
            forks=_int_value(extra.get("forks", 800)),
            todayStars=_int_value(extra.get("todayStars", parsed.todayStars)),
            readmeText=readme,
            readmeSummary=readme[:240],
            createdAt=str(extra.get("createdAt", "2026-05-01T00:00:00Z")),
            updatedAt=str(extra.get("updatedAt", now_iso())),
            license=str(extra.get("license", "MIT")),
            collectedAt=now_iso(),
        )

    def fallback_search(self, limit: int) -> list[Candidate]:
        return [
            Candidate(
                repoFullName=f"fallback/repo-{idx}",
                repoUrl=f"https://github.com/fallback/repo-{idx}",
                description="Fallback GitHub search candidate",
                language="Python",
                topics=["ai", "developer-tools"],
                stars=1000 + idx,
                forks=100,
                todayStars=50,
                readmeText="Fallback README describing developer tooling and AI workflows.",
                readmeSummary="Fallback README describing developer tooling and AI workflows.",
                createdAt="2026-05-01T00:00:00Z",
                updatedAt=now_iso(),
                license="MIT",
                collectedAt=now_iso(),
            )
            for idx in range(1, limit + 1)
        ]


class ParsedGitHubMetadataClient:
    def enrich(self, parsed: ParsedTrendingRepo) -> Candidate:
        return _candidate_from_parsed(parsed)

    def fallback_search(self, limit: int) -> list[Candidate]:
        return MockGitHubMetadataClient().fallback_search(limit)


class GitHubApiMetadataClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def enrich(self, parsed: ParsedTrendingRepo) -> Candidate:
        owner, name = parsed.repoFullName.split("/", 1)
        repo = self._get_json(f"https://api.github.com/repos/{owner}/{name}")
        readme = self._get_readme(owner, name)
        topics = _string_list(repo.get("topics", []))
        license_payload = repo.get("license")
        license_name = ""
        if isinstance(license_payload, dict):
            license_name = str(license_payload.get("spdx_id") or license_payload.get("name") or "")
        return Candidate(
            repoFullName=parsed.repoFullName,
            repoUrl=str(repo.get("html_url", parsed.repoUrl)),
            description=str(repo.get("description") or parsed.description),
            language=str(repo.get("language") or parsed.language or ""),
            topics=topics,
            stars=_int_value(repo.get("stargazers_count", 0)),
            forks=_int_value(repo.get("forks_count", 0)),
            todayStars=parsed.todayStars,
            readmeText=readme,
            readmeSummary=readme[:500],
            createdAt=str(repo.get("created_at", "")),
            updatedAt=str(repo.get("updated_at", "")),
            license=license_name,
            collectedAt=now_iso(),
        )

    def fallback_search(self, limit: int) -> list[Candidate]:
        payload = self._get_json(
            "https://api.github.com/search/repositories"
            "?q=stars:%3E1000+pushed:%3E2026-01-01&sort=stars&order=desc"
        )
        raw_items = payload.get("items", []) if isinstance(payload, dict) else []
        items = cast(list[object], raw_items)
        candidates: list[Candidate] = []
        for item in items[:limit]:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("full_name", ""))
            if "/" not in full_name:
                continue
            parsed = ParsedTrendingRepo(
                repoFullName=full_name,
                repoUrl=str(item.get("html_url", f"https://github.com/{full_name}")),
                description=str(item.get("description") or ""),
                language=str(item.get("language") or ""),
                todayStars=0,
            )
            candidates.append(self.enrich(parsed))
        return candidates

    def _get_json(self, url: str) -> dict[str, object]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "github-daily-video-mvp",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise AppError(
                "GITHUB_API_FAILED",
                "GitHub API metadata fetch failed",
                exc.code >= 500 or exc.code == 429,
                {"reason": exc.__class__.__name__, "httpStatus": exc.code},
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AppError(
                "GITHUB_API_FAILED",
                "GitHub API metadata fetch failed",
                True,
                {"reason": exc.__class__.__name__, "detail": str(exc)},
            ) from exc
        if not isinstance(payload, dict):
            raise AppError("GITHUB_API_FAILED", "GitHub API returned invalid JSON", True, {})
        return payload

    def _get_readme(self, owner: str, name: str) -> str:
        headers = {
            "Accept": "application/vnd.github.raw",
            "User-Agent": "github-daily-video-mvp",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{name}/readme", headers=headers
        )
        try:
            with urllib.request.urlopen(request, timeout=20) as response:
                readme = response.read().decode("utf-8", errors="replace")
                return str(readme)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            return ""


class GitHubCollectorService:
    def __init__(
        self,
        repository: SQLiteRepository,
        parser: TrendingParser | None = None,
        fetcher: TrendingPageFetcher | None = None,
        metadata_client: GitHubMetadataClient | None = None,
    ) -> None:
        self.repository = repository
        self.parser = parser or TrendingParser()
        self.fetcher = fetcher or StaticTrendingPageFetcher(default_trending_html())
        self.metadata_client = metadata_client or MockGitHubMetadataClient()

    def fetch_single_repo(self, repo_full_name: str) -> Candidate:
        parsed = ParsedTrendingRepo(
            repoFullName=repo_full_name,
            repoUrl=f"https://github.com/{repo_full_name}",
            description="",
            language="",
            todayStars=0,
        )
        try:
            return GitHubApiMetadataClient().enrich(parsed)
        except AppError as exc:
            if not exc.retryable:
                raise
            return _candidate_from_parsed(parsed)

    def collect(
        self, language: str = "all", since: str = "daily", limit: int = 20
    ) -> dict[str, object]:
        if since != "daily":
            raise AppError(
                "INVALID_TRENDING_SINCE",
                "MVP only supports daily trending",
                False,
                {"since": since},
            )
        try:
            html = self.fetcher.fetch(language, since)
            parsed = self.parser.parse(html, limit)
            candidates = []
            for item in parsed:
                try:
                    candidates.append(self.metadata_client.enrich(item))
                except AppError as exc:
                    if not exc.retryable:
                        raise
                    candidates.append(_candidate_from_parsed(item))
        except AppError as exc:
            if exc.retryable:
                try:
                    candidates = self.metadata_client.fallback_search(limit)
                except AppError:
                    candidates = MockGitHubMetadataClient().fallback_search(limit)
            else:
                raise
        saved = self.repository.upsert_candidates(candidates[:limit])
        self.repository.add_run_log(
            "github_collector", "collect", True, artifact_refs={"count": len(saved)}
        )
        return {
            "jobId": f"collect_{uuid4().hex[:8]}",
            "candidates": [item.model_dump() for item in saved],
        }


def _candidate_from_parsed(parsed: ParsedTrendingRepo) -> Candidate:
    summary = parsed.description or f"{parsed.repoFullName} is trending on GitHub."
    return Candidate(
        repoFullName=parsed.repoFullName,
        repoUrl=parsed.repoUrl,
        description=summary,
        language=parsed.language,
        topics=[],
        stars=max(parsed.todayStars * 10, parsed.todayStars),
        forks=0,
        todayStars=parsed.todayStars,
        readmeText=summary,
        readmeSummary=summary[:500],
        createdAt="",
        updatedAt=now_iso(),
        license="",
        collectedAt=now_iso(),
    )


def default_trending_html() -> str:
    return """
    <article class="Box-row">
      <h2><a href="/alpha/ai-tool"> alpha / ai-tool </a></h2>
      <p>AI developer workflow automation.</p>
      <span itemprop="programmingLanguage">Python</span>
      <span>321 stars today</span>
    </article>
    <article class="Box-row">
      <h2><a href="/beta/code-agent"> beta / code-agent </a></h2>
      <p>Code agent framework for developers.</p>
      <span itemprop="programmingLanguage">TypeScript</span>
      <span>210 stars today</span>
    </article>
    <article class="Box-row">
      <h2><a href="/gamma/local-llm"> gamma / local-llm </a></h2>
      <p>Run local LLM developer tools.</p>
      <span itemprop="programmingLanguage">Go</span>
      <span>140 stars today</span>
    </article>
    """


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


def _string_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []
