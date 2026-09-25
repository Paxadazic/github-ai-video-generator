# 模块任务: 评分与去重模块

模块目标：将候选项目过滤、打分、去重并输出 3-5 个可推荐项目，附带推荐理由和风险提示。

## Checklist

- [ ] 定义 `POST /api/jobs/score-candidates` 接口请求结构，包含 `jobId`、`candidates`、`targetCount`。
- [ ] 定义评分接口响应结构，包含 `recommended`、`scoreBreakdown`、`riskFlags`、`recommendReason`。
- [ ] 实现请求参数校验，`targetCount` 默认 5。
- [ ] 实现 `CandidateFilter`，过滤 README 过短项目。
- [ ] 实现 `CandidateFilter`，过滤无法解释核心用途的项目。
- [ ] 实现 `CandidateFilter`，过滤描述为空项目。
- [ ] 实现 `CandidateFilter`，过滤链接异常项目。
- [ ] 实现 `CandidateFilter`，过滤明显无关或低质量仓库。
- [ ] 实现 `DedupChecker`，读取近期已生成或已跳过项目。
- [ ] 实现近期重复仓库过滤。
- [ ] 定义评分配置结构，包含各评分项权重和惩罚项权重。
- [ ] 实现 `RuleScorer` 的日榜热度分。
- [ ] 实现 `RuleScorer` 的总 Star 背书分。
- [ ] 实现 `RuleScorer` 的 README 可解释性分。
- [ ] 实现 `RuleScorer` 的 AI/开发工具相关性分。
- [ ] 实现 `RuleScorer` 的项目新鲜度分。
- [ ] 实现重复题材惩罚。
- [ ] 实现异常项目惩罚。
- [ ] 实现 `RiskFlagger`，标记创建时间极短但 Star 异常飙升项目。
- [ ] 实现 `RiskFlagger`，标记信息不足但热度较高项目。
- [ ] 实现 `RecommendationSelector`，按分数选出 3-5 个项目。
- [ ] 实现有效候选不足时的降级输出。
- [ ] 实现 `ScoreExplainer`，生成非空推荐理由。
- [ ] 将评分、风险和推荐理由回写候选项目记录。
- [ ] 写入评分模块运行日志。
- [ ] 编写固定候选列表过滤测试。
- [ ] 编写历史发布记录去重测试。
- [ ] 编写风险标记测试。
- [ ] 编写输出数量 3-5 个测试。
- [ ] 编写评分解释非空测试。
- [ ] 编写评分配置变更不会破坏响应结构的契约测试。

## 完成定义

- [ ] 输出推荐项目满足 3-5 个目标或明确说明有效候选不足。
- [ ] 每个推荐项目都有评分明细、风险标记和推荐理由。
- [ ] 去重逻辑能阻止一天内重复推荐同一仓库。

