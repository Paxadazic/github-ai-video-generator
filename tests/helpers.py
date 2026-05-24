from __future__ import annotations

from app.contracts.schemas import Candidate


def candidate(repo: str = "owner/project", stars: int = 12000, today: int = 300) -> Candidate:
    return Candidate(
        repoFullName=repo,
        repoUrl=f"https://github.com/{repo}",
        description="AI developer tool for practical workflow automation.",
        language="Python",
        topics=["ai", "developer-tools"],
        stars=stars,
        forks=300,
        todayStars=today,
        readmeText=(
            "This README explains a developer tooling project for AI workflows and code automation."
        ),
        readmeSummary="Developer tooling project for AI workflows.",
        createdAt="2026-05-01T00:00:00Z",
        updatedAt="2026-05-22T00:00:00Z",
        license="MIT",
    )


def script_payload() -> dict[str, object]:
    return {
        "title": "Project is trending",
        "coverText": "GitHub pick",
        "description": "A developer-friendly overview.",
        "hashtags": ["GitHub", "OpenSource"],
        "segments": [
            {
                "type": "hook",
                "durationSec": 20,
                "voiceText": "This project is getting attention from developers.",
                "screenText": "Trending now",
                "visualHint": "Repository card",
                "emotion": "excited",
            },
            {
                "type": "value",
                "durationSec": 25,
                "voiceText": "It focuses on practical workflow automation.",
                "screenText": "Workflow automation",
                "visualHint": "README highlights",
                "emotion": "confident",
            },
            {
                "type": "cta",
                "durationSec": 20,
                "voiceText": "Check the GitHub link before trying it.",
                "screenText": "Check GitHub",
                "visualHint": "CTA",
                "emotion": "calm",
            },
        ],
        "cta": "Save it for later.",
    }
