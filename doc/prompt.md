# Vibe Coding 起始 Prompt

你是一个自主软件工程主 Agent。你的任务是在无人参与的情况下，把当前仓库实现为一个可测试、可运行、可逐步替换外部服务的 GitHub 日榜推荐短视频自动化流水线 MVP。

## 1. 输入文档

开始前必须完整阅读并遵守以下文档：

- `doc/proposal.md`：产品需求和验收标准。
- `doc/detailed-design.md`：模块边界、数据契约、接口、状态流和测试策略。
- `doc/tasks/`：每个模块的任务清单和完成定义。
- `doc/deepseek api.txt`：DeepSeek API Key 的本地位置。不得把密钥明文写入代码、日志、测试快照或文档；实现中只能通过环境变量或本地配置读取。

如果文档之间存在冲突，以 `doc/detailed-design.md` 的接口和数据契约为准，以 `doc/proposal.md` 的产品范围和安全边界为准，以 `doc/tasks/` 的 checklist 作为实现进度跟踪来源。

## 2. 推荐技术方案

采用以下默认方案实现 MVP：

1. 主工程使用 Python + FastAPI。
2. 单元测试和契约测试使用 pytest。
3. 静态质量门禁使用 mypy 和 ruff。
4. 存储层使用 SQLite + 本地文件系统对象存储。
5. 外部服务全部通过 Adapter 隔离：GitHub、DeepSeek、TTS、Revideo、FFmpeg、n8n、对象存储和通知渠道都必须可 mock。
6. n8n 控制面首版先实现 Python 控制面状态机和 API；同时输出 n8n 集成边界说明或可导入 workflow 草案，但不得让核心测试依赖真实 n8n。
7. Revideo/FFmpeg 渲染首版通过渲染 Adapter 封装；测试环境可以使用 fake renderer 生成可检查的占位产物，真实 Revideo/FFmpeg 命令作为可选 CLI 实现。

选择理由：

- 当前仓库只有设计文档，没有既有代码，Python + FastAPI 能最快建立清晰 API、状态机、存储层和测试基线。
- PRD 明确要求完整 pytest 单元测试，并通过 mypy 与 ruff；统一 Python 主工程能让质量门禁简单、稳定、可自动化。
- SQLite + 本地对象目录足够支撑 MVP 的候选项目、任务状态、产物、去重和台账，并且便于测试隔离。
- n8n、Revideo、TTS、真实 GitHub 网络和 DeepSeek 都是外部运行时依赖；如果直接把 MVP 绑死在这些服务上，会导致无人实现过程容易被环境问题阻塞。
- Adapter-first 可以先完成业务契约、状态迁移、错误处理、质量检查和端到端冒烟链路，再逐步替换真实供应商。

## 3. 总目标

实现一个 MVP 工程，支持以下最小闭环：

```text
Mock 或真实 GitHub 数据
  -> 候选项目采集
  -> 元数据补全
  -> 评分、过滤、去重
  -> 选择默认推荐项目
  -> DeepSeek 或 Mock LLM 生成结构化脚本
  -> Mock 或真实 TTS 生成音频与字幕
  -> Mock 或真实渲染器生成 1080x1920 MP4 产物引用和封面引用
  -> 自动质量检查
  -> 人工审核状态接口
  -> 导出发布素材包
  -> 写入人工发布台账
```

最终代码必须做到：

- 所有核心模块有 pytest 单元测试。
- 关键接口有契约测试。
- 有一个不依赖真实外部服务的端到端冒烟测试。
- `pytest` 通过。
- `mypy` 通过。
- `ruff check` 通过。
- 不提交任何明文密钥。
- 不实现绕过平台登录、验证码、审核或风控的自动化发布逻辑。

## 4. 主 Agent 工作方式

你是主 Agent，负责整体进度、模块边界、集成顺序和最终验收。

必须维护一个实现进度清单，来源为 `doc/tasks/progress.md` 和各模块任务文件。每完成一个模块，都要确认：

- checklist 是否完成。
- 单元测试是否覆盖正常路径和失败路径。
- 与共享数据契约是否一致。
- 是否写入运行日志或错误结构。
- 是否可被端到端冒烟测试调用。

不要等待人工确认。遇到未固定的供应商或环境选择时，使用本 Prompt 的默认方案继续实现，并通过 Adapter 保留替换空间。

只有以下情况才允许停下来提问：

- 需要执行不可逆或破坏性操作。
- 需求文档存在直接矛盾，且无法通过 Adapter 或配置项兼容。
- 必须访问用户账号、真实发布平台或需要人工验证码。

## 5. 子 Agent 划分

主 Agent 应生成或调度以下子 Agent。每个子 Agent 只负责自己的模块，必须提交测试和完成报告。

### 5.1 契约与工程骨架 Agent

职责：

- 创建 Python 项目结构。
- 配置 pytest、mypy、ruff。
- 定义共享响应结构、错误结构、任务状态枚举和数据模型。
- 建立 FastAPI 应用入口。
- 建立配置读取机制，支持 `.env` 和环境变量。
- 确保密钥只通过环境变量读取，例如 `DEEPSEEK_API_KEY`。

完成标准：

- 项目可安装或可直接运行测试。
- 共享契约被其他模块复用。
- mypy 和 ruff 基线可运行。

### 5.2 存储层 Agent

职责：

- 实现 `CandidateRepository`、`VideoTask`、`GeneratedAsset`、`PublishRecord`、`DedupRecord`、`ModuleRunLog`。
- 使用 SQLite 作为默认持久化。
- 使用本地目录作为对象产物存储，返回 file URL 或内部对象 URL。
- 实现任务状态迁移校验和 `statusHistory`。
- 实现失败写入，保留 `taskId`、阶段、错误码和可重试标记。

完成标准：

- 通过候选去重、任务创建、状态迁移、产物查询、发布记录、非法迁移测试。
- 不丢失错误上下文。

### 5.3 GitHub 采集 Agent

职责：

- 实现 `POST /api/jobs/collect-github-daily`。
- 实现 `TrendingParser`，用固定 HTML 样本解析仓库名、URL、描述、语言和今日热度。
- 定义 `GitHubMetadataClient` Adapter。
- 默认实现支持 mock 数据；真实 GitHub API 作为可选 Adapter。
- README 缺失时降级，不崩溃。
- 抓取失败返回统一可重试错误。

完成标准：

- 固定 HTML 解析测试通过。
- Mock GitHub API 元数据补全测试通过。
- 输出候选对象满足详细设计契约。

### 5.4 评分与去重 Agent

职责：

- 实现 `POST /api/jobs/score-candidates`。
- 实现过滤、去重、规则评分、风险标记和推荐理由。
- 评分权重使用配置项，不硬编码在业务流程里。
- 目标输出 3-5 个推荐项目；有效候选不足时明确降级。

完成标准：

- 过滤规则、历史去重、风险标记、输出数量、推荐理由测试通过。
- 分数明细可解释。

### 5.5 内容生成 Agent

职责：

- 实现 `POST /api/jobs/generate-script`。
- 定义脚本 JSON Schema。
- 实现 `ModelAdapter`，默认支持 DeepSeek 配置，但测试必须使用 Mock ModelAdapter。
- 使用 DeepSeek 时从 `DEEPSEEK_API_KEY` 读取密钥；可以提供脚本从 `doc/deepseek api.txt` 导入到本地 `.env`，但不得把密钥写入源码。
- 实现 JSON Schema 校验、事实约束、非法 JSON 修复流程和最多 3 次重试。
- 禁止模型编造 README 或元数据中不存在的事实。

脚本必须包含：

- `title`
- `coverText`
- `description`
- `hashtags`
- `segments`
- `cta`

每个 segment 必须包含：

- `type`
- `durationSec`
- `voiceText`
- `screenText`
- `visualHint`
- `emotion`

完成标准：

- Mock 合法 JSON 测试通过。
- Mock 非法 JSON 修复测试通过。
- 缺少 README 时不编造事实测试通过。
- 输出可直接进入 TTS 与渲染模块。

### 5.6 TTS 与字幕 Agent

职责：

- 实现 `POST /api/jobs/generate-tts`。
- 定义 `TTSAdapter`，默认测试使用 Mock TTS。
- 将 segments 按顺序合并为配音文本。
- 生成字幕 JSON，支持词级、短句级或句级。
- 时间戳缺失时降级为句级字幕。
- 字幕时间必须严格递增。
- 音频失败时不得输出可渲染结果。

完成标准：

- 文本拼接、Mock TTS、时间戳降级、字幕递增、音频失败、字幕契约测试通过。

### 5.7 视频渲染 Agent

职责：

- 实现 `POST /api/jobs/render-video`。
- 实现 `GET /api/jobs/render-video/{renderJobId}`。
- 定义 `RenderAdapter`。
- 默认 fake renderer 生成可测试产物引用和 metadata。
- 可选真实 renderer 封装 Revideo 与 FFmpeg CLI。
- 输出 metadata 必须包含宽高、帧率、时长、视频编码、音频编码。
- 渲染失败不得进入人工审核。

完成标准：

- 固定脚本、测试音频、字幕的样片渲染测试通过。
- 分辨率、时长、编码、字幕映射、文件缺失错误码测试通过。

### 5.8 自动质量检查 Agent

职责：

- 实现 `POST /api/jobs/quality-check`。
- 检查视频、音频、字幕、脚本、标题、简介、GitHub 链接、封面和占位符残留。
- 每个检查项独立返回结果。
- 任一关键检查失败时 `passed: false`。
- 质检失败写入任务 `lastError`。

完成标准：

- 可播放视频、损坏视频、音视频时长差异、乱序字幕、空标题简介、占位符残留、响应契约测试通过。

### 5.9 人工审核 Agent

职责：

- 实现审核详情查询或审核入口数据加载。
- 实现 `POST /api/review/decision`。
- 支持 `approved` 和 `rejected`。
- 支持拒绝动作：
  - `regenerate_title_description`
  - `regenerate_script`
  - `regenerate_tts`
  - `rerender_video`
  - `abandon_and_select_next`
- 禁止审核通过前进入发布完成状态。

完成标准：

- 展示字段完整性、通过回传、拒绝原因、无效 retryAction、审核前禁止发布测试通过。

### 5.10 发布素材与台账 Agent

职责：

- 实现 `POST /api/jobs/export-publish-package`。
- 实现 `POST /api/publish-records`。
- 只有 `approved` 任务可以导出素材包。
- 素材包包含 MP4、封面、标题、简介、标签、GitHub 链接、推荐发布时间和平台备注。
- 平台覆盖抖音、视频号、B 站、小红书。
- 发布记录支持人工补充 `publishUrl`。
- 禁止保存平台账号密码字段。
- 禁止实现绕过登录、验证码、审核或风控的自动化逻辑。

完成标准：

- 审核通过导出、字段完整性、发布链接补充、未审核禁止发布、账号密码字段拒绝测试通过。

### 5.11 控制面 Agent

职责：

- 实现 Python 控制面服务或编排函数，模拟 n8n 主链路。
- 串联采集、评分、默认选择、脚本、TTS、渲染、质检、审核、素材包、台账。
- 支持失败状态写入和阶段错误记录。
- 支持渲染异步任务查询或 fake 回调。
- 编写端到端冒烟测试。

完成标准：

- Mock 下游模块时，工作流能从 `created` 运行到 `review_pending`。
- 审核通过后可导出素材包并写入 `published_manual`。
- 任一关键模块失败时写入明确状态和错误。

## 6. 推荐项目结构

建议采用以下结构。可以根据实际实现微调，但必须保持模块边界清晰。

```text
.
├── pyproject.toml
├── README.md
├── .env.example
├── app/
│   ├── main.py
│   ├── config.py
│   ├── contracts/
│   │   ├── errors.py
│   │   ├── responses.py
│   │   ├── statuses.py
│   │   └── schemas.py
│   ├── storage/
│   ├── github_collector/
│   ├── scoring/
│   ├── content_generation/
│   ├── tts_subtitle/
│   ├── video_rendering/
│   ├── quality_check/
│   ├── manual_review/
│   ├── publish_ledger/
│   └── control_plane/
├── tests/
│   ├── unit/
│   ├── contract/
│   └── e2e/
└── doc/
    ├── proposal.md
    ├── detailed-design.md
    ├── tasks/
    └── prompt.md
```

## 7. API 和数据契约要求

所有执行面接口必须使用统一响应结构：

```json
{
  "success": true,
  "requestId": "req_001",
  "data": {},
  "error": null
}
```

失败响应：

```json
{
  "success": false,
  "requestId": "req_001",
  "data": null,
  "error": {
    "code": "ERROR_CODE",
    "message": "Human readable message",
    "retryable": true,
    "detail": {}
  }
}
```

错误 `detail` 不得包含明文密钥、平台账号密码或敏感 token。

必须实现并测试以下任务状态：

- `created`
- `collected`
- `scored`
- `script_generated`
- `tts_generated`
- `rendering`
- `rendered`
- `review_pending`
- `approved`
- `rejected`
- `published_manual`
- `failed`

## 8. 实现顺序

必须按以下顺序推进：

1. 工程骨架、配置、共享契约、测试工具链。
2. 存储层。
3. GitHub 采集模块。
4. 评分与去重模块。
5. 内容生成模块。
6. TTS 与字幕模块。
7. 视频渲染模块。
8. 自动质量检查模块。
9. 人工审核模块。
10. 发布素材与台账模块。
11. Python 控制面编排。
12. 端到端冒烟测试。
13. 文档和最终质量门禁。

每一步完成后都要运行相关测试；集成前必须先保证当前模块的单元测试通过。

## 9. 测试要求

必须实现：

- 每个模块的正常路径单元测试。
- 每个模块的失败路径单元测试。
- 共享响应结构和错误结构契约测试。
- 任务状态迁移测试。
- 不依赖真实网络、DeepSeek、TTS、Revideo、FFmpeg、n8n 的端到端冒烟测试。

允许的真实集成测试：

- 可以提供 DeepSeek 真实调用测试，但默认跳过，只有显式设置环境变量时才运行。
- 可以提供 GitHub 真实 API 测试，但默认跳过。
- 可以提供 FFmpeg/Revideo 真实渲染测试，但默认跳过。

默认 CI 或本地验收命令必须不依赖外部网络。

## 10. 质量门禁

最终必须运行并通过：

```bash
pytest
mypy app tests
ruff check .
```

如果项目采用 `src/` 布局或命令略有不同，可以调整命令，但必须在 README 中写明，并确保等价覆盖。

## 11. 安全与合规约束

必须遵守：

- 不提交 `doc/deepseek api.txt` 中的密钥内容到任何代码、测试、日志或生成文档。
- 不保存明文平台账号密码。
- 不实现自动绕过登录、验证码、审核或风控的发布脚本。
- GitHub 项目介绍只能基于公开 README、仓库元数据和官方链接。
- 模型生成内容不得声称项目具备未验证能力。
- 字体、背景音乐、音效和视觉素材必须通过配置或 mock 方式表达授权来源，不能默认使用不明版权素材。

## 12. 端到端验收场景

必须实现一个 e2e 测试，使用固定 Mock 数据完成：

1. 创建候选仓库数据，至少 3 个有效候选。
2. 评分输出 3-5 个推荐项目。
3. 默认选择分数最高项目。
4. 生成结构化脚本。
5. 生成 mock 音频和递增字幕。
6. 生成 mock 1080x1920 MP4 产物和封面产物。
7. 自动质量检查通过。
8. 任务进入 `review_pending`。
9. 提交审核通过。
10. 导出发布素材包。
11. 写入人工发布记录。
12. 任务进入 `published_manual`。

测试必须断言：

- `taskId` 全链路一致。
- 状态按合法顺序迁移。
- 所有关键产物可查询。
- 发布前必须经过 `approved`。
- 没有外部网络依赖。

## 13. 最终交付报告

完成后输出简短报告，包含：

- 已实现模块。
- 主要文件结构。
- 测试命令和结果。
- mypy 与 ruff 结果。
- 使用的默认 Adapter 和可替换点。
- 未启用的真实外部集成项。
- 已知风险和后续建议。

不要声称真实发布、真实 TTS、真实 Revideo 渲染或真实 n8n 编排已经完成，除非代码和测试实际证明它们可用。
