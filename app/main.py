from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from app.config import Settings, load_settings
from app.content_generation import ContentGenerationService
from app.content_generation.service import (
    DeepSeekModelAdapter,
    MiniMaxCliModelAdapter,
    ModelAdapter,
)
from app.contracts.errors import AppError
from app.contracts.responses import error_response, success_response
from app.contracts.schemas import (
    ScriptGenerationConfig,
    TTSConfig,
    VideoGenerationConfig,
    VideoPresetPayload,
    VisualConfig,
    default_video_preset_payload,
)
from app.control_plane import ControlPlaneService
from app.github_collector import GitHubCollectorService
from app.github_collector.service import (
    GitHubApiMetadataClient,
    GitHubTrendingPageFetcher,
    ParsedGitHubMetadataClient,
)
from app.manual_review import ManualReviewService
from app.minimax_cli import MiniMaxCliRunner
from app.publish_ledger import PublishLedgerService
from app.quality_check import QualityCheckService
from app.scoring import ScoringService
from app.storage import LocalObjectStore, SQLiteRepository
from app.tts_subtitle import TTSSubtitleService
from app.tts_subtitle.service import (
    EdgeTTSAdapter,
    MiniMaxCliTTSAdapter,
    MiniMaxTTSAdapter,
    TTSAdapter,
    WindowsSapiTTSAdapter,
)
from app.video_rendering import VideoRenderingService
from app.video_rendering.service import FfmpegInfoRenderAdapter


class CollectRequest(BaseModel):
    language: str = "all"
    since: str = "daily"
    limit: int = Field(default=20, ge=1, le=100)


class ScoreRequest(BaseModel):
    jobId: str
    candidates: list[dict[str, Any]] | None = None
    targetCount: int = Field(default=5, ge=1, le=5)


class ScriptRequest(BaseModel):
    repoFullName: str
    style: str = "code_ppt"
    durationSec: int = 75
    audience: str = "chinese_developers"
    taskId: str | None = None
    scriptConfig: ScriptGenerationConfig | None = None


class TTSRequest(BaseModel):
    taskId: str
    voice: str = "default_cn_tech"
    script: dict[str, Any]
    ttsConfig: TTSConfig | None = None


class RenderRequest(BaseModel):
    taskId: str
    template: str = "github_daily_code_ppt_v1"
    scriptUrl: str
    audioUrl: str
    subtitleUrl: str
    visualConfig: VisualConfig | None = None


class QualityRequest(BaseModel):
    taskId: str
    scriptUrl: str
    audioUrl: str
    subtitleUrl: str
    videoUrl: str
    coverUrl: str


class ReviewDecisionRequest(BaseModel):
    taskId: str
    decision: str
    comment: str = ""
    retryAction: str | None = None
    reviewer: str = "manual"


class ExportPackageRequest(BaseModel):
    taskId: str
    platforms: list[str] = Field(
        default_factory=lambda: ["douyin", "wechat_channels", "bilibili", "xiaohongshu"]
    )


class PublishRecordRequest(BaseModel):
    taskId: str
    platform: str
    title: str
    description: str
    hashtags: list[str] = Field(default_factory=list)
    publishedAt: str
    publishUrl: str | None = None
    operator: str

    model_config = {"extra": "allow"}


class GenerateVideoRequest(BaseModel):
    provider: str = "local"
    candidateLimit: int = Field(default=5, ge=1, le=20)
    useDeepSeek: bool = False
    ttsMode: str = "mock"
    renderMode: str = "ffmpeg_info"
    presetId: str | None = None
    scriptConfig: ScriptGenerationConfig | None = None
    ttsConfig: TTSConfig | None = None
    visualConfig: VisualConfig | None = None


class DiscoverRequest(BaseModel):
    candidateLimit: int = Field(default=5, ge=1, le=20)


class GenerateFromSelectionRequest(BaseModel):
    repoFullName: str
    provider: str = "local"
    useDeepSeek: bool = False
    ttsMode: str = "mock"
    renderMode: str = "ffmpeg_info"
    presetId: str | None = None
    scriptConfig: ScriptGenerationConfig | None = None
    ttsConfig: TTSConfig | None = None
    visualConfig: VisualConfig | None = None


class GenerateForRepoRequest(BaseModel):
    repoFullName: str
    provider: str = "local"
    useDeepSeek: bool = False
    ttsMode: str = "mock"
    renderMode: str = "ffmpeg_info"
    presetId: str | None = None
    scriptConfig: ScriptGenerationConfig | None = None
    ttsConfig: TTSConfig | None = None
    visualConfig: VisualConfig | None = None


class VideoPresetRequest(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    scriptConfig: ScriptGenerationConfig = Field(default_factory=ScriptGenerationConfig)
    ttsConfig: TTSConfig = Field(default_factory=TTSConfig)
    visualConfig: VisualConfig = Field(default_factory=VisualConfig)
    isDefault: bool = False


class Services(BaseModel):
    repository: Any
    object_store: Any
    collector: Any
    scoring: Any
    content: Any
    tts: Any
    renderer: Any
    quality: Any
    review: Any
    publish: Any
    control: Any

    model_config = {"arbitrary_types_allowed": True}


def create_services(settings: Settings | None = None) -> Services:
    settings = settings or load_settings()
    repository = SQLiteRepository(settings.database_url)
    object_store = LocalObjectStore(settings.object_storage_dir)
    use_real_trending = settings.github_provider in {"real", "real_trending_only"}
    collector = GitHubCollectorService(
        repository,
        fetcher=GitHubTrendingPageFetcher() if use_real_trending else None,
        metadata_client=(
            GitHubApiMetadataClient(settings.github_token)
            if settings.github_provider == "real"
            else ParsedGitHubMetadataClient()
            if settings.github_provider == "real_trending_only"
            else None
        ),
    )
    scoring = ScoringService(repository)
    minimax_cli_runner = MiniMaxCliRunner(
        settings.minimax_cli_path,
        settings.minimax_cli_region,
        settings.minimax_runtime_tmp_dir,
    )
    model_adapter: ModelAdapter | None = None
    if settings.model_provider == "deepseek":
        model_adapter = DeepSeekModelAdapter(settings.deepseek_api_key, settings.deepseek_model)
    elif settings.model_provider == "minimax":
        model_adapter = MiniMaxCliModelAdapter(minimax_cli_runner, settings.minimax_text_model)
    content = ContentGenerationService(
        repository,
        object_store,
        model_adapter=model_adapter,
    )
    tts_adapter: TTSAdapter | None = None
    if settings.tts_provider == "windows_sapi":
        tts_adapter = WindowsSapiTTSAdapter()
    elif settings.tts_provider == "edge_tts":
        tts_adapter = EdgeTTSAdapter()
    elif settings.tts_provider == "minimax":
        tts_adapter = MiniMaxCliTTSAdapter(
            minimax_cli_runner,
            settings.minimax_tts_model,
            settings.minimax_tts_voice_id,
        )
    elif settings.tts_provider == "minimax_http":
        tts_adapter = MiniMaxTTSAdapter(
            settings.minimax_api_key,
            settings.minimax_tts_model,
            settings.minimax_tts_endpoint,
            settings.minimax_tts_voice_id,
        )
    tts = TTSSubtitleService(repository, object_store, adapter=tts_adapter)
    renderer = VideoRenderingService(
        repository,
        object_store,
        adapter=FfmpegInfoRenderAdapter() if settings.render_provider == "ffmpeg_info" else None,
    )
    quality = QualityCheckService(repository, object_store)
    review = ManualReviewService(repository)
    publish = PublishLedgerService(repository, object_store)
    control = ControlPlaneService(
        repository, collector, scoring, content, tts, renderer, quality, review, publish
    )
    return Services(
        repository=repository,
        object_store=object_store,
        collector=collector,
        scoring=scoring,
        content=content,
        tts=tts,
        renderer=renderer,
        quality=quality,
        review=review,
        publish=publish,
        control=control,
    )


def create_real_generation_services(
    use_deepseek: bool = False,
    provider: str = "local",
    tts_provider: str = "mock",
    render_provider: str = "ffmpeg_info",
) -> Services:
    model_provider = provider
    if provider == "local":
        model_provider = "mock"
    if use_deepseek:
        model_provider = "deepseek"
    github_provider = "real_trending_only" if provider == "local" else "real"
    settings = replace(
        load_settings(),
        github_provider=github_provider,
        model_provider=model_provider,
        tts_provider=tts_provider,
        render_provider=render_provider,
    )
    return create_services(settings)


def _asset_payload(asset: dict[str, Any]) -> dict[str, Any]:
    return {
        **asset,
        "contentUrl": f"/api/assets/{asset['assetId']}/content",
        "localUrl": asset["url"],
    }


def _script_summary(
    services: Services, assets_by_type: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    script_asset = assets_by_type.get("script")
    if script_asset is None:
        return {}
    try:
        script = services.object_store.read_json_url(str(script_asset["url"]))
    except (OSError, ValueError):
        return {"title": script_asset.get("metadata", {}).get("title", "")}
    segments = script.get("segments", [])
    voice_text = " ".join(
        str(segment.get("voiceText", ""))
        for segment in segments
        if isinstance(segment, dict)
    )
    return {
        "title": script.get("title", script_asset.get("metadata", {}).get("title", "")),
        "coverText": script.get("coverText", ""),
        "description": script.get("description", ""),
        "hashtags": script.get("hashtags", []),
        "segmentCount": len(segments) if isinstance(segments, list) else 0,
        "voiceSummary": voice_text[:240],
    }


def _quality_summary(task: dict[str, Any]) -> dict[str, Any]:
    last_error = task.get("lastError")
    failed_checks: list[Any] = []
    if isinstance(last_error, dict):
        detail = last_error.get("detail")
        if isinstance(detail, dict):
            raw_failed_checks = detail.get("failedChecks")
            if isinstance(raw_failed_checks, list):
                failed_checks = raw_failed_checks
    return {
        "passed": task["status"] not in {"failed", "rejected"} if not failed_checks else False,
        "failedChecks": failed_checks,
    }


def _task_summary(services: Services, task: dict[str, Any]) -> dict[str, Any]:
    task_id = str(task["taskId"])
    candidate = services.repository.get_candidate(str(task["repoFullName"]))
    assets = services.repository.list_assets(task_id)
    assets_by_type = {str(asset["type"]): _asset_payload(asset) for asset in assets}
    script_summary = _script_summary(services, {str(asset["type"]): asset for asset in assets})
    return {
        "taskId": task_id,
        "repoFullName": task["repoFullName"],
        "repoUrl": candidate.repoUrl if candidate else "",
        "status": task["status"],
        "title": script_summary.get("title", ""),
        "updatedAt": task["updatedAt"],
        "createdAt": task["createdAt"],
        "lastError": task["lastError"],
        "assets": {
            key: assets_by_type[key]
            for key in ("video", "cover", "audio", "script", "subtitle", "package")
            if key in assets_by_type
        },
    }


def _task_detail(services: Services, task_id: str) -> dict[str, Any]:
    task = services.repository.get_task(task_id)
    candidate = services.repository.get_candidate(str(task["repoFullName"]))
    assets = services.repository.list_assets(task_id)
    raw_assets_by_type = {str(asset["type"]): asset for asset in assets}
    assets_by_type = {
        asset_type: _asset_payload(asset) for asset_type, asset in raw_assets_by_type.items()
    }
    return {
        "task": task,
        "candidate": candidate.model_dump() if candidate else None,
        "assets": [_asset_payload(asset) for asset in assets],
        "assetsByType": assets_by_type,
        "review": services.review.get_review_detail(task_id),
        "publishRecords": services.repository.list_publish_records(task_id),
        "scriptSummary": _script_summary(services, raw_assets_by_type),
        "quality": _quality_summary(task),
    }


def _merge_generation_config(
    base: VideoGenerationConfig,
    request: GenerateVideoRequest | GenerateFromSelectionRequest | GenerateForRepoRequest,
) -> VideoGenerationConfig:
    data = base.model_dump()
    if request.scriptConfig is not None:
        data["scriptConfig"] |= request.scriptConfig.model_dump(exclude_unset=True)
    if request.ttsConfig is not None:
        data["ttsConfig"] |= request.ttsConfig.model_dump(exclude_unset=True)
    if request.visualConfig is not None:
        data["visualConfig"] |= request.visualConfig.model_dump(exclude_unset=True)
    if request.scriptConfig is None:
        provider = "deepseek" if request.useDeepSeek or request.provider == "deepseek" else request.provider
        data["scriptConfig"]["provider"] = "local" if provider == "local" else provider
    if request.ttsConfig is None:
        data["ttsConfig"]["provider"] = request.ttsMode
    config = VideoGenerationConfig.model_validate(data)
    script = config.scriptConfig
    if script.provider == "deepseek" and script.model == "MiniMax-M2.7":
        config = config.model_copy(
            update={"scriptConfig": script.model_copy(update={"model": "deepseek-v4-flash"})}
        )
    return config


def _effective_generation_config(
    services: Services,
    request: GenerateVideoRequest | GenerateFromSelectionRequest | GenerateForRepoRequest,
) -> VideoGenerationConfig:
    preset = (
        services.repository.get_video_preset(request.presetId)
        if request.presetId
        else services.repository.get_default_video_preset()
    )
    payload = preset.get("payload") or default_video_preset_payload()
    base = VideoPresetPayload.model_validate(payload)
    return _merge_generation_config(VideoGenerationConfig.model_validate(base.model_dump()), request)


def _preset_response(item: dict[str, Any]) -> dict[str, Any]:
    payload = VideoPresetPayload.model_validate(item.get("payload") or default_video_preset_payload())
    return {
        "presetId": item["presetId"],
        "name": item["name"],
        "isDefault": bool(item["isDefault"]),
        "createdAt": item["createdAt"],
        "updatedAt": item["updatedAt"],
        "payload": payload.model_dump(),
    }


def create_app(services: Services | None = None) -> FastAPI:
    app = FastAPI(title="GitHub Daily Video MVP")
    app.state.services = services or create_services()

    def wrap(handler: Callable[[], dict[str, Any]]) -> dict[str, Any]:
        try:
            return success_response(handler())
        except AppError as exc:
            return error_response(exc)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return GENERATE_PAGE

    @app.get("/health")
    def health() -> dict[str, Any]:
        return success_response({"status": "ok"})

    def _generation_services(
        request: GenerateVideoRequest | GenerateFromSelectionRequest | GenerateForRepoRequest,
        config: VideoGenerationConfig,
    ) -> Services:
        use_deepseek = request.useDeepSeek or config.scriptConfig.provider == "deepseek"
        return create_real_generation_services(
            use_deepseek,
            config.scriptConfig.provider,
            config.ttsConfig.provider,
            request.renderMode,
        )

    def _format_generation_result(services: Services, result: dict[str, Any]) -> dict[str, Any]:
        task_id = str(result["taskId"])
        detail = services.review.get_review_detail(task_id)
        assets = services.repository.list_assets(task_id)
        paths = {
            str(asset["type"]): str(
                services.object_store.path_from_url(str(asset["url"]))
            )
            for asset in assets
            if asset["type"] in {"video", "cover", "audio", "script", "subtitle"}
        }
        return {
            "taskId": task_id,
            "outputFolder": result.get("outputFolder"),
            "selected": result.get("selected"),
            "review": detail,
            "paths": paths,
        }

    @app.post("/api/discover")
    def discover(request: DiscoverRequest) -> dict[str, Any]:
        return wrap(lambda: app.state.services.control.discover_candidates(request.candidateLimit))

    @app.get("/api/video-presets")
    def list_video_presets() -> dict[str, Any]:
        return wrap(
            lambda: {
                "presets": [
                    _preset_response(item)
                    for item in app.state.services.repository.list_video_presets()
                ]
            }
        )

    @app.get("/api/video-presets/{preset_id}")
    def get_video_preset(preset_id: str) -> dict[str, Any]:
        return wrap(lambda: _preset_response(app.state.services.repository.get_video_preset(preset_id)))

    @app.post("/api/video-presets")
    def create_video_preset(request: VideoPresetRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            payload = VideoPresetPayload(
                name=request.name,
                scriptConfig=request.scriptConfig,
                ttsConfig=request.ttsConfig,
                visualConfig=request.visualConfig,
            ).model_dump()
            item = app.state.services.repository.upsert_video_preset(
                request.name, payload, is_default=request.isDefault
            )
            return {"preset": _preset_response(item)}

        return wrap(run)

    @app.put("/api/video-presets/{preset_id}")
    def update_video_preset(preset_id: str, request: VideoPresetRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            payload = VideoPresetPayload(
                name=request.name,
                scriptConfig=request.scriptConfig,
                ttsConfig=request.ttsConfig,
                visualConfig=request.visualConfig,
            ).model_dump()
            item = app.state.services.repository.upsert_video_preset(
                request.name, payload, preset_id, request.isDefault
            )
            return {"preset": _preset_response(item)}

        return wrap(run)

    @app.delete("/api/video-presets/{preset_id}")
    def delete_video_preset(preset_id: str) -> dict[str, Any]:
        return wrap(
            lambda: (
                app.state.services.repository.delete_video_preset(preset_id) or {"deleted": True}
            )
        )

    @app.post("/api/video/generate-from-selection")
    def generate_from_selection(request: GenerateFromSelectionRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            config = _effective_generation_config(app.state.services, request)
            services = _generation_services(request, config)
            result = services.control.generate_from_selection(request.repoFullName, config)
            return _format_generation_result(services, result)
        return wrap(run)

    @app.post("/api/video/generate-for-repo")
    def generate_for_repo(request: GenerateForRepoRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            config = _effective_generation_config(app.state.services, request)
            services = _generation_services(request, config)
            result = services.control.generate_for_repo(request.repoFullName, config)
            return _format_generation_result(services, result)
        return wrap(run)

    @app.post("/api/video/generate-real")
    def generate_real_video(request: GenerateVideoRequest) -> dict[str, Any]:
        def run() -> dict[str, Any]:
            config = _effective_generation_config(app.state.services, request)
            services = _generation_services(request, config)
            result = services.control.run_to_review_pending(request.candidateLimit, config)
            return _format_generation_result(services, result)
        return wrap(run)

    @app.get("/api/tasks/recent")
    def recent_tasks(limit: int = Query(default=20, ge=1, le=100)) -> dict[str, Any]:
        return wrap(
            lambda: {
                "tasks": [
                    _task_summary(app.state.services, task)
                    for task in app.state.services.repository.list_tasks(limit)
                ]
            }
        )

    @app.get("/api/tasks/{task_id}")
    def task_detail(task_id: str) -> dict[str, Any]:
        return wrap(lambda: _task_detail(app.state.services, task_id))

    @app.get("/api/assets/{asset_id}/content", response_model=None)
    def asset_content(asset_id: str) -> Any:
        try:
            asset = app.state.services.repository.get_asset(asset_id)
            path = app.state.services.object_store.path_from_url(str(asset["url"]))
            if not path.exists() or not path.is_file():
                raise AppError(
                    "ASSET_CONTENT_NOT_FOUND",
                    "Asset content was not found on disk",
                    False,
                    {"assetId": asset_id},
                )
            return FileResponse(
                path,
                media_type=str(asset["contentType"]),
                filename=path.name,
            )
        except AppError as exc:
            return error_response(exc)

    @app.post("/api/jobs/collect-github-daily")
    def collect(request: CollectRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.collector.collect(
                request.language, request.since, request.limit
            )
        )

    @app.post("/api/jobs/score-candidates")
    def score(request: ScoreRequest) -> dict[str, Any]:
        from app.contracts.schemas import Candidate

        candidates = (
            [Candidate.model_validate(item) for item in request.candidates]
            if request.candidates
            else None
        )
        return wrap(
            lambda: app.state.services.scoring.score_candidates(
                request.jobId, candidates, request.targetCount
            )
        )

    @app.post("/api/jobs/generate-script")
    def generate_script(request: ScriptRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.content.generate_script(
                request.repoFullName,
                request.style,
                request.durationSec,
                request.audience,
                request.taskId,
                request.scriptConfig,
            )
        )

    @app.post("/api/jobs/generate-tts")
    def generate_tts(request: TTSRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.tts.generate_tts(
                request.taskId, request.script, request.voice, request.ttsConfig
            )
        )

    @app.post("/api/jobs/render-video")
    def render_video(request: RenderRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.renderer.render_video(
                request.taskId,
                request.template,
                request.scriptUrl,
                request.audioUrl,
                request.subtitleUrl,
                request.visualConfig,
            )
        )

    @app.get("/api/jobs/render-video/{render_job_id}")
    def get_render_job(render_job_id: str) -> dict[str, Any]:
        return wrap(lambda: app.state.services.renderer.get_render_job(render_job_id))

    @app.post("/api/jobs/quality-check")
    def quality_check(request: QualityRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.quality.run(
                request.taskId,
                request.scriptUrl,
                request.audioUrl,
                request.subtitleUrl,
                request.videoUrl,
                request.coverUrl,
            )
        )

    @app.get("/api/review/{task_id}")
    def review_detail(task_id: str) -> dict[str, Any]:
        return wrap(lambda: app.state.services.review.get_review_detail(task_id))

    @app.post("/api/review/decision")
    def review_decision(request: ReviewDecisionRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.review.decide(
                request.taskId,
                request.decision,
                request.comment,
                request.retryAction,
                request.reviewer,
            )
        )

    @app.post("/api/jobs/export-publish-package")
    def export_package(request: ExportPackageRequest) -> dict[str, Any]:
        return wrap(
            lambda: app.state.services.publish.export_package(request.taskId, request.platforms)
        )

    @app.post("/api/publish-records")
    def publish_record(request: PublishRecordRequest) -> dict[str, Any]:
        return wrap(lambda: app.state.services.publish.create_publish_record(request.model_dump()))

    @app.post("/api/control-plane/run-to-review-pending")
    def run_to_review_pending() -> dict[str, Any]:
        return wrap(lambda: app.state.services.control.run_to_review_pending())

    return app


GENERATE_PAGE = (Path(__file__).parent / "templates" / "generate.html").read_text(encoding="utf-8")

app = create_app()
