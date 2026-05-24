# 模块任务: 视频渲染模块

模块目标：使用 Revideo 和 FFmpeg 将脚本、音频、字幕渲染为 9:16 竖屏 MP4，并输出封面图。

## Checklist

- [ ] 定义 `POST /api/jobs/render-video` 请求结构，包含 `taskId`、`template`、`scriptUrl`、`audioUrl`、`subtitleUrl`。
- [ ] 定义渲染提交响应结构，包含 `renderJobId` 和 `status`。
- [ ] 定义渲染完成产物结构，包含 `videoUrl`、`coverUrl` 和 metadata。
- [ ] 定义 `GET /api/jobs/render-video/{renderJobId}` 查询接口。
- [ ] 实现 `RenderJobManager` 创建渲染任务。
- [ ] 实现 `RenderJobManager` 查询渲染任务状态。
- [ ] 实现 `RenderInputLoader` 读取脚本 JSON。
- [ ] 实现 `RenderInputLoader` 读取音频文件。
- [ ] 实现 `RenderInputLoader` 读取字幕 JSON。
- [ ] 实现输入文件不可访问错误码。
- [ ] 实现 `TemplateDataMapper` 将脚本映射到 Revideo 模板参数。
- [ ] 实现模板参数对开场 Hook 的支持。
- [ ] 实现模板参数对项目卡片的支持。
- [ ] 实现模板参数对 2-3 个核心卖点的支持。
- [ ] 实现模板参数对 README、终端效果、项目 UI 或代码片段展示的支持。
- [ ] 实现模板参数对动态字幕高亮的支持。
- [ ] 实现模板参数对结尾 CTA 的支持。
- [ ] 实现模板禁止单项目硬编码的配置校验。
- [ ] 实现 `RevideoRenderer` 渲染视频画面。
- [ ] 实现 `FfmpegComposer` 合成音频和视频。
- [ ] 配置输出分辨率为 1080x1920。
- [ ] 配置输出帧率为 30fps。
- [ ] 配置视频编码为 H.264。
- [ ] 配置音频编码为 AAC。
- [ ] 配置容器为 MP4。
- [ ] 实现输出时长 60-90 秒校验。
- [ ] 实现 `CoverGenerator` 生成封面图。
- [ ] 实现 `RenderAssetWriter` 保存 MP4 和封面。
- [ ] 实现渲染产物元数据写入存储层。
- [ ] 实现 `RenderCallbackSender` 回调 n8n。
- [ ] 支持 n8n 轮询查询渲染状态。
- [ ] Revideo 渲染失败时记录错误日志。
- [ ] FFmpeg 合成失败时记录错误日志。
- [ ] 支持相同素材重新渲染。
- [ ] 连续失败后标记任务失败并通知控制面。
- [ ] 编写固定脚本、测试音频、字幕的样片渲染测试。
- [ ] 编写输出分辨率测试。
- [ ] 编写输出时长测试。
- [ ] 编写编码格式测试。
- [ ] 编写字幕时间轴映射测试。
- [ ] 编写文件缺失错误码测试。

## 完成定义

- [ ] 可生成 1080x1920、30fps、H.264/AAC 的 MP4。
- [ ] 同一输入可重渲染。
- [ ] 渲染失败不会进入人工审核。

