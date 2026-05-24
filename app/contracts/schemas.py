from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Candidate(BaseModel):
    repoFullName: str
    repoUrl: str
    description: str = ""
    language: str = ""
    topics: list[str] = Field(default_factory=list)
    stars: int = 0
    forks: int = 0
    todayStars: int = 0
    readmeText: str = ""
    readmeSummary: str = ""
    createdAt: str = ""
    updatedAt: str = ""
    license: str = ""
    source: str = "github_trending"
    collectedAt: str = ""
    score: float | None = None
    scoreBreakdown: dict[str, float] = Field(default_factory=dict)
    riskFlags: list[str] = Field(default_factory=list)
    recommendReason: str = ""
    valid: bool = True


class ScriptSegment(BaseModel):
    type: str
    durationSec: int = Field(gt=0)
    voiceText: str
    screenText: str
    visualHint: str
    emotion: str


class VideoScript(BaseModel):
    title: str
    coverText: str
    description: str
    hashtags: list[str]
    segments: list[ScriptSegment]
    cta: str

    @field_validator("title", "coverText", "description", "cta")
    @classmethod
    def non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("field must not be empty")
        return value


class SubtitleItem(BaseModel):
    text: str
    startMs: int
    endMs: int
    segmentIndex: int


class SubtitleDocument(BaseModel):
    taskId: str
    level: Literal["word", "phrase", "sentence"]
    items: list[SubtitleItem]


class AssetMetadata(BaseModel):
    durationSec: float | None = None
    width: int | None = None
    height: int | None = None
    fps: int | None = None
    videoCodec: str | None = None
    audioCodec: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class ScriptGenerationConfig(BaseModel):
    provider: Literal["local", "minimax", "deepseek"] = "local"
    model: str = "MiniMax-M2.7"
    systemPrompt: str = (
        "你是中文科技短视频编导。只输出严格 JSON，不要 markdown。"
        "所有讲稿、标题、封面、屏幕文字、简介和 CTA 必须是中文。"
    )
    userPromptTemplate: str = ""
    style: str = "code_ppt"
    durationSec: int = Field(default=75, ge=30, le=180)
    audience: str = "chinese_developers"
    temperature: float = Field(default=0.35, ge=0, le=2)
    topP: float | None = Field(default=None, ge=0, le=1)
    maxTokens: int | None = Field(default=4096, ge=256, le=16000)


class TTSPronunciation(BaseModel):
    source: str
    target: str


class TTSConfig(BaseModel):
    provider: Literal["mock", "minimax", "minimax_http", "edge_tts", "windows_sapi"] = "mock"
    model: str = "speech-2.8-hd"
    voiceId: str = "default_cn_tech"
    speed: float = Field(default=1.2, ge=0.5, le=2.0)
    volume: float = Field(default=1.0, ge=0, le=10)
    pitch: int = Field(default=0, ge=-12, le=12)
    format: Literal["mp3", "wav", "flac", "pcm"] = "mp3"
    sampleRate: int = Field(default=32000, ge=8000, le=48000)
    bitrate: int = Field(default=128000, ge=32000, le=320000)
    channels: Literal[1, 2] = 1
    language: str = "Chinese"
    subtitles: bool = False
    pronunciation: list[TTSPronunciation] = Field(default_factory=list)


class VisualConfig(BaseModel):
    theme: Literal["auto", "blue", "green", "amber"] = "auto"
    width: int = Field(default=1080, ge=720, le=2160)
    height: int = Field(default=1920, ge=1280, le=3840)
    fps: int = Field(default=30, ge=12, le=60)
    label: str = "GITHUB DAILY"
    sourceText: str = "素材来源：GitHub 公开信息 / README / 仓库元数据"
    showGrid: bool = True
    showSubtitlePanel: bool = True
    showStep: bool = True
    margin: int = Field(default=96, ge=24, le=220)
    outerMargin: int = Field(default=48, ge=0, le=160)
    outerRadius: int = Field(default=36, ge=0, le=80)
    panelRadius: int = Field(default=24, ge=0, le=80)
    cardRadius: int = Field(default=18, ge=0, le=60)
    chipRadius: int = Field(default=25, ge=0, le=60)
    titleSize: int = Field(default=62, ge=32, le=96)
    titleSizeCompact: int = Field(default=54, ge=28, le=88)
    summarySize: int = Field(default=42, ge=24, le=72)
    bodySize: int = Field(default=36, ge=20, le=64)
    smallSize: int = Field(default=30, ge=16, le=52)
    chipSize: int = Field(default=26, ge=14, le=44)
    bulletCount: int = Field(default=3, ge=0, le=6)
    bodyWrap: int = Field(default=18, ge=8, le=40)
    bulletWrap: int = Field(default=25, ge=8, le=48)
    subtitleWrap: int = Field(default=28, ge=10, le=56)
    subtitlePanelTop: int = Field(default=1288, ge=400, le=3000)
    subtitlePanelBottom: int = Field(default=1688, ge=600, le=3600)
    footerY: int = Field(default=1788, ge=600, le=3800)


class VideoGenerationConfig(BaseModel):
    scriptConfig: ScriptGenerationConfig = Field(default_factory=ScriptGenerationConfig)
    ttsConfig: TTSConfig = Field(default_factory=TTSConfig)
    visualConfig: VisualConfig = Field(default_factory=VisualConfig)


class VideoPresetPayload(VideoGenerationConfig):
    name: str = "默认模板"


def default_video_preset_payload() -> dict[str, Any]:
    return VideoPresetPayload().model_dump()
