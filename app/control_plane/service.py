from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

from app.content_generation import ContentGenerationService
from app.contracts.errors import AppError
from app.contracts.schemas import Candidate, VideoGenerationConfig
from app.contracts.statuses import TaskStatus
from app.github_collector import GitHubCollectorService
from app.manual_review import ManualReviewService
from app.publish_ledger import PublishLedgerService
from app.quality_check import QualityCheckService
from app.scoring import ScoringService
from app.storage.repository import SQLiteRepository, utc_now
from app.tts_subtitle import TTSSubtitleService
from app.video_rendering import VideoRenderingService


class ControlPlaneService:
    def __init__(
        self,
        repository: SQLiteRepository,
        collector: GitHubCollectorService,
        scoring: ScoringService,
        content: ContentGenerationService,
        tts: TTSSubtitleService,
        renderer: VideoRenderingService,
        quality: QualityCheckService,
        review: ManualReviewService,
        publish: PublishLedgerService,
    ) -> None:
        self.repository = repository
        self.collector = collector
        self.scoring = scoring
        self.content = content
        self.tts = tts
        self.renderer = renderer
        self.quality = quality
        self.review = review
        self.publish = publish

    def discover_candidates(self, candidate_limit: int = 5) -> dict[str, object]:
        collect = self.collector.collect(limit=candidate_limit)
        collect_candidates = cast(list[object], collect["candidates"])
        candidates = [Candidate.model_validate(item) for item in collect_candidates]
        score = self.scoring.score_candidates(
            str(collect["jobId"]), candidates, target_count=min(candidate_limit, 5)
        )
        score_recommended = cast(list[object], score["recommended"])
        recommended = [Candidate.model_validate(item) for item in score_recommended]
        return {
            "jobId": str(score["jobId"]),
            "recommended": [item.model_dump() for item in recommended],
            "degraded": score.get("degraded", False),
        }

    def _run_pipeline(
        self,
        task_id: str,
        repo_full_name: str,
        config: VideoGenerationConfig | None = None,
    ) -> dict[str, object]:
        effective_config = config or VideoGenerationConfig()
        script_config = effective_config.scriptConfig
        tts_config = effective_config.ttsConfig
        visual_config = effective_config.visualConfig
        script_result = self.content.generate_script(
            repo_full_name,
            script_config.style,
            script_config.durationSec,
            script_config.audience,
            task_id,
            script_config,
        )
        self.repository.update_task_status(task_id, TaskStatus.SCRIPT_GENERATED, "script generated")
        script_payload = cast(dict[str, object], script_result["script"])
        tts_result = self.tts.generate_tts(task_id, script_payload, tts_config.voiceId, tts_config)
        self.repository.update_task_status(task_id, TaskStatus.TTS_GENERATED, "tts generated")
        render_submit = self.renderer.render_video(
            task_id,
            "github_daily_code_ppt_v1",
            str(script_result["scriptUrl"]),
            str(tts_result["audioUrl"]),
            str(tts_result["subtitleUrl"]),
            visual_config,
        )
        self.repository.update_task_status(task_id, TaskStatus.RENDERING, "render submitted")
        render_result = render_submit["result"]
        render_payload = cast(dict[str, object], render_result)
        self.repository.update_task_status(task_id, TaskStatus.RENDERED, "render completed")
        qc = self.quality.run(
            task_id,
            str(script_result["scriptUrl"]),
            str(tts_result["audioUrl"]),
            str(tts_result["subtitleUrl"]),
            str(render_payload["videoUrl"]),
            str(render_payload["coverUrl"]),
        )
        if not qc["passed"]:
            raise AppError(
                "QUALITY_CHECK_FAILED", "Quality check failed", False, {"taskId": task_id}
            )
        self.repository.update_task_status(
            task_id, TaskStatus.REVIEW_PENDING, "quality check passed"
        )
        return {
            "scriptResult": script_result,
            "ttsResult": tts_result,
            "renderResult": render_payload,
            "quality": qc,
        }

    def run_to_review_pending(
        self, candidate_limit: int = 5, config: VideoGenerationConfig | None = None
    ) -> dict[str, object]:
        run_folder = self._begin_output_folder()
        discover = self.discover_candidates(candidate_limit)
        recommended = [
            Candidate.model_validate(item) for item in cast(list[object], discover["recommended"])
        ]
        selected = recommended[0]
        task = self.repository.create_task(selected.repoFullName, selected_by="system")
        task_id = str(task["taskId"])
        try:
            self.repository.update_task_status(
                task_id, TaskStatus.COLLECTED, "candidates collected"
            )
            self.repository.update_task_status(task_id, TaskStatus.SCORED, "candidate scored")
            pipeline = self._run_pipeline(task_id, selected.repoFullName, config)
            return {
                "taskId": task_id,
                "outputFolder": run_folder,
                "selected": selected.model_dump(),
                "recommended": [item.model_dump() for item in recommended],
                "quality": pipeline["quality"],
                "task": self.repository.get_task(task_id),
            }
        except AppError as exc:
            task = self.repository.get_task(task_id)
            if task["status"] != TaskStatus.FAILED.value:
                self.repository.fail_task(task_id, "control_plane", exc)
            raise

    def generate_for_repo(
        self, repo_full_name: str, config: VideoGenerationConfig | None = None
    ) -> dict[str, object]:
        run_folder = self._begin_output_folder()
        candidate = self.collector.fetch_single_repo(repo_full_name)
        self.repository.upsert_candidates([candidate])
        task = self.repository.create_task(repo_full_name, selected_by="manual")
        task_id = str(task["taskId"])
        try:
            self.repository.update_task_status(
                task_id, TaskStatus.COLLECTED, "repo metadata fetched"
            )
            self.repository.update_task_status(task_id, TaskStatus.SCORED, "single repo selected")
            pipeline = self._run_pipeline(task_id, repo_full_name, config)
            return {
                "taskId": task_id,
                "outputFolder": run_folder,
                "selected": candidate.model_dump(),
                "quality": pipeline["quality"],
                "task": self.repository.get_task(task_id),
            }
        except AppError as exc:
            task = self.repository.get_task(task_id)
            if task["status"] != TaskStatus.FAILED.value:
                self.repository.fail_task(task_id, "control_plane", exc)
            raise

    def _begin_output_folder(self) -> str | None:
        object_store = getattr(self.content, "object_store", None)
        if object_store is None or not hasattr(object_store, "begin_run"):
            return None
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = object_store.begin_run(f"{timestamp}_github_daily_video")
        return str(path.resolve())

    def generate_from_selection(
        self, repo_full_name: str, config: VideoGenerationConfig | None = None
    ) -> dict[str, object]:
        run_folder = self._begin_output_folder()
        candidate = self.repository.get_candidate(repo_full_name)
        if candidate is None:
            candidate = self.collector.fetch_single_repo(repo_full_name)
            self.repository.upsert_candidates([candidate])
        task = self.repository.create_task(repo_full_name, selected_by="manual")
        task_id = str(task["taskId"])
        try:
            self.repository.update_task_status(
                task_id, TaskStatus.COLLECTED, "candidate selected from recommendation"
            )
            self.repository.update_task_status(task_id, TaskStatus.SCORED, "candidate confirmed")
            pipeline = self._run_pipeline(task_id, repo_full_name, config)
            return {
                "taskId": task_id,
                "outputFolder": run_folder,
                "selected": candidate.model_dump(),
                "quality": pipeline["quality"],
                "task": self.repository.get_task(task_id),
            }
        except AppError as exc:
            task = self.repository.get_task(task_id)
            if task["status"] != TaskStatus.FAILED.value:
                self.repository.fail_task(task_id, "control_plane", exc)
            raise

    def approve_export_and_record(
        self, task_id: str, platform: str = "douyin"
    ) -> dict[str, object]:
        self.review.decide(task_id, "approved", "approved for manual publish")
        package = self.publish.export_package(
            task_id, ["douyin", "wechat_channels", "bilibili", "xiaohongshu"]
        )
        items = cast(dict[str, object], package["items"])
        record = self.publish.create_publish_record(
            {
                "taskId": task_id,
                "platform": platform,
                "title": items["title"],
                "description": items["description"],
                "hashtags": items["hashtags"],
                "publishedAt": utc_now(),
                "publishUrl": "https://example.com/manual-video",
                "operator": "manual",
            }
        )
        return {
            "package": package,
            "publishRecord": record,
            "task": self.repository.get_task(task_id),
        }
