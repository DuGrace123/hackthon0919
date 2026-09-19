**Version:** 4.13.0 · **Platform:** Windows 10 / 11 · **Source runtime:** Python 3.11+

[Download the Windows installer](https://github.com/MikeKang202210061/lingjian-ai-video-editor/releases/download/v4.13.0/LingJian-AI-Video-Editor-4.13.0-Windows-Setup.exe) · [Download details and checksum](docs/download_guide.md) · [Release notes](docs/release_notes.md)

## What you can do

| Area | Capabilities |
| --- | --- |
| Timeline editing | Source and program monitors, in/out points, insert and overwrite, trimming, splitting, ripple deletion, duplication, undo and redo. |
| Assisted assembly | Local scene and quality analysis, target-duration assembly, optional cloud content analysis, and capture-order and continuity checks. |
| Creative treatment | Editable captions, animated titles, transitions, masks, camera-motion effects, and independent overlay tracks. |
| Audio | Original audio, background music, dialogue ducking, six bundled music loops, and sixteen sound effects. |
| Person effects | Local U²-Net person segmentation with temporal smoothing and background blur, dimming, or color treatment. |
| Export | Portrait, landscape, and square MP4 presets using H.264/AAC, with preflight checks and output validation. |

Cloud AI is optional. Manual editing, local analysis, and rendering work without an API key. The desktop interface uses Chinese labels; the workflow below includes the labels you will see in the application.

## Web editing interface (Member 3)

The repository also includes a browser-based editing workspace backed by real local APIs. Its DaVinci-inspired layout places the media library on the left, the program monitor in the center, the clip inspector on the right, and video/audio tracks across the bottom. It covers timeline ordering, trim points, subtitles, transitions, project saving, and asynchronous MP4 export. Use the **EN / 中文** button to switch the entire interface between Chinese and English. Drag clips to reorder them, drag the horizontal divider to resize the timeline, and use the timeline zoom control for finer or broader timing views; language and layout settings are remembered in the browser.

```powershell
pip install -r requirements.txt
python web_app.py
```

Open `http://127.0.0.1:5000`. Uploaded media, the saved project, and exports are kept under `web_workspace/`. The server binds to localhost by default. The page includes empty, loading, success, and error states; uploaded originals remain in the media library when a timeline clip is removed.

On the first launch, the login page asks you to create the initial administrator account. There is no default username or password. Account records are stored in `web_workspace/accounts.sqlite3`; passwords are stored as one-way hashes, and authenticated write requests use a session-bound CSRF token. Administrators can open **账户管理 / Accounts** from the editor header to create editors or other administrators, change roles, enable or disable access, reset passwords, and delete accounts. The application prevents deletion or deactivation of the current user and the last active administrator.

## Get started

### Use the Windows installer

1. Download the **4.13.0 Windows installer** using the link above.
2. Check the file against the SHA-256 value in the [download guide](docs/download_guide.md).
3. Run the installer and launch LingJian.

The local distribution also includes the installer under `installer/`. A packaged installation does not require a separate Python environment.

### Run from source

Open PowerShell in this project's root directory, then run:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe video_editor_app.py
```

The application uses PySide6 for its interface, NumPy and Pillow for image processing, and ONNX Runtime for person segmentation. Dependency versions are defined in [requirements.txt](requirements.txt) and [pyproject.toml](pyproject.toml).

For media processing, LingJian first looks for `ffmpeg.exe` beside `video_editor_app.py`, then looks for `ffmpeg` on `PATH`. The local distribution includes the Windows executable. Keep the `assets/` and `models/` folders at the project root so the application can find its resources.

## Make your first video

1. **Import footage.** Click **＋ 导入** and select video or audio files. Add the clips you want to work with using **添加到时间线**. Difficult video formats may need a proxy before previewing smoothly.
2. **Choose how to assemble it.** Edit directly on the timeline, or open **AI 导演** and set the target duration, story style, and editing instructions. The three assisted options are described below.
3. **Review the proposal.** Inspect the proposed clip sequence, captions, effects, and audio treatment. Apply the plan to the timeline when it is ready; the resulting clips remain editable and the application supports undo.
4. **Refine the timeline.** Adjust cuts, captions, transitions, overlays, and audio. Use **学习当前人工时间线** if you want later plans to take your editing preferences into account.
5. **Save and export.** Save a `.ljproject` file to keep editing later. Under **音频与导出**, select an output preset, run **导出前质量检查**, and choose **导出 MP4**.

Project files store editing decisions and media paths. Keep the original media available at those paths when reopening a project.

| Option in AI 导演 | What it does | Requires a cloud key |
| --- | --- | --- |
| 快速节奏方案 | Builds a quick assembly from clips already on the timeline. | No |
| 离线分析并预览完整方案 | Analyzes local scenes and technical quality, then proposes a sequence. | No |
| 生成完整方案并预览高级开头 | Uses cloud content analysis and narrative planning, then presents a reviewable edit plan. | Yes |

## Optional cloud analysis

Open **AI 接口**, enter the service URL, API key, visual model, and transcription model, then select **加密保存接口设置**. Start cloud analysis explicitly from **AI 导演**.

The configured service must support the request formats used by this application: `/v1/responses` with image input and structured JSON output, and `/v1/audio/transcriptions` for audio transcription. Model names must match models available through your provider. See [cloud API setup](docs/cloud_ai_setup.md) for configuration details.

During a cloud analysis run, the application sends generated contact sheets and extracted audio, along with your editing instructions and analysis context, to the configured service. Rendering and project editing remain local. On Windows, API keys are protected with the current user's DPAPI credentials and stored in application settings; they are not saved in project files.

## Optional person-segmentation model

Person effects use the following model file:

```text
models/u2net_human_seg.onnx
```

The local distribution includes this file. If you obtain the source without it, supply the model separately and verify it against `MODEL_SHA256` in [person_segmentation.py](person_segmentation.py). Other editing features remain available without the model.

Model files, installers, and generated videos are excluded by `.gitignore`, so a source checkout may not include them. Component notices and model licenses are listed in [third-party notices](docs/third_party_notices.md).

## Project structure

```text
.
├── video_editor_app.py        # Desktop entry point and workflow coordination
├── multitrack_timeline.py     # Media list and interactive timeline widgets
├── video_editing_engine.py    # Project data, media analysis, editing, and rendering
├── ai_story_planner.py        # Cloud requests, narrative planning, and continuity
├── edit_plan.py               # Edit-plan construction, validation, and application
├── creative_treatment.py      # Whole-video caption, motion, sound, and music choices
├── editing_preferences.py     # Preferences learned from user-edited timelines
├── person_segmentation.py     # Local person segmentation and tracking
├── web_app.py                 # Authenticated local web editor and API
├── web_auth.py                # SQLite account store and validation
├── web/                       # Login, account-management, and editing interfaces
├── builtin_music.py           # Bundled music metadata and generation
├── builtin_sound_effects.py   # Bundled sound-effect metadata and generation
├── assets/
│   ├── fonts/                 # Bundled fonts and their licenses
│   ├── music/                 # Generated music loops
│   └── sfx/                   # Generated sound effects
├── docs/                      # Setup, release notes, design, and component notices
├── examples/
│   ├── projects/              # Local sample editing projects
│   └── renders/               # Existing sample render outputs
├── installer/                 # Local Windows installer
├── licenses/                  # Third-party license texts
├── models/                    # Optional segmentation model
├── tests/                     # Portable checks and FFmpeg rendering tests
├── ffmpeg.exe                 # Bundled Windows media-processing executable
├── pyproject.toml             # Project metadata and dependency constraints
└── requirements.txt           # Dependencies for running from source
```

Start with `video_editor_app.py` to follow the application workflow. Assisted editing runs through `ai_story_planner.py`, `edit_plan.py`, and `creative_treatment.py`; `video_editing_engine.py` owns the project operations and rendering commands. Files in `examples/` are local sample artifacts. Sample projects may reference source media that is not included.

## Tests

Run the portable regression suite from the project root:

```powershell
python tests/run_regression_tests.py
```

It covers edit-plan validation, automatic ordering, continuity, editing preferences, long-form sequencing, capture chronology, and the AI request flow. These checks use the Python standard library and a local mock API; they do not require a GUI, a cloud key, or FFmpeg. The mock API needs permission to listen on the loopback interface.

On Windows with FFmpeg available, run the additional rendering checks from the project root:

```powershell
python -m tests.test_video_editing_engine
python -m tests.test_transitions_and_masks
```

These generate test media and render actual output files. The portable suite does not replace rendering checks or a manual desktop smoke test.

## Documentation

- [Download and checksum](docs/download_guide.md)
- [Cloud API configuration](docs/cloud_ai_setup.md)
- [Release notes](docs/release_notes.md)
- [Creative-treatment design](docs/creative_treatment_design.md)
- [Third-party components and licenses](docs/third_party_notices.md)
