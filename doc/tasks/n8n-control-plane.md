# 模块任务: n8n 控制面

模块目标：负责触发、编排、状态流转、通知、人工确认和发布台账协调，不直接实现业务算法。

## Checklist

- [ ] 定义每日采集工作流入口，支持定时触发。
- [ ] 定义每日采集工作流入口，支持手动触发。
- [ ] 实现当日批次创建或读取步骤。
- [ ] 调用 `POST /api/jobs/collect-github-daily` 获取候选项目。
- [ ] 将采集结果写入存储层候选项目表。
- [ ] 调用 `POST /api/jobs/score-candidates` 执行评分与去重。
- [ ] 保存评分结果、风险标记和推荐理由。
- [ ] 向运营者推送 3-5 个候选项目。
- [ ] 实现人工选择候选项目入口。
- [ ] 实现接受默认推荐项目的分支。
- [ ] 创建 `VideoTask` 并绑定选中 `repoFullName`。
- [ ] 调用 `POST /api/jobs/generate-script` 生成结构化脚本。
- [ ] 脚本生成成功后更新任务状态为 `script_generated`。
- [ ] 调用 `POST /api/jobs/generate-tts` 生成音频和字幕。
- [ ] TTS 成功后更新任务状态为 `tts_generated`。
- [ ] 调用 `POST /api/jobs/render-video` 创建异步渲染任务。
- [ ] 渲染提交成功后更新任务状态为 `rendering`。
- [ ] 实现渲染完成 Webhook 回调处理。
- [ ] 实现渲染状态轮询兜底流程。
- [ ] 渲染成功后更新任务状态为 `rendered`。
- [ ] 调用 `POST /api/jobs/quality-check` 执行自动质量检查。
- [ ] 质量检查通过后更新任务状态为 `review_pending`。
- [ ] 质量检查失败时更新任务为 `failed` 并记录错误。
- [ ] 创建人工审核入口或发送审核通知。
- [ ] 处理审核通过决策并更新任务状态为 `approved`。
- [ ] 处理审核拒绝决策并更新任务状态为 `rejected`。
- [ ] 根据拒绝动作触发重新生成标题简介、脚本、TTS、渲染或放弃项目。
- [ ] 审核通过后调用 `POST /api/jobs/export-publish-package` 导出素材包。
- [ ] 人工发布完成后调用 `POST /api/publish-records` 写入台账。
- [ ] 发布台账写入成功后更新任务状态为 `published_manual`。
- [ ] 为采集失败配置 1-3 分钟后重试。
- [ ] 为采集重试失败配置 GitHub Search API 备用分支。
- [ ] 为 LLM、TTS、渲染失败配置对应错误记录和通知分支。
- [ ] 编写 Mock 下游模块的工作流测试。
- [ ] 编写端到端工作流冒烟测试，从 `created` 跑到 `review_pending`。

## 完成定义

- [ ] 控制面能串起完整 MVP 主链路。
- [ ] 任一关键模块失败时能写入明确任务状态和错误。
- [ ] 人工审核前不会进入发布素材导出。

