# 模块任务: 存储层

模块目标：为所有模块提供候选项目、视频任务、产物、去重记录、发布记录和运行日志的统一读写能力。

## Checklist

- [ ] 定义 `CandidateRepository` 数据模型，字段覆盖 `repoFullName`、`repoUrl`、描述、语言、Topics、Star、Fork、README、时间、License、评分、风险标记和推荐理由。
- [ ] 为 `CandidateRepository` 添加 `repoFullName` 业务唯一约束。
- [ ] 实现候选项目批量写入接口，支持采集模块一次写入多个候选。
- [ ] 实现候选项目按 `repoFullName` 查询接口。
- [ ] 实现候选项目按批次或采集时间查询接口。
- [ ] 定义 `VideoTask` 数据模型，字段覆盖 `taskId`、`repoFullName`、`status`、产物引用、创建时间、更新时间和 `lastError`。
- [ ] 定义任务状态枚举，覆盖 `created`、`collected`、`scored`、`script_generated`、`tts_generated`、`rendering`、`rendered`、`review_pending`、`approved`、`rejected`、`published_manual`、`failed`。
- [ ] 实现任务创建接口，默认状态为 `created`。
- [ ] 实现任务状态更新接口，写入 `statusHistory`。
- [ ] 实现任务状态非法迁移校验。
- [ ] 实现任务失败写入接口，必须保存错误码、阶段、可重试标记和 `taskId`。
- [ ] 定义 `GeneratedAsset` 数据模型，字段覆盖 `assetId`、`taskId`、类型、URL、contentType、size、checksum 和 metadata。
- [ ] 实现产物写入接口，支持脚本、音频、字幕、封面和视频类型。
- [ ] 实现按 `taskId` 查询全部产物接口。
- [ ] 实现按 `assetId` 查询单个产物接口。
- [ ] 定义 `PublishRecord` 数据模型，字段覆盖平台、标题、简介、标签、发布时间、发布链接和操作人。
- [ ] 实现发布记录写入接口。
- [ ] 实现按 `taskId` 查询发布记录接口。
- [ ] 定义 `DedupRecord` 数据模型，支持记录已生成、已跳过或已放弃仓库。
- [ ] 实现去重查询接口，供评分模块判断近期是否已生成。
- [ ] 定义 `ModuleRunLog` 数据模型，覆盖模块名、阶段、耗时、成功状态、错误码和产物引用。
- [ ] 实现模块运行日志写入接口。
- [ ] 实现通用响应结构封装，成功和失败响应字段保持一致。
- [ ] 编写存储层单元测试：候选项目去重、任务创建、状态迁移、产物查询、发布记录写入。
- [ ] 编写失败路径测试：非法状态迁移被拒绝，失败错误不会丢失 `taskId` 和阶段信息。

## 完成定义

- [ ] 所有模型字段满足详细设计数据契约。
- [ ] 所有写入接口可被其他模块用 Mock 数据调用。
- [ ] 单元测试覆盖正常路径和失败路径。

