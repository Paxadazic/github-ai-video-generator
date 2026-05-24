from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Protocol
from uuid import uuid4

from pydantic import ValidationError

from app.contracts.errors import AppError
from app.contracts.schemas import Candidate, ScriptGenerationConfig, VideoScript
from app.minimax_cli import MiniMaxCliRunner
from app.storage.object_store import LocalObjectStore
from app.storage.repository import SQLiteRepository


class ModelAdapter(Protocol):
    def generate(self, prompt: str, config: ScriptGenerationConfig | None = None) -> str: ...

    def repair(
        self, invalid_output: str, error: str, config: ScriptGenerationConfig | None = None
    ) -> str: ...


class MockModelAdapter:
    def __init__(self, outputs: list[str] | None = None) -> None:
        self.outputs = outputs or []
        self.calls = 0

    def generate(self, prompt: str, config: ScriptGenerationConfig | None = None) -> str:
        self.calls += 1
        if self.outputs:
            return self.outputs.pop(0)
        repo_name = "project"
        if "repoFullName=" in prompt:
            repo_name = prompt.split("repoFullName=", 1)[1].split("\n", 1)[0]
        return json.dumps(default_script_payload(repo_name), ensure_ascii=False)

    def repair(
        self, invalid_output: str, error: str, config: ScriptGenerationConfig | None = None
    ) -> str:
        if self.outputs:
            return self.outputs.pop(0)
        return json.dumps(default_script_payload("repaired/project"), ensure_ascii=False)


class DeepSeekModelAdapter:
    def __init__(self, api_key: str | None, model: str = "deepseek-v4-flash") -> None:
        self.api_key = api_key
        self.model = model

    def generate(self, prompt: str, config: ScriptGenerationConfig | None = None) -> str:
        if not self.api_key:
            raise AppError(
                "DEEPSEEK_API_KEY_MISSING", "DeepSeek API key is not configured", True, {}
            )
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是中文科技短视频编导。只输出严格 JSON，不要 markdown。"
                        "所有讲稿、标题、封面、PPT 屏幕文字、简介和 CTA 必须是中文。"
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.35,
            "response_format": {"type": "json_object"},
        }
        if config:
            payload["model"] = config.model if config.provider == "deepseek" else self.model
            payload["messages"][0] = {"role": "system", "content": config.systemPrompt}
            payload["temperature"] = config.temperature
            if config.topP is not None:
                payload["top_p"] = config.topP
            if config.maxTokens is not None:
                payload["max_tokens"] = config.maxTokens
        request = urllib.request.Request(
            "https://api.deepseek.com/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise AppError(
                "DEEPSEEK_REQUEST_FAILED",
                "DeepSeek request failed",
                True,
                {"reason": exc.__class__.__name__},
            ) from exc
        return self._extract_content(raw)

    def repair(
        self, invalid_output: str, error: str, config: ScriptGenerationConfig | None = None
    ) -> str:
        return self.generate(
            "只修复为合法 JSON，并保持全中文。"
            f"错误：{error}\n原始输出：\n{invalid_output}"
            ,
            config,
        )

    def _extract_content(self, raw: object) -> str:
        if not isinstance(raw, dict):
            raise AppError("DEEPSEEK_RESPONSE_INVALID", "DeepSeek response was invalid", True, {})
        choices = raw.get("choices")
        if not isinstance(choices, list) or not choices:
            raise AppError("DEEPSEEK_RESPONSE_INVALID", "DeepSeek returned no choices", True, {})
        first = choices[0]
        if not isinstance(first, dict):
            raise AppError("DEEPSEEK_RESPONSE_INVALID", "DeepSeek choice was invalid", True, {})
        message = first.get("message")
        if not isinstance(message, dict):
            raise AppError("DEEPSEEK_RESPONSE_INVALID", "DeepSeek message was invalid", True, {})
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise AppError("DEEPSEEK_RESPONSE_INVALID", "DeepSeek content was empty", True, {})
        return content


class MiniMaxCliModelAdapter:
    def __init__(
        self,
        runner: MiniMaxCliRunner | None = None,
        model: str = "MiniMax-M2.7",
        timeout: float = 180,
    ) -> None:
        self.runner = runner or MiniMaxCliRunner()
        self.model = model
        self.timeout = timeout

    def generate(self, prompt: str, config: ScriptGenerationConfig | None = None) -> str:
        model = config.model if config and config.provider == "minimax" else self.model
        command = ["text", "chat", "--model", model, "--message", prompt]
        if config and config.systemPrompt:
            command.extend(["--system", config.systemPrompt])
        if config and config.maxTokens is not None:
            command.extend(["--max-tokens", str(config.maxTokens)])
        if config:
            command.extend(["--temperature", str(config.temperature)])
        if config and config.topP is not None:
            command.extend(["--top-p", str(config.topP)])
        raw = self.runner.run_json(
            command,
            timeout=self.timeout,
        )
        return self._extract_assistant_content(raw)

    def repair(
        self, invalid_output: str, error: str, config: ScriptGenerationConfig | None = None
    ) -> str:
        return self.generate(
            "Return only valid JSON. Keep the original content language and fix the schema error.\n"
            f"Error: {error}\nInvalid output:\n{invalid_output}"
            ,
            config,
        )

    def _extract_assistant_content(self, raw: object) -> str:
        content = self._find_content(raw)
        if content is None or not content.strip():
            raise AppError(
                "MINIMAX_CLI_RESPONSE_INVALID",
                "MiniMax CLI response did not include assistant content",
                True,
                {"model": self.model, "region": self.runner.region},
            )
        return content

    def _find_content(self, raw: object) -> str | None:
        if isinstance(raw, dict):
            choices = raw.get("choices")
            if isinstance(choices, list) and choices:
                choice_content = self._find_content(choices[0])
                if choice_content:
                    return choice_content
            message = raw.get("message")
            if isinstance(message, dict):
                message_content = message.get("content")
                if isinstance(message_content, str):
                    return message_content
            messages = raw.get("messages")
            if isinstance(messages, list):
                for item in reversed(messages):
                    if isinstance(item, dict) and item.get("role") == "assistant":
                        assistant_content = item.get("content")
                        if isinstance(assistant_content, str):
                            return assistant_content
            for key in ("content", "text", "output"):
                value = raw.get(key)
                if isinstance(value, str):
                    return value
            for key in ("data", "result", "response"):
                nested = raw.get(key)
                nested_content = self._find_content(nested)
                if nested_content:
                    return nested_content
        return None


class ProjectContextBuilder:
    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    def build(self, repo_full_name: str) -> Candidate:
        candidate = self.repository.get_candidate(repo_full_name)
        if candidate is None:
            raise AppError(
                "CANDIDATE_NOT_FOUND",
                "Candidate metadata not found",
                False,
                {"repoFullName": repo_full_name},
            )
        return candidate


class FactGuard:
    banned_claims = [
        "融资",
        "官方背书",
        "性能提升",
        "百万用户",
        "商业合作",
        "verified performance",
    ]

    def check(self, script: VideoScript, candidate: Candidate) -> None:
        text = json.dumps(script.model_dump(), ensure_ascii=False)
        source = json.dumps(candidate.model_dump(), ensure_ascii=False)
        for claim in self.banned_claims:
            if claim in text and claim not in source:
                raise AppError(
                    "UNSUPPORTED_FACT_CLAIM",
                    "Script contains facts not present in metadata or README",
                    False,
                    {"claim": claim, "repoFullName": candidate.repoFullName},
                )


class ScriptSchemaValidator:
    def validate(self, payload: object) -> VideoScript:
        return VideoScript.model_validate(payload)


class ContentGenerationService:
    def __init__(
        self,
        repository: SQLiteRepository,
        object_store: LocalObjectStore,
        model_adapter: ModelAdapter | None = None,
    ) -> None:
        self.repository = repository
        self.object_store = object_store
        self.model_adapter = model_adapter or MockModelAdapter()
        self.context_builder = ProjectContextBuilder(repository)
        self.validator = ScriptSchemaValidator()
        self.fact_guard = FactGuard()

    def generate_script(
        self,
        repo_full_name: str,
        style: str = "code_ppt",
        duration_sec: int = 75,
        audience: str = "chinese_developers",
        task_id: str | None = None,
        config: ScriptGenerationConfig | None = None,
    ) -> dict[str, object]:
        effective_config = config or ScriptGenerationConfig(
            style=style, durationSec=duration_sec, audience=audience
        )
        candidate = self.context_builder.build(repo_full_name)
        last_error = "unknown"
        output = ""
        attempt_errors: list[dict[str, object]] = []
        blocked_by_fact_guard = False
        for attempt in range(3):
            try:
                prompt = self._prompt(candidate, effective_config)
                output = (
                    self.model_adapter.generate(prompt, effective_config)
                    if attempt == 0
                    else self.model_adapter.repair(output, last_error, effective_config)
                )
                payload = json.loads(output)
                script = self.validator.validate(payload)
                self.fact_guard.check(script, candidate)
                asset = self._write_script_asset(script, task_id, effective_config)
                self.repository.add_run_log(
                    "content_generation",
                    "generate_script",
                    True,
                    task_id=task_id,
                    artifact_refs={"assetId": asset["assetId"]},
                )
                return {
                    "jobId": f"script_{uuid4().hex[:8]}",
                    "script": script.model_dump(),
                    "scriptAssetId": asset["assetId"],
                    "scriptUrl": asset["url"],
                }
            except (json.JSONDecodeError, ValidationError, AppError) as exc:
                last_error = str(exc)
                if isinstance(exc, AppError) and exc.code == "UNSUPPORTED_FACT_CLAIM":
                    blocked_by_fact_guard = True
                attempt_errors.append(
                    {
                        "attempt": attempt + 1,
                        "errorType": exc.__class__.__name__,
                        "code": exc.code if isinstance(exc, AppError) else None,
                        "message": str(exc)[:500],
                        "outputPreview": output[:500],
                    }
                )
        if not blocked_by_fact_guard:
            script = self._fallback_script(candidate)
            asset = self._write_script_asset(script, task_id, effective_config)
            self.repository.add_run_log(
                "content_generation",
                "generate_script_fallback",
                True,
                task_id=task_id,
                artifact_refs={"assetId": asset["assetId"], "attemptErrors": attempt_errors},
            )
            return {
                "jobId": f"script_{uuid4().hex[:8]}",
                "script": script.model_dump(),
                "scriptAssetId": asset["assetId"],
                "scriptUrl": asset["url"],
                "fallbackUsed": True,
                "attemptErrors": attempt_errors,
            }
        error = AppError(
            "SCRIPT_GENERATION_FAILED",
            "Script generation failed after retries",
            True,
            {"attemptErrors": attempt_errors},
        )
        if task_id:
            self.repository.fail_task(task_id, "content_generation", error)
        raise error

    def _fallback_script(self, candidate: Candidate) -> VideoScript:
        payload = default_script_payload(candidate.repoFullName)
        project = candidate.repoFullName.split("/")[-1]
        description = (
            candidate.description or candidate.readmeSummary or "一个值得技术评估的开源项目。"
        )
        reason = candidate.recommendReason or "它在近期的 GitHub 趋势中值得关注。"
        payload["title"] = f"GitHub 今日项目：{project}"
        payload["coverText"] = f"{project} 值得看"
        payload["description"] = f"{candidate.repoFullName}：{description}"
        payload["segments"] = [
            {
                "type": "hook",
                "durationSec": 20,
                "voiceText": (
                    f"今天关注 {candidate.repoFullName}。"
                    f"它的核心信息是：{description[:90]}"
                ),
                "screenText": f"{project}：今日开源关注",
                "visualHint": "展示仓库名称、语言、Star 和 README 摘要。",
                "emotion": "confident",
            },
            {
                "type": "value",
                "durationSec": 25,
                "voiceText": (
                    f"推荐理由是：{reason[:110]}"
                    "这类项目适合先阅读 README，再判断是否放进自己的工具链。"
                ),
                "screenText": "先看场景，再评估价值",
                "visualHint": "展示推荐理由和仓库元数据。",
                "emotion": "calm",
            },
            {
                "type": "cta",
                "durationSec": 20,
                "voiceText": (
                    "如果这个方向正好匹配你的需求，可以打开 GitHub 链接继续看安装方式、"
                    "许可证和维护活跃度。"
                ),
                "screenText": "打开 GitHub 继续核对",
                "visualHint": "展示项目链接、许可证和更新时间。",
                "emotion": "calm",
            },
        ]
        script = self.validator.validate(payload)
        self.fact_guard.check(script, candidate)
        return script

    def _write_script_asset(
        self,
        script: VideoScript,
        task_id: str | None,
        config: ScriptGenerationConfig | None = None,
    ) -> dict[str, object]:
        if task_id is None:
            task_id = f"script_only_{uuid4().hex[:8]}"
        written = self.object_store.write_json("scripts", script.model_dump())
        return self.repository.add_asset(
            task_id,
            "script",
            str(written["url"]),
            "application/json",
            int(written["sizeBytes"]),
            str(written["checksum"]),
            {
                "title": script.title,
                "durationSec": sum(s.durationSec for s in script.segments),
                "scriptConfig": config.model_dump() if config else {},
            },
        )

    def _prompt(self, candidate: Candidate, config: ScriptGenerationConfig) -> str:
        if config.userPromptTemplate.strip():
            return _render_prompt_template(config.userPromptTemplate, candidate, config)
        return (
            "请只返回严格 JSON，字段必须包含 title、coverText、description、hashtags、"
            "segments、cta。\n"
            "每个 segment 必须包含 type、durationSec、voiceText、screenText、visualHint、"
            "emotion。\n"
            "所有内容必须使用中文，尤其是 voiceText 和 screenText。\n"
            "前 3 秒必须直接给出钩子，不要使用“大家好，今天介绍”。\n"
            "只能基于仓库元数据、README 摘要和推荐理由，不要编造融资、官方背书、"
            "用户规模、性能指标或未验证能力。\n"
            "screenText 要像竖屏 PPT 文案，短、清楚、适合直接放到画面上。\n"
            "voiceText 要口语化，但不要夸张营销。\n"
            "目标是一条 60-90 秒的竖屏 PPT 风格中文推荐视频。\n"
            f"repoFullName={candidate.repoFullName}\n"
            f"repoUrl={candidate.repoUrl}\n"
            f"description={candidate.description}\n"
            f"language={candidate.language}\n"
            f"topics={','.join(candidate.topics)}\n"
            f"stars={candidate.stars}; forks={candidate.forks}; todayStars={candidate.todayStars}\n"
            f"readmeSummary={candidate.readmeSummary or candidate.readmeText[:800]}\n"
            f"recommendReason={candidate.recommendReason}\n"
            f"style={config.style}; durationSec={config.durationSec}; audience={config.audience}\n"
        )


class _SafeFormatDict(dict[str, object]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _render_prompt_template(
    template: str, candidate: Candidate, config: ScriptGenerationConfig
) -> str:
    context = _SafeFormatDict(
        repoFullName=candidate.repoFullName,
        repoUrl=candidate.repoUrl,
        description=candidate.description,
        language=candidate.language,
        topics=",".join(candidate.topics),
        stars=candidate.stars,
        forks=candidate.forks,
        todayStars=candidate.todayStars,
        readmeSummary=candidate.readmeSummary or candidate.readmeText[:800],
        recommendReason=candidate.recommendReason,
        style=config.style,
        durationSec=config.durationSec,
        audience=config.audience,
    )
    return template.format_map(context)


def default_script_payload(repo_full_name: str) -> dict[str, object]:
    project = repo_full_name.split("/")[-1]
    return {
        "title": f"GitHub 今日项目：{project}",
        "coverText": f"今天值得看的开源项目：{project}",
        "description": f"用一分钟了解 {repo_full_name} 这个 GitHub 热门项目。",
        "hashtags": ["GitHub", "开源项目", "开发者工具"],
        "segments": [
            {
                "type": "hook",
                "durationSec": 20,
                "voiceText": (
                    f"{repo_full_name} 今天在 GitHub 上值得关注。"
                    "它瞄准的是开发者工作流里的一个具体问题，适合先收藏再评估。"
                ),
                "screenText": f"{project} 正在升温",
                "visualHint": "展示仓库卡片、语言、Star 和今日热度。",
                "emotion": "excited",
            },
            {
                "type": "value",
                "durationSec": 25,
                "voiceText": (
                    "从 README 和仓库元数据看，它更适合想提升效率、"
                    "尝试 AI 或自动化工具的开发者先做技术调研。"
                ),
                "screenText": "适合开发者先收藏评估",
                "visualHint": "展示 README 摘要和核心使用场景。",
                "emotion": "confident",
            },
            {
                "type": "cta",
                "durationSec": 20,
                "voiceText": (
                    "如果你正在找新的开源工具，可以先打开 GitHub 链接看看 README，"
                    "再决定要不要放进自己的技术栈。"
                ),
                "screenText": "先看 README，再决定是否尝试",
                "visualHint": "展示项目链接和关注引导。",
                "emotion": "calm",
            },
        ],
        "cta": "收藏这条视频，明天继续看 GitHub 新项目。",
    }
