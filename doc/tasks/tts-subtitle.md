# 模块任务: TTS 与字幕模块

模块目标：将结构化脚本中的配音文本转换为音频，并生成可供渲染模块使用的字幕时间戳。

## Checklist

- [ ] 定义 `POST /api/jobs/generate-tts` 请求结构，包含 `taskId`、`voice`、`script`。
- [ ] 定义 TTS 响应结构，包含 `audioUrl`、`subtitleUrl`、可选 `srtUrl`。
- [ ] 定义字幕 JSON Schema，包含 `taskId`、`level`、`items`。
- [ ] 定义字幕 item Schema，包含 `text`、`startMs`、`endMs`、`segmentIndex`。
- [ ] 实现 `VoiceTextAssembler`，按 segments 顺序合并配音文本。
- [ ] 实现情绪提示到 TTS 请求参数的映射。
- [ ] 实现停顿、强调、疑问等提示的最小表达。
- [ ] 实现 `TTSAdapter` 接口，隔离 Fish Audio 或同等服务。
- [ ] 实现默认中文科技口播 voice 配置。
- [ ] 实现 TTS 请求发送和响应解析。
- [ ] 实现音频文件保存。
- [ ] 实现 `TimestampNormalizer`，支持词级时间戳。
- [ ] 实现 `TimestampNormalizer`，支持短句级时间戳。
- [ ] 实现时间戳缺失时降级为句级字幕。
- [ ] 实现 `SubtitleBuilder` 生成字幕 JSON。
- [ ] 实现字幕时间递增校验。
- [ ] 实现字幕文本与脚本配音文本对应校验。
- [ ] 实现 `SrtExporter`，必要时导出 SRT。
- [ ] 实现字幕文件保存。
- [ ] 实现音频产物元数据写入存储层。
- [ ] 实现字幕产物元数据写入存储层。
- [ ] TTS 调用失败时执行重试。
- [ ] 音频生成失败时返回失败，不输出可渲染结果。
- [ ] 字幕时间戳不递增时标记 TTS 阶段失败。
- [ ] 音频文件不可访问时标记 TTS 阶段失败。
- [ ] 写入 TTS 模块运行日志。
- [ ] 编写固定脚本文本拼接测试。
- [ ] 编写 Mock TTSAdapter 成功返回测试。
- [ ] 编写词级时间戳缺失降级测试。
- [ ] 编写字幕时间递增测试。
- [ ] 编写音频失败不会进入渲染测试。
- [ ] 编写字幕 JSON 契约测试。

## 完成定义

- [ ] 输出音频 URL 和字幕 URL 可被渲染模块读取。
- [ ] 字幕时间戳严格递增。
- [ ] 音频失败不会产生可渲染任务结果。

