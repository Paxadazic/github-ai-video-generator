from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from app.contracts.errors import AppError
from app.contracts.schemas import Candidate
from app.storage.repository import SQLiteRepository


@dataclass(frozen=True)
class ScoringConfig:
    trending_heat_weight: float = 20
    star_proof_weight: float = 15
    readme_weight: float = 20
    relevance_weight: float = 20
    freshness_weight: float = 15
    abnormal_penalty: float = 10


class CandidateFilter:
    def is_valid(self, candidate: Candidate) -> bool:
        if not candidate.description.strip():
            return False
        if (
            not candidate.repoUrl.startswith("https://github.com/")
            or "/" not in candidate.repoFullName
        ):
            return False
        if len(candidate.readmeText.strip()) < 30:
            return False
        low_quality = {"test", "demo-only", "empty"}
        haystack = f"{candidate.repoFullName} {candidate.description}".lower()
        return not any(word in haystack for word in low_quality)


class RiskFlagger:
    def flags(self, candidate: Candidate) -> list[str]:
        flags: list[str] = []
        try:
            created = datetime.fromisoformat(candidate.createdAt.replace("Z", "+00:00"))
            updated = datetime.fromisoformat(candidate.updatedAt.replace("Z", "+00:00"))
            if (updated - created).days <= 3 and candidate.stars >= 5000:
                flags.append("star_spike")
        except ValueError:
            flags.append("metadata_date_invalid")
        if candidate.todayStars > 200 and len(candidate.readmeText) < 120:
            flags.append("insufficient_info_high_heat")
        return flags


class RuleScorer:
    def __init__(self, config: ScoringConfig) -> None:
        self.config = config

    def score(self, candidate: Candidate, duplicate: bool) -> tuple[float, dict[str, float]]:
        relevance_terms = ["ai", "agent", "developer", "code", "llm", "tool", "workflow"]
        text = " ".join(
            [candidate.description, candidate.readmeText, " ".join(candidate.topics)]
        ).lower()
        relevance = min(sum(1 for term in relevance_terms if term in text) / 4, 1.0)
        breakdown = {
            "trendingHeat": min(candidate.todayStars / 300, 1.0) * self.config.trending_heat_weight,
            "starProof": min(candidate.stars / 20000, 1.0) * self.config.star_proof_weight,
            "readmeExplainability": min(len(candidate.readmeText) / 800, 1.0)
            * self.config.readme_weight,
            "audienceRelevance": relevance * self.config.relevance_weight,
            "freshness": self.config.freshness_weight,
            "duplicatePenalty": -50.0 if duplicate else 0.0,
            "abnormalPenalty": 0.0,
        }
        if "star_spike" in candidate.riskFlags:
            breakdown["abnormalPenalty"] = -self.config.abnormal_penalty
        return round(sum(breakdown.values()), 2), breakdown


class ScoreExplainer:
    def explain(self, candidate: Candidate) -> str:
        parts = [
            f"daily heat {candidate.todayStars}",
            f"{candidate.stars} stars",
            "README is explainable" if candidate.readmeText else "README missing",
        ]
        if candidate.riskFlags:
            parts.append("risk: " + ",".join(candidate.riskFlags))
        return "; ".join(parts)


class ScoringService:
    def __init__(
        self,
        repository: SQLiteRepository,
        config: ScoringConfig | None = None,
        candidate_filter: CandidateFilter | None = None,
    ) -> None:
        self.repository = repository
        self.config = config or ScoringConfig()
        self.filter = candidate_filter or CandidateFilter()
        self.flagger = RiskFlagger()
        self.scorer = RuleScorer(self.config)
        self.explainer = ScoreExplainer()

    def score_candidates(
        self, job_id: str, candidates: list[Candidate] | None = None, target_count: int = 5
    ) -> dict[str, object]:
        target_count = max(1, min(target_count, 5))
        source = candidates if candidates is not None else self.repository.list_candidates()
        scored: list[Candidate] = []
        for candidate in source:
            if not self.filter.is_valid(candidate):
                continue
            duplicate = self.repository.is_deduped(candidate.repoFullName)
            if duplicate:
                continue
            candidate.riskFlags = self.flagger.flags(candidate)
            candidate.score, candidate.scoreBreakdown = self.scorer.score(
                candidate, duplicate=False
            )
            candidate.recommendReason = self.explainer.explain(candidate)
            scored.append(candidate)
        scored.sort(key=lambda item: item.score or 0, reverse=True)
        recommended = scored[:target_count]
        self.repository.update_candidate_scores(recommended)
        self.repository.add_run_log(
            "scoring",
            "score",
            True,
            artifact_refs={"jobId": job_id, "recommended": len(recommended)},
        )
        if not recommended:
            raise AppError(
                "NO_RECOMMENDABLE_CANDIDATES", "No candidates passed filtering", False, {}
            )
        return {
            "jobId": f"score_{uuid4().hex[:8]}",
            "recommended": [candidate.model_dump() for candidate in recommended],
            "degraded": len(recommended) < min(3, target_count),
        }
