# 模块任务: 内容生成模块

模块目标：基于候选项目元数据、README 摘要和评分理由生成结构化短视频脚本、标题、简介、标签、封面文案和 CTA。

## Checklist

- [ ] 定义 `POST /api/jobs/generate-script` 请求结构，包含 `repoFullName`、`style`、`durationSec`、`audience`。
- [ ] 定义脚本响应结构，包含 `jobId` 和 `script`。
- [ ] 定义脚本 JSON Schema，覆盖 `title`、`coverText`、`description`、`hashtags`、`segments`、`cta`。
- [ ] 定义 segment JSON Schema，覆盖 `type`、`durationSec`、`voiceText`、`screenText`、`visualHint`、`emotion`。
- [ ] 实现 `ProjectContextBuilder`，读取仓库元数据。
- [ ] 实现 `ProjectContextBuilder`，读取 README 摘要。
- [ ] 实现 `ProjectContextBuilder`，读取评分理由和风险提示。
- [ ] 实现 `ModelAdapter` 接口，隔离具体 LLM 供应商。
- [ ] 实现 DeepSeek 默认配置入口，保持可替换。
- [ ] 实现 `SummaryGenerator`，生成项目摘要、标题候选和标签候选。
- [ ] 实现 `ScriptGenerator`，生成最终结构化脚本。
- [ ] 在 prompt 中约束前 3 秒必须给出 Hook。
- [ ] 在 prompt 中禁止“大家好，今天介绍”类低效开场。
- [ ] 在 prompt 中要求使用普通开发者可理解表达。
- [ ] 在 prompt 中要求说明项目解决的问题、火的原因和适合人群。
- [ ] 在 prompt 中要求包含项目名、核心能力、技术亮点和使用场景。
- [ ] 在 prompt 中要求结尾 CTA。
- [ ] 实现 `ScriptSchemaValidator` 校验 JSON 结构和必填字段。
- [ ] 实现 `FactGuard`，检查性能指标、融资、官方背书、用户数量、商业合作和未验证能力。
- [ ] 实现事实缺失时的保守表达或回退策略。
- [ ] 实现非 JSON 输出的 `ScriptRepairer` 修复流程。
- [ ] 实现 JSON Schema 校验失败后的修复或重试流程。
- [ ] 实现连续失败 3 次后标记任务失败。
- [ ] 实现标题为空或简介为空时视为生成失败。
- [ ] 实现脚本 JSON 写入对象存储。
- [ ] 实现脚本产物元数据写入存储层。
- [ ] 写入内容生成模块运行日志。
- [ ] 编写 Mock ModelAdapter 合法 JSON 测试。
- [ ] 编写 Mock ModelAdapter 非法 JSON 修复测试。
- [ ] 编写缺少 README 不编造事实测试。
- [ ] 编写脚本 Schema 必填字段测试。
- [ ] 编写 segment 配音文本和屏幕字幕存在测试。

## 完成定义

- [ ] 生成结果必须是可解析 JSON。
- [ ] 脚本事实只来自元数据或 README。
- [ ] 输出可直接进入 TTS 与渲染模块。

