# 灵剪 LingJian AI Video Editor

**Version:** 4.13.0 · **Platform:** any OS with Python 3.11+ and FFmpeg (browser-based editor) · **Source runtime:** Python 3.11+

LingJian is a browser-based nonlinear video editor with auditable AI-assisted editing. The web editor is the only supported product surface. The earlier PySide6 desktop application remains in the repository for reference but is no longer maintained (see [Desktop application (legacy)](#desktop-application-legacy)).

## Quick start

```sh
python -m pip install -r requirements-web.txt
python web_app.py
```

Open `http://127.0.0.1:5000`. Set `PORT` to use another port; macOS reserves 5000 for AirPlay Receiver, so `PORT=5002 python web_app.py` is a common choice there. On the first launch the login page asks you to create the initial administrator account. There is no default username or password.

FFmpeg lookup order: `LINGJIAN_FFMPEG`, `ffmpeg.exe` beside `web_app.py` (Windows only), `ffmpeg` on `PATH`, then the `imageio-ffmpeg` package that `requirements-web.txt` installs. `GET /api/health` reports which executable is in use and whether export is ready.

Uploaded media, the working project, the media catalog, exports, and the account database are kept under `web_workspace/` (override with `LINGJIAN_WEB_WORKSPACE`). The server binds to localhost by default.

## What you can do

| Area | Capabilities |
| --- | --- |
| Media pool | Upload video and audio through the browser. The server probes every file with FFmpeg; originals stay in the media library when timeline clips are removed. |
| Timeline editing | DaVinci-inspired layout with the media pool on the left, the program monitor in the center, the clip inspector on the right, and video/audio tracks across the bottom. Trim points, captions, transitions, source-audio volume, drag-to-reorder, timeline zoom, and a resizable timeline. |
| AI 导演 / AI Director | Pick source clips, a target duration, and an editing brief. Local mode analyzes scenes with FFmpeg and never uploads footage; cloud mode (when configured on the server) adds content analysis and narrative planning. Preview the shot list, apply it to the timeline, undo in one click. |
| Accounts and AI service | Administrators create editors or other administrators, change roles, enable or disable access, reset passwords, and delete accounts, and connect the cloud AI service (URL, API key, models) with a connection test. Passwords are stored as one-way hashes; write requests use a session-bound CSRF token. |
| Export | Portrait, landscape, and square MP4 presets using H.264/AAC, rendered asynchronously with preflight checks and output validation. |
| Language | The **EN / 中文** button switches the whole interface; language and layout settings are remembered in the browser. |

## Make your first video

1. **Import footage.** Click **＋ 导入 / Import** and select video or audio files. The login page and every screen switch between 中文 and English with the language control in the top-right corner.
2. **Ask the AI Director for a cut.** Click **AI 导演 / AI Director**, tick the source clips, set the target duration (5–180 seconds), describe what you want, and click **生成方案 / Generate Plan**. Local mode needs no API key.
3. **Review the plan.** The panel lists every shot with its source, in/out points, caption, and reasoning, plus what applying it will change (which timeline clips are replaced, whether background music is kept). Click a shot to preview it in the program monitor.
4. **Apply or discard.** **应用到时间线 / Apply to Timeline** replaces the video clips, saves the project to disk, and marks the new clips with an **AI** badge. **撤销应用 / Undo Apply** restores the previous timeline. Manual edits made after a plan was generated block applying it (HTTP 409), so a plan can never overwrite work it has not seen.
5. **Refine, save, export.** Trim, caption, and reorder clips as usual, click **保存工程 / Save Project**, then **导出 MP4 / Export MP4**.

## Optional cloud analysis

Administrators connect the cloud service under **账户管理 / Accounts → AI 接口 / AI Service**: service URL (HTTPS only), API key, vision model, transcription model, and request timeout, with a **测试连接 / Test Connection** button that calls the provider's model list. Settings are stored on the server in `web_workspace/ai_settings.json` (DPAPI-encrypted on Windows, owner-readable elsewhere), are never returned to browsers, and cannot be read or changed by editor accounts. Saved settings take precedence over the environment variables below, which remain available for headless deployments. Plan requests from the browser never carry keys, endpoints, or model names.

| Environment variable | Default |
| --- | --- |
| `FIGSTUDIO_AI_API_KEY` | empty; without web settings cloud mode is unavailable and local mode still works |
| `FIGSTUDIO_AI_BASE_URL` | `https://api.openai.com` (HTTPS required) |
| `FIGSTUDIO_AI_MODEL` | `gpt-5-mini` |
| `FIGSTUDIO_AI_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` |

The configured service must support `/v1/responses` with image input and structured JSON output, and `/v1/audio/transcriptions`. During a cloud run the server sends contact sheets, extracted audio, the editing brief, and analysis context; the AI Director panel requires an explicit consent tick for every cloud plan. See [cloud API setup](docs/cloud_ai_setup.md).

## Backend API (optional)

`python -m backend` starts a separate FastAPI service at `http://127.0.0.1:8000/docs` that stores multiple `.ljproject` files under `workspace/` and exposes the same AI planning, apply, and undo operations for integrations. The web editor does not depend on it. Install its dependencies with `requirements-backend.txt`; see the [backend API guide](docs/backend_api.md) and the [AI workflow guide](docs/ai_workflow_integration.md).

## Desktop application (legacy)

`video_editor_app.py` is the earlier Windows desktop interface (PySide6, ONNX person segmentation, bundled `ffmpeg.exe`, optional `models/u2net_human_seg.onnx`). It is no longer the development target. Its dependencies stay in `requirements.txt` and the Windows installer is described in the [download guide](docs/download_guide.md). The web editor shares the same `.ljproject` format and editing engine, so existing projects remain readable.

## Project structure

```text
.
├── web_app.py                 # Web editor: authenticated Flask app, editing API, AI Director routes
├── web_auth.py                # SQLite account store and validation
├── web/                       # Login, account-management, and editing interfaces
├── ai_workflow.py             # Reviewable AI plans: background analysis, apply and undo transactions
├── ai_story_planner.py        # Local scene analysis, cloud requests, narrative planning, continuity
├── edit_plan.py               # Edit-plan construction, validation, and application
├── creative_treatment.py      # Whole-video caption, motion, sound, and music choices
├── editing_preferences.py     # Preferences learned from user-edited timelines
├── video_editing_engine.py    # Project data, media probing, editing, and rendering
├── builtin_music.py           # Bundled music metadata and generation
├── builtin_sound_effects.py   # Bundled sound-effect metadata and generation
├── backend/                   # Optional FastAPI service: multi-project store + AI routes
├── ai_workflow_api.py         # FastAPI router used by backend/
├── video_editor_app.py        # Legacy desktop entry point
├── multitrack_timeline.py     # Legacy desktop timeline widgets
├── person_segmentation.py     # Legacy desktop person segmentation
├── assets/                    # Fonts, generated music loops, sound effects
├── docs/                      # Setup, design, release notes, component notices
├── examples/                  # Local sample projects and renders
├── tests/                     # Portable checks, web editor tests, FFmpeg rendering tests
├── requirements-web.txt       # Web editor dependencies
├── requirements-backend.txt   # Optional backend API dependencies
└── requirements.txt           # Legacy desktop dependencies
```

Start with `web_app.py` to follow the application workflow. AI planning runs through `ai_workflow.py`, `ai_story_planner.py`, and `edit_plan.py`; `video_editing_engine.py` owns the project operations and rendering commands. Files in `examples/` are local sample artifacts and may reference source media that is not included.

## Tests

Run the portable regression suite from the project root:

```sh
python tests/run_regression_tests.py
```

It covers edit-plan validation, automatic ordering, continuity, editing preferences, long-form sequencing, capture chronology, the project store (validation, atomic saves, revisions, backups), and the AI request flow. These checks use the Python standard library and a local mock API; they do not require a browser, a cloud key, or FFmpeg. The mock API needs permission to listen on the loopback interface.

The web editor and its AI Director are covered by `tests/test_web_app.py` (login, accounts, upload, timeline editing, export, AI plan preview/apply/undo, revision conflicts, privacy). The HTTP checks in `tests/test_backend_api.py` run when `fastapi` is installed and are skipped otherwise:

```sh
python -m pytest tests/test_web_app.py tests/test_ai_workflow.py tests/test_backend_api.py
```

With FFmpeg available, run the additional rendering checks from the project root:

```sh
python -m tests.test_video_editing_engine
python -m tests.test_transitions_and_masks
```

These generate test media and render actual output files. The portable suite does not replace rendering checks or a manual browser smoke test.

## Documentation

- [Integrated AI workflow and browser contract](docs/ai_workflow_integration.md)
- [Cloud API configuration](docs/cloud_ai_setup.md)
- [Backend API and project persistence](docs/backend_api.md)
- [Release notes](docs/release_notes.md)
- [Creative-treatment design](docs/creative_treatment_design.md)
- [Download and checksum (legacy desktop installer)](docs/download_guide.md)
- [Third-party components and licenses](docs/third_party_notices.md)
