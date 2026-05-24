from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Protocol, cast
from uuid import uuid4

from app.contracts.errors import AppError
from app.contracts.schemas import VisualConfig
from app.storage.object_store import LocalObjectStore
from app.storage.repository import SQLiteRepository


class RenderAdapter(Protocol):
    def render(
        self,
        task_id: str,
        script: dict[str, object],
        audio: bytes,
        subtitle: dict[str, object],
        visual_config: VisualConfig | None = None,
    ) -> dict[str, object]: ...


class FakeRenderAdapter:
    def render(
        self,
        task_id: str,
        script: dict[str, object],
        audio: bytes,
        subtitle: dict[str, object],
        visual_config: VisualConfig | None = None,
    ) -> dict[str, object]:
        config = visual_config or VisualConfig()
        timeline = _slide_timeline(script, subtitle)
        duration = _timeline_duration_sec(timeline)
        metadata = {
            "width": config.width,
            "height": config.height,
            "fps": config.fps,
            "durationSec": duration,
            "videoCodec": "H.264",
            "audioCodec": "AAC",
            "container": "MP4",
            "visualConfig": config.model_dump(),
        }
        subtitle_items = cast(list[object], subtitle.get("items", []))
        video_bytes, cover_bytes = _render_placeholder_media(audio, duration)
        return {
            "videoBytes": video_bytes,
            "coverBytes": cover_bytes,
            "metadata": metadata | {"subtitleItems": len(subtitle_items)},
        }


class FfmpegInfoRenderAdapter:
    def render(
        self,
        task_id: str,
        script: dict[str, object],
        audio: bytes,
        subtitle: dict[str, object],
        visual_config: VisualConfig | None = None,
    ) -> dict[str, object]:
        config = visual_config or VisualConfig()
        timeline = _slide_timeline(script, subtitle)
        duration = _timeline_duration_sec(timeline)
        video_bytes, cover_bytes = _render_info_template(script, audio, subtitle, timeline, config)
        return {
            "videoBytes": video_bytes,
            "coverBytes": cover_bytes,
            "metadata": {
                "width": config.width,
                "height": config.height,
                "fps": config.fps,
                "durationSec": duration,
                "videoCodec": "H.264",
                "audioCodec": "AAC",
                "container": "MP4",
                "subtitleItems": len(cast(list[object], subtitle.get("items", []))),
                "slideTimeline": timeline,
                "template": "github_light_cards_v1",
                "taskId": task_id,
                "visualConfig": config.model_dump(),
            },
        }


class RenderJobManager:
    def __init__(self) -> None:
        self.jobs: dict[str, dict[str, object]] = {}

    def create(self, task_id: str) -> str:
        render_job_id = f"render_{uuid4().hex[:8]}"
        self.jobs[render_job_id] = {
            "renderJobId": render_job_id,
            "taskId": task_id,
            "status": "rendering",
        }
        return render_job_id

    def complete(self, render_job_id: str, payload: dict[str, object]) -> None:
        self.jobs[render_job_id] = self.jobs[render_job_id] | payload | {"status": "rendered"}

    def get(self, render_job_id: str) -> dict[str, object]:
        if render_job_id not in self.jobs:
            raise AppError(
                "RENDER_JOB_NOT_FOUND",
                "Render job not found",
                False,
                {"renderJobId": render_job_id},
            )
        return self.jobs[render_job_id]


class VideoRenderingService:
    def __init__(
        self,
        repository: SQLiteRepository,
        object_store: LocalObjectStore,
        adapter: RenderAdapter | None = None,
        job_manager: RenderJobManager | None = None,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.adapter = adapter or FakeRenderAdapter()
        self.job_manager = job_manager or RenderJobManager()

    def render_video(
        self,
        task_id: str,
        template: str,
        script_url: str,
        audio_url: str,
        subtitle_url: str,
        visual_config: VisualConfig | None = None,
    ) -> dict[str, object]:
        try:
            script = self._load_json(script_url, "RENDER_SCRIPT_MISSING")
            subtitle = self._load_json(subtitle_url, "RENDER_SUBTITLE_MISSING")
            audio_path = self.object_store.path_from_url(audio_url)
            if not audio_path.exists():
                raise AppError(
                    "RENDER_AUDIO_MISSING",
                    "Audio file is not accessible",
                    True,
                    {"audioUrl": audio_url},
                )
            render_job_id = self.job_manager.create(task_id)
            rendered = self.adapter.render(
                task_id, script, audio_path.read_bytes(), subtitle, visual_config
            )
            video_bytes = cast(bytes, rendered["videoBytes"])
            cover_bytes = cast(bytes, rendered["coverBytes"])
            metadata = cast(dict[str, object], rendered["metadata"])
            video = self.object_store.write_bytes("videos", ".mp4", video_bytes)
            cover = self.object_store.write_bytes("covers", ".png", cover_bytes)
            video_asset = self.repository.add_asset(
                task_id,
                "video",
                str(video["url"]),
                "video/mp4",
                int(video["sizeBytes"]),
                str(video["checksum"]),
                metadata,
            )
            cover_asset = self.repository.add_asset(
                task_id,
                "cover",
                str(cover["url"]),
                "image/png",
                int(cover["sizeBytes"]),
                str(cover["checksum"]),
                {"template": template},
            )
            completion = {
                "renderJobId": render_job_id,
                "taskId": task_id,
                "status": "rendered",
                "videoUrl": video_asset["url"],
                "coverUrl": cover_asset["url"],
                "metadata": metadata,
                "videoAssetId": video_asset["assetId"],
                "coverAssetId": cover_asset["assetId"],
            }
            self.job_manager.complete(render_job_id, completion)
            self.repository.add_run_log(
                "video_rendering", "render_video", True, task_id=task_id, artifact_refs=completion
            )
            return {"renderJobId": render_job_id, "status": "rendering", "result": completion}
        except AppError as exc:
            self.repository.fail_task(task_id, "video_rendering", exc)
            raise

    def get_render_job(self, render_job_id: str) -> dict[str, object]:
        return self.job_manager.get(render_job_id)

    def _load_json(self, url: str, error_code: str) -> dict[str, object]:
        path = self.object_store.path_from_url(url)
        if not path.exists():
            raise AppError(error_code, "Render input file is not accessible", True, {"url": url})
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise AppError(error_code, "Render input JSON is not an object", True, {"url": url})
        return cast(dict[str, object], payload)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    if isinstance(value, float):
        return int(value)
    return 0


def _float_value(value: object) -> float:
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        return float(value)
    return 0.0


def _slide_timeline(
    script: dict[str, object], subtitle: dict[str, object]
) -> list[dict[str, object]]:
    raw_timeline = subtitle.get("slideTimeline")
    if isinstance(raw_timeline, list) and raw_timeline:
        return [
            {
                "slideIndex": _int_value(item.get("slideIndex", index))
                if isinstance(item, dict)
                else index,
                "segmentIndex": _int_value(item.get("segmentIndex", index))
                if isinstance(item, dict)
                else index,
                "startMs": _int_value(item.get("startMs", 0)) if isinstance(item, dict) else 0,
                "endMs": _int_value(item.get("endMs", 0)) if isinstance(item, dict) else 0,
                "audioDurationMs": _int_value(item.get("audioDurationMs", 0))
                if isinstance(item, dict)
                else 0,
                "visualDurationMs": _int_value(item.get("visualDurationMs", 0))
                if isinstance(item, dict)
                else 0,
                "transitionDurationMs": _int_value(item.get("transitionDurationMs", 0))
                if isinstance(item, dict)
                else 0,
                "totalVisualDurationMs": _int_value(item.get("totalVisualDurationMs", 0))
                if isinstance(item, dict)
                else 0,
                "textLength": _int_value(item.get("textLength", 0))
                if isinstance(item, dict)
                else 0,
            }
            for index, item in enumerate(raw_timeline)
        ]
    items = cast(list[dict[str, object]], subtitle.get("items", []))
    if items:
        timeline: list[dict[str, object]] = []
        for index, item in enumerate(items):
            start_ms = _int_value(item.get("startMs", 0))
            end_ms = _int_value(item.get("endMs", start_ms))
            duration_ms = max(1, end_ms - start_ms)
            timeline.append(
                {
                    "slideIndex": index,
                    "segmentIndex": _int_value(item.get("segmentIndex", index)),
                    "startMs": start_ms,
                    "endMs": end_ms,
                    "audioDurationMs": duration_ms,
                    "visualDurationMs": duration_ms,
                    "transitionDurationMs": 0,
                    "totalVisualDurationMs": duration_ms,
                    "textLength": len(str(item.get("text", ""))),
                }
            )
        return timeline
    segments = cast(list[dict[str, object]], script.get("segments", []))
    cursor = 0
    timeline = []
    for index, segment in enumerate(segments):
        duration_ms = max(1, _int_value(segment.get("durationSec", 1)) * 1000)
        timeline.append(
            {
                "slideIndex": index,
                "segmentIndex": index,
                "startMs": cursor,
                "endMs": cursor + duration_ms,
                "audioDurationMs": duration_ms,
                "visualDurationMs": duration_ms,
                "transitionDurationMs": 0,
                "totalVisualDurationMs": duration_ms,
                "textLength": len(str(segment.get("voiceText", ""))),
            }
        )
        cursor += duration_ms
    return timeline or [
        {
            "slideIndex": 0,
            "segmentIndex": 0,
            "startMs": 0,
            "endMs": 60_000,
            "audioDurationMs": 60_000,
            "visualDurationMs": 60_000,
            "transitionDurationMs": 0,
            "totalVisualDurationMs": 60_000,
            "textLength": 0,
        }
    ]


def _timeline_duration_sec(timeline: list[dict[str, object]]) -> float:
    total_ms = sum(_int_value(item.get("totalVisualDurationMs", 0)) for item in timeline)
    if total_ms <= 0:
        total_ms = sum(_int_value(item.get("audioDurationMs", 0)) for item in timeline)
    return round(total_ms / 1000, 3)


def _render_placeholder_media(audio: bytes, duration: float) -> tuple[bytes, bytes]:
    tmp_path = _render_work_dir()
    try:
        audio_path = tmp_path / "audio.wav"
        video_path = tmp_path / "video.mp4"
        cover_path = tmp_path / "cover.png"
        audio_path.write_bytes(audio)
        common_flags = ["-hide_banner", "-loglevel", "error", "-y"]
        video_cmd = [
            "ffmpeg",
            *common_flags,
            "-f",
            "lavfi",
            "-i",
            "color=c=0x101827:s=1080x1920:r=30",
            "-i",
            str(audio_path),
            "-t",
            str(duration),
            "-shortest",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video_path),
        ]
        cover_cmd = [
            "ffmpeg",
            *common_flags,
            "-f",
            "lavfi",
            "-i",
            "color=c=0x101827:s=1080x1920",
            "-frames:v",
            "1",
            str(cover_path),
        ]
        try:
            subprocess.run(video_cmd, check=True, capture_output=True)
            subprocess.run(cover_cmd, check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise AppError(
                "FFMPEG_PLACEHOLDER_RENDER_FAILED",
                "FFmpeg is required to create openable placeholder media",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        return video_path.read_bytes(), cover_path.read_bytes()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def _render_info_template(
    script: dict[str, object],
    audio: bytes,
    subtitle: dict[str, object],
    timeline: list[dict[str, object]],
    visual_config: VisualConfig,
) -> tuple[bytes, bytes]:
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise AppError(
            "PILLOW_REQUIRED",
            "Pillow is required for the FFmpeg information template",
            True,
            {},
        ) from exc

    width, height = visual_config.width, visual_config.height
    title = str(script.get("title", "GitHub 今日推荐"))
    cover_text = str(script.get("coverText", title))
    description = str(script.get("description", ""))
    cta = str(script.get("cta", "打开 GitHub 链接，查看 README 和示例。"))
    segments = cast(list[dict[str, object]], script.get("segments", []))
    subtitle_items = cast(list[dict[str, object]], subtitle.get("items", []))
    slides = _build_slides(
        title, cover_text, description, cta, segments, subtitle_items, timeline, visual_config
    )
    duration = _timeline_duration_sec(timeline)

    tmp_path = _render_work_dir()
    try:
        slide_paths: list[Path] = []
        for index, slide in enumerate(slides):
            path = tmp_path / f"slide_{index}.png"
            _write_slide(path, width, height, slide, Image, ImageDraw, ImageFont, visual_config)
            slide_paths.append(path)
        concat_path = tmp_path / "slides.txt"
        with concat_path.open("w", encoding="utf-8") as file:
            for path, slide in zip(slide_paths, slides, strict=True):
                file.write(f"file '{path.as_posix()}'\n")
                file.write(f"duration {slide['durationSec']}\n")
            file.write(f"file '{slide_paths[-1].as_posix()}'\n")

        audio_path = tmp_path / "audio.mp3"
        video_path = tmp_path / "video.mp4"
        cover_path = tmp_path / "cover.png"
        audio_path.write_bytes(audio)
        cover_path.write_bytes(slide_paths[0].read_bytes())
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_path),
            "-i",
            str(audio_path),
            "-t",
            str(duration),
            "-vf",
            f"fps={visual_config.fps}",
            "-r",
            str(visual_config.fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(video_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)
        except (FileNotFoundError, subprocess.CalledProcessError) as exc:
            raise AppError(
                "FFMPEG_TEMPLATE_RENDER_FAILED",
                "FFmpeg information template render failed",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        return video_path.read_bytes(), cover_path.read_bytes()
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def _write_slide(
    path: Path,
    width: int,
    height: int,
    slide: dict[str, object],
    image_module: Any,
    draw_module: Any,
    font_module: Any,
    visual_config: VisualConfig,
) -> None:
    palette = cast(dict[str, tuple[int, int, int]], slide["palette"])
    image = image_module.new("RGB", (width, height), palette["background"])
    draw = draw_module.Draw(image)
    font_path = _font_path()
    title_size = (
        visual_config.titleSize
        if len(str(slide["heading"])) <= 18
        else visual_config.titleSizeCompact
    )
    title_font = _font(font_module, font_path, title_size)
    summary_font = _font(font_module, font_path, visual_config.summarySize)
    body_font = _font(font_module, font_path, visual_config.bodySize)
    small_font = _font(font_module, font_path, visual_config.smallSize)
    chip_font = _font(font_module, font_path, visual_config.chipSize)

    heading = str(slide["heading"])
    body = str(slide["body"])
    footnote = str(slide.get("footnote", ""))
    subtitle_text = str(slide.get("subtitle", ""))
    label = visual_config.label or str(slide.get("label", "GITHUB DAILY"))
    step = str(slide.get("step", "")) if visual_config.showStep else ""
    bullets = cast(list[str], slide.get("bullets", []))

    left = visual_config.margin
    right = width - visual_config.margin
    bottom_safe = height - 112
    if visual_config.showGrid:
        _draw_soft_grid(draw, width, height, palette)
    outer = visual_config.outerMargin
    draw.rounded_rectangle(
        (outer, outer, width - outer, height - outer),
        radius=visual_config.outerRadius,
        fill=palette["surface"],
    )

    draw.rounded_rectangle(
        (left, 92, left + 224, 142), radius=visual_config.chipRadius, fill=palette["chip"]
    )
    draw.text((left + 24, 103), label[:14], fill=palette["accent"], font=chip_font)
    if step:
        draw.text((right - 56, 104), step, fill=palette["muted"], font=chip_font)

    y = 190
    for line in _wrap_heading(heading)[:2]:
        draw.text((left, y), line, fill=palette["heading"], font=title_font)
        y += title_size + 18
    draw.line((left, y + 16, right, y + 16), fill=palette["rule"], width=3)

    y += 64
    for line in _wrap_text(body, visual_config.bodyWrap)[:3]:
        draw.text((left, y), line, fill=palette["text"], font=summary_font)
        y += 58

    card_y = max(560, y + 28)
    for bullet in bullets[: visual_config.bulletCount]:
        card_bottom = card_y + 104
        draw.rounded_rectangle(
            (left, card_y, right, card_bottom), radius=visual_config.cardRadius, fill=palette["panel"]
        )
        draw.ellipse((left + 28, card_y + 40, left + 50, card_y + 62), fill=palette["accent"])
        for line_index, line in enumerate(_wrap_text(bullet, visual_config.bulletWrap)[:2]):
            draw.text(
                (left + 78, card_y + 26 + line_index * 39),
                line,
                fill=palette["text"],
                font=body_font,
            )
        card_y += 124

    if footnote:
        draw.text(
            (left, card_y + 22),
            _wrap_text(footnote, 24)[0],
            fill=palette["accent"],
            font=body_font,
        )

    if visual_config.showSubtitlePanel:
        panel_top = min(visual_config.subtitlePanelTop, bottom_safe - 160)
        panel_bottom = min(visual_config.subtitlePanelBottom, bottom_safe - 72)
        panel_bottom = max(panel_bottom, panel_top + 120)
        draw.rounded_rectangle(
            (left, panel_top, right, panel_bottom),
            radius=visual_config.panelRadius,
            fill=palette["subtitle_panel"],
        )
        subtitle_lines = _wrap_text(subtitle_text, visual_config.subtitleWrap)
        subtitle_font = small_font
        line_step = max(32, visual_config.smallSize + 16)
        max_lines = max(1, (panel_bottom - panel_top - 72) // line_step)
        if len(subtitle_lines) > max_lines:
            subtitle_font = _font(font_module, font_path, max(18, visual_config.smallSize - 4))
            line_step = max(28, visual_config.smallSize + 10)
            max_lines = max(1, (panel_bottom - panel_top - 56) // line_step)
        subtitle_y = panel_top + 34
        for line in subtitle_lines[:max_lines]:
            draw.text((left + 34, subtitle_y), line, fill=palette["subtitle"], font=subtitle_font)
            subtitle_y += line_step
    draw.text(
        (left, visual_config.footerY),
        "素材来源：GitHub 公开信息 / README / 仓库元数据",
        fill=palette["muted"],
        font=small_font,
    )
    if visual_config.sourceText:
        draw.rectangle(
            (left, visual_config.footerY, right, visual_config.footerY + visual_config.smallSize + 12),
            fill=palette["surface"],
        )
        draw.text(
            (left, visual_config.footerY),
            visual_config.sourceText,
            fill=palette["muted"],
            font=small_font,
        )
    image.save(path)


def _font(font_module: Any, font_path: str | None, size: int) -> Any:
    return font_module.truetype(font_path, size) if font_path else font_module.load_default()


def _font_path() -> str | None:
    for path in [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]:
        if Path(path).exists():
            return path
    return None


def _wrap_text(text: str, width: int) -> list[str]:
    normalized = text.replace("\n", " ").strip()
    if not normalized:
        return [""]
    if " " not in normalized:
        return [normalized[index : index + width] for index in range(0, len(normalized), width)]
    words = normalized.split()
    lines: list[str] = []
    current = ""
    for word in words:
        parts = (
            [word[index : index + width] for index in range(0, len(word), width)]
            if len(word) > width
            else [word]
        )
        for part in parts:
            candidate = f"{current} {part}".strip()
            if len(candidate) > width and current:
                lines.append(current)
                current = part
            else:
                current = candidate
    if current:
        lines.append(current)
    return lines


def _wrap_heading(text: str) -> list[str]:
    normalized = text.replace("\n", " ").strip()
    if "：" in normalized and len(normalized) > 16:
        prefix, suffix = normalized.split("：", 1)
        suffix = suffix.strip()
        if suffix:
            return [f"{prefix}：", suffix]
    return _wrap_text(normalized, 18)


def _build_slides(
    title: str,
    cover_text: str,
    description: str,
    cta: str,
    segments: list[dict[str, object]],
    subtitle_items: list[dict[str, object]],
    timeline: list[dict[str, object]],
    visual_config: VisualConfig,
) -> list[dict[str, object]]:
    palettes = [
        {
            "background": (239, 246, 255),
            "surface": (255, 255, 255),
            "panel": (248, 250, 252),
            "subtitle_panel": (15, 23, 42),
            "chip": (219, 234, 254),
            "rule": (219, 234, 254),
            "accent": (37, 99, 235),
            "heading": (15, 23, 42),
            "text": (30, 41, 59),
            "subtitle": (248, 250, 252),
            "muted": (100, 116, 139),
        },
        {
            "background": (236, 253, 245),
            "surface": (255, 255, 255),
            "panel": (240, 253, 250),
            "subtitle_panel": (20, 83, 45),
            "chip": (204, 251, 241),
            "rule": (204, 251, 241),
            "accent": (13, 148, 136),
            "heading": (15, 23, 42),
            "text": (30, 41, 59),
            "subtitle": (248, 250, 252),
            "muted": (71, 85, 105),
        },
        {
            "background": (255, 251, 235),
            "surface": (255, 255, 255),
            "panel": (255, 247, 237),
            "subtitle_panel": (120, 53, 15),
            "chip": (254, 243, 199),
            "rule": (254, 215, 170),
            "accent": (217, 119, 6),
            "heading": (15, 23, 42),
            "text": (41, 37, 36),
            "subtitle": (255, 251, 235),
            "muted": (120, 113, 108),
        },
    ]
    selected_palettes = _select_palettes(palettes, visual_config.theme)
    if not segments:
        duration = _timeline_duration_sec(timeline)
        return [
            {
                "heading": cover_text or title,
                "body": description or title,
                "subtitle": cta,
                "footnote": title,
                "label": visual_config.label,
                "step": "01",
                "bullets": _bullet_points(description or title),
                "durationSec": duration,
                "palette": selected_palettes[0],
            }
        ]

    headings = ["项目看点", "核心能力", "使用场景", "上手建议", "风险提醒", "下一步"]
    slides: list[dict[str, object]] = []
    for index, item in enumerate(timeline):
        segment_index = min(_int_value(item.get("segmentIndex", index)), len(segments) - 1)
        segment = segments[segment_index]
        screen_text = str(segment.get("screenText") or segment.get("voiceText") or "")
        voice_text = _subtitle_for_segment(subtitle_items, segment_index) or str(
            segment.get("voiceText") or ""
        )
        heading = headings[min(segment_index, len(headings) - 1)]
        if index == 0:
            heading = cover_text or heading
        footnote = title if index == 0 else ""
        if index == len(timeline) - 1:
            footnote = cta
        duration_sec = (
            _int_value(item.get("totalVisualDurationMs", 0))
            or _int_value(item.get("visualDurationMs", 0))
            or _int_value(item.get("audioDurationMs", 0))
        ) / 1000
        slides.append(
            {
                "heading": heading,
                "body": screen_text,
                "subtitle": voice_text,
                "footnote": footnote,
                "label": visual_config.label,
                "step": f"{index + 1:02}",
                "bullets": _bullet_points(screen_text),
                "durationSec": max(0.001, duration_sec),
                "palette": selected_palettes[index % len(selected_palettes)],
            }
        )
    return slides


def _select_palettes(
    palettes: list[dict[str, tuple[int, int, int]]], theme: str
) -> list[dict[str, tuple[int, int, int]]]:
    theme_index = {"blue": 0, "green": 1, "amber": 2}.get(theme)
    if theme_index is None:
        return palettes
    return [palettes[theme_index]]


def _subtitle_for_segment(items: list[dict[str, object]], segment_index: int) -> str:
    parts = [
        str(item.get("text", "")).strip()
        for item in items
        if _int_value(item.get("segmentIndex", 0)) == segment_index
        and str(item.get("text", "")).strip()
    ]
    return " ".join(parts[:8])


def _bullet_points(text: str) -> list[str]:
    defaults = ["基于公开仓库信息", "适合先收藏再评估", "查看 README 获取细节"]
    if len(text.strip()) < 12:
        return defaults
    lines = [line.strip(" -，。") for line in _wrap_text(text, 18) if line.strip()]
    if len(lines) >= 3:
        return lines[:3]
    return (lines + defaults)[:3]


def _draw_soft_grid(
    draw: Any, width: int, height: int, palette: dict[str, tuple[int, int, int]]
) -> None:
    for x in range(0, width, 90):
        draw.line((x, 0, x, height), fill=palette["rule"], width=1)
    for y in range(0, height, 90):
        draw.line((0, y, width, y), fill=palette["rule"], width=1)


def _render_work_dir() -> Path:
    root = Path("data/render_tmp")
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"render_{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    return path.resolve()
