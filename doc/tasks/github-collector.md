# 模块任务: GitHub 采集模块

模块目标：获取 GitHub Trending 日榜候选项目，并补全评分和内容生成所需的仓库元数据。

## Checklist

- [ ] 定义 `POST /api/jobs/collect-github-daily` 接口请求结构，包含 `language`、`since`、`limit`。
- [ ] 定义采集接口响应结构，包含 `jobId` 和 `candidates`。
- [ ] 实现请求参数校验，`since` MVP 默认只接受 `daily`。
- [ ] 实现 `TrendingPageFetcher`，使用 Playwright 打开 GitHub Trending 页面。
- [ ] 实现语言筛选参数映射，默认 `all`。
- [ ] 实现 `TrendingParser`，从 HTML 提取仓库全名。
- [ ] 实现 `TrendingParser`，提取仓库 URL。
- [ ] 实现 `TrendingParser`，提取仓库描述。
- [ ] 实现 `TrendingParser`，提取主语言。
- [ ] 实现 `TrendingParser`，提取今日热度信号。
- [ ] 实现 `limit` 限制，最多返回请求指定数量。
- [ ] 实现 `GitHubMetadataClient` 抽象，屏蔽 REST API 或 GraphQL API 选择。
- [ ] 实现仓库 Star、Fork、Topics、License、创建时间、更新时间补全。
- [ ] 实现 `ReadmeFetcher` 获取 README 文本。
- [ ] 实现 README 缺失的降级处理，保留空值且不崩溃。
- [ ] 实现 `CandidateNormalizer`，统一字段名和时间格式。
- [ ] 实现 GitHub 仓库 URL 合法性校验。
- [ ] 实现链接异常时标记候选无效。
- [ ] 实现采集结果写入存储层。
- [ ] 实现模块运行日志写入。
- [ ] 实现 Trending 页面抓取失败后的 1-3 分钟重试。
- [ ] 实现重试失败后的 GitHub Search API 备用采集逻辑。
- [ ] 实现 API 速率限制错误，返回 `retryable: true`。
- [ ] 实现统一错误结构，错误码可定位到抓取、解析、API、README 或标准化阶段。
- [ ] 编写固定 HTML 样本测试 `TrendingParser`。
- [ ] 编写 Mock GitHub API 测试元数据补全。
- [ ] 编写 README 缺失测试。
- [ ] 编写异常页面可重试错误测试。
- [ ] 编写输出数据契约测试。

## 完成定义

- [ ] 接口可返回满足契约的候选项目列表。
- [ ] 采集失败有重试和备用逻辑。
- [ ] 模块可用固定 HTML 和 Mock API 独立测试。

