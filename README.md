# GitHub Daily Video MVP

Python + FastAPI MVP for a GitHub daily trending recommendation short-video pipeline.

## What Is Implemented

- Shared API envelope and error contract.
- SQLite storage for candidates, tasks, assets, dedup records, publish records, and run logs.
- Local filesystem object storage returning `file://` URLs.
- GitHub Trending collector with fixed HTML parser and mock metadata adapter.
- Rule-based scoring, filtering, deduplication, risk flags, and recommendation reasons.
- Structured script generation behind a model adapter, with JSON repair and fact guard.
- Mock TTS adapter for tests, plus optional MiniMax CLI / Edge TTS / Windows SAPI real adapters.
- Fake render adapter for tests, plus optional FFmpeg/Pillow Chinese information-card renderer.
- Automatic quality checks before review.
- Manual review decision API.
- Publish package export and manual publish ledger.
- Python control-plane orchestration that simulates the n8n main path.

## Run

```bash
python -m pip install -e ".[dev]"
pytest
mypy app tests
ruff check .
```

Start the API:

```bash
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000/` for the local generation page. It has a one-click
button for the real GitHub + MiniMax CLI + FFmpeg draft workflow.

## Configuration

Copy `.env.example` to `.env` for local overrides. Secrets are read from environment variables only.

- `DATABASE_URL`: defaults to `sqlite:///./data/app.db`
- `OBJECT_STORAGE_DIR`: defaults to `./data/objects`
- `DEEPSEEK_API_KEY`: optional; real DeepSeek calls are disabled by default
- `DEEPSEEK_API_KEY_FILE`: optional local key file, defaults to `doc/deepseek api.txt`
- `GITHUB_TOKEN`: optional; real GitHub API calls are not used by default
- `MODEL_PROVIDER`: `mock`, `deepseek`, or `minimax`
- `TTS_PROVIDER`: `mock`, `minimax`, `minimax_http`, `edge_tts`, or `windows_sapi`
- `MINIMAX_CLI_PATH`: MiniMax CLI executable, defaults to `mmx`
- `MINIMAX_CLI_REGION`: MiniMax CLI region, defaults to `cn`
- `MINIMAX_TEXT_MODEL`: MiniMax CLI text model, defaults to `MiniMax-M2.7`
- `MINIMAX_TTS_MODEL`: MiniMax CLI TTS model, defaults to `speech-2.8-hd`
- `MINIMAX_TTS_VOICE_ID`: MiniMax TTS voice, defaults to `Chinese (Mandarin)_News_Anchor`
- `MINIMAX_RUNTIME_TMP_DIR`: project-local CLI temp directory, defaults to `data/runtime_tmp`
- `RENDER_PROVIDER`: `fake` or `ffmpeg_info`

Do not copy values from `doc/deepseek api.txt` into source, tests, logs, or docs.
MiniMax Token Plan usage relies on `mmx auth login`; API keys are not passed on the
Python command line. The old MiniMax HTTP TTS adapter remains available as
`TTS_PROVIDER=minimax_http` for pay-as-you-go API keys.

## Main API

All endpoints return:

```json
{"success": true, "requestId": "req_x", "data": {}, "error": null}
```

Implemented endpoints:

- `POST /api/jobs/collect-github-daily`
- `POST /api/jobs/score-candidates`
- `POST /api/jobs/generate-script`
- `POST /api/jobs/generate-tts`
- `POST /api/jobs/render-video`
- `GET /api/jobs/render-video/{renderJobId}`
- `POST /api/jobs/quality-check`
- `GET /api/review/{taskId}`
- `POST /api/review/decision`
- `POST /api/jobs/export-publish-package`
- `POST /api/publish-records`
- `POST /api/control-plane/run-to-review-pending`

## Adapter Boundaries

Default adapters used in tests:

- GitHub: fixed Trending HTML + `MockGitHubMetadataClient`
- LLM: `MockModelAdapter`
- TTS: `MockTTSAdapter`
- Renderer: `FakeRenderAdapter`
- Storage: `LocalObjectStore`
- Control plane: Python `ControlPlaneService`

Replaceable points:

- `GitHubMetadataClient` for REST or GraphQL metadata.
- `ModelAdapter` for DeepSeek, MiniMax CLI, or another LLM provider.
- `TTSAdapter` for MiniMax CLI, Edge TTS, Fish Audio, or another TTS provider.
- `RenderAdapter` for Revideo/FFmpeg CLI integration.
- Control-plane caller for real n8n workflow triggers.

## Real Content Mode

The default mode stays offline and deterministic for tests. To generate a real GitHub
daily recommendation draft, start the API with real providers enabled:

```powershell
cd <project-directory>
$env:GITHUB_PROVIDER="real"
$env:MODEL_PROVIDER="minimax"
$env:TTS_PROVIDER="minimax"
$env:RENDER_PROVIDER="ffmpeg_info"
$env:MINIMAX_CLI_PATH="mmx"
$env:MINIMAX_CLI_REGION="cn"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Then open:

```text
http://127.0.0.1:8000/
```

This uses:

- Real GitHub Trending HTML and GitHub repository metadata.
- MiniMax CLI `text chat` for the structured script.
- MiniMax CLI `speech synthesize` for MP3 narration.
- An FFmpeg/Pillow Chinese information-card template for an openable 1080x1920 MP4 and PNG cover.

Each run writes assets into a separate timestamp-named folder under
`OBJECT_STORAGE_DIR`, for example `20260522_130015_github_daily_video`.
This is an information-card video, not a final Revideo animated template.

## n8n Boundary

The MVP does not require real n8n for tests. A real n8n workflow should call the HTTP endpoints in this order:

1. `collect-github-daily`
2. `score-candidates`
3. create/select a task and candidate
4. `generate-script`
5. `generate-tts`
6. `render-video`, then poll `GET /render-video/{renderJobId}`
7. `quality-check`
8. wait for human review through `review/decision`
9. `export-publish-package`
10. `publish-records`

The Python `ControlPlaneService` is the executable local stand-in for this workflow.

## Verification

Latest local results:

- `pytest`: 20 passed
- `mypy app tests`: success, no issues
- `ruff check .`: all checks passed

## Not Enabled

- Real Revideo rendering.
- Real n8n execution.
- Automated publishing to Douyin, WeChat Channels, Bilibili, or Xiaohongshu.

## Safety

The publish module only prepares material packages and records manual publish results. It rejects password/token-like fields and does not implement login, captcha, review, or risk-control bypass automation.
