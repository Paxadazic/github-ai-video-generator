# MVP 模块进度

来源：`doc/proposal.md`、`doc/detailed-design.md`、`doc/tasks/*.md`

## 模块完成状态

- [x] `storage-layer.md`：存储层
- [x] `n8n-control-plane.md`：Python 控制面 / n8n 边界
- [x] `github-collector.md`：GitHub 采集模块
- [x] `scoring-dedup.md`：评分与去重模块
- [x] `content-generation.md`：内容生成模块
- [x] `tts-subtitle.md`：TTS 与字幕模块
- [x] `video-rendering.md`：视频渲染模块
- [x] `quality-check.md`：自动质量检查模块
- [x] `manual-review.md`：人工审核模块
- [x] `publish-ledger.md`：发布素材与台账模块

## 集成里程碑

- [x] 完成全局响应结构、错误结构和任务状态枚举的共享契约。
- [x] 完成 SQLite 存储层，支持候选项目、视频任务、产物、去重记录、发布记录和运行日志。
- [x] 完成采集到评分的候选项目链路，能返回 3-5 个推荐项目。
- [x] 完成选中项目到结构化脚本的链路，脚本通过 Schema 和事实约束检查。
- [x] 完成脚本到音频、字幕的链路，字幕时间戳递增。
- [x] 完成脚本、音频、字幕到 1080x1920 MP4 和封面的 fake 渲染链路。
- [x] 完成自动质量检查，失败产物不会进入人工审核。
- [x] 完成人工审核通过、拒绝和重试动作校验。
- [x] 完成发布素材包导出和人工发布台账写入。
- [x] 完成最小端到端冒烟测试：Mock GitHub -> 候选推荐 -> 脚本 -> TTS -> 渲染 -> 质检 -> 审核 -> 素材包 -> 台账。

## 验证结果

- [x] `pytest`：20 passed
- [x] `mypy app tests`：success
- [x] `ruff check .`：all checks passed
