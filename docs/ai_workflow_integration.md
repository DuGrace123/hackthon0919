# 成员 1 + 成员 4：工程存储与 AI 工作流接入说明

`python -m backend` 现在同时提供成员 1 的工程存储和成员 4 的 AI 工作流，统一使用 `/api/v1`。`backend/ai_adapter.py` 将方案应用、撤销接到真实 `ProjectStore`，已保存的修改能在服务重启后重新打开。网页编辑器 `web_app.py` 已把同一套工作流挂到自己的素材库和工程上（见下文「网页编辑器接入」），这是唯一的产品界面；桌面入口不再是开发目标。

## 网页编辑器接入（已实现）

`web_app.py` 直接实例化 `AIWorkflow`，用 `EditorAIBackend` 实现 `WorkflowBackend`：工程是网页编辑器内存中的单一工程（固定 ID `workspace`），素材来自网页上传目录的服务端目录记录，浏览器永远不提交路径。所有路由都经过现有的登录、会话与 CSRF 检查，`owner_id` 取当前登录账户，因此一个账户生成的方案对其他账户不可见。

| 请求 | 用途 |
| --- | --- |
| `GET /api/ai/capabilities` | 本地/云端可用性、限制与用户提示 |
| `GET /api/ai/sources` | 可参与 AI 剪辑的视频素材（音频文件不列出）与当前 `revision` |
| `GET /api/ai/plans` | 当前账户未过期的方案列表（最新在前），页面刷新后据此恢复进行中、待确认或已应用的方案 |
| `POST /api/ai/plans` | 创建分析任务（`media_ids`、`revision`、`mode`、`target_duration`、`prompt`、`cloud_consent`），返回 202 |
| `GET /api/ai/plans/{plan_id}` | 查询状态与镜头预览 |
| `POST /api/ai/plans/{plan_id}/cancel` | 取消任务或放弃未应用方案 |
| `POST /api/ai/plans/{plan_id}/apply` | `{"revision": n, "confirm": true}`，成功时同时返回 `plan` 和最新工程状态 |
| `POST /api/ai/plans/{plan_id}/undo` | `{"revision": n}`，恢复应用前的完整工程 |
| `GET /api/admin/ai-config` | 管理员：当前云端配置（密钥只返回是否已设置和掩码提示）、来源（网页设置 / 环境变量 / 未配置）、云端是否可用 |
| `PUT /api/admin/ai-config` | 管理员：保存接口地址（仅 HTTPS）、API Key（留空沿用已保存密钥）、视觉模型、转写模型、超时，保存后立即生效 |
| `DELETE /api/admin/ai-config` | 管理员：删除网页保存的配置，回退到环境变量或仅本地模式 |
| `POST /api/admin/ai-config/test` | 管理员：用提交的配置（密钥可省略）请求服务商 `/v1/models`，返回是否连通及模型名是否存在 |

版本规则：`GET /api/project` 返回的 `project.revision` 在每次实际改动（加片段、裁剪、字幕、转场、排序、删除、改标题或画幅）后加一；仅重复提交相同标题/画幅不会加一，所以「保存工程」不会让待应用的方案失效。生成方案时带上当前 `revision`；应用时若工程已被手工修改则返回 409 `revision_conflict`，方案不会覆盖它没见过的编辑。应用成功后工程会立即原子写入 `web_workspace/project.ljproject`，并在 `edit_log` 追加 `apply_ai_plan`；撤销同样落盘。AI 片段带 `ai_selected: true`，时间线以「AI」标签显示，片段编辑接受 `edit_plan.ALLOWED_TRANSITIONS` 中的全部转场，因此 AI 片段可以继续手工修改。

错误响应统一为 `{"error": "<提示>", "code": "<错误码>"}`，状态码与本文「成员 3：浏览器接口」一节相同。

云端配置由管理员在「账户管理 → AI 接口」中填写，服务端以 `protect_secret` 保存到 `web_workspace/ai_settings.json`（Windows 为 DPAPI，其他系统为 0600 权限文件），优先于「服务端云端配置」一节的环境变量；`AIWorkflow.configure_cloud()` 在保存后即时切换配置，进行中的任务沿用启动时的配置。密钥不回传浏览器、不写入工程文件，编辑成员账户无法读取或修改。未配置时 `capabilities.cloud_available` 为 `false`，面板中的云端选项会被禁用并提示管理员前往配置。

`tests/test_web_app.py::AIServiceSettingsTests` 覆盖：未配置状态、保存后云端可用且密钥掩码与文件保护、重启后保留、HTTP/缺密钥/超时校验、连接测试沿用已保存密钥并核对模型名、清除回退、环境变量回退、编辑成员 403。`tests/test_web_app.py::AIDirectorTests` 用假分析器覆盖：能力与素材列表、预览不改工程、应用落盘、撤销恢复、手工编辑后 409、无改动 PATCH 不影响方案、确认与版本校验、取消、音频素材拒绝、云端同意与可用性、AI 转场可编辑、跨账户不可见与未登录 401。

## 已实现的行为

- 本地模式：通过 FFmpeg 检测场景，按时长与拍摄顺序生成剪辑方案；不调用云端、不编造语音字幕。
- 云端模式：服务器生成联系图和压缩音频，调用现有 Responses/转写流程；必须先收到明确的 `cloud_consent: true`。
- 分析作为后台任务运行；生成过程中工程不变，只有确认应用时才提交一次工程事务。
- 浏览器只获得素材 ID、镜头入/出点、字幕、理由、转场和检查提醒，内部工程路径不出现在 AI API 响应中。
- 应用前检查原工程版本、工程内容标识、素材内容标识及访问权限；期间有人工保存时返回 409，保护新修改。内容标识还能区分复用同一版本号的连续外部文件改写。
- 应用会替换视频片段，清除与旧时间线位置绑定的叠加层和音效，保留背景音乐。预览的 `changes` 返回受影响数量，前端应在确认前展示。
- 应用后可撤销，恢复完整原工程；应用之后又有人工编辑时，撤销也返回 409，避免覆盖后续编辑。
- 支持任务查询、取消、队列上限、FFmpeg 超时和失败反馈。云端失败不会静默冒充本地结果，不自动重试收费请求。

## 启动统一后端

在仓库根目录，使用 Python 3.11+：

```sh
python -m pip install -r requirements-backend.txt
python -m backend
```

访问 `http://127.0.0.1:8000/docs` 查看工程和 AI 接口，`GET /api/v1/health` 的 `ai` 字段返回本地/云端可用性。只运行后端不需要安装 Qt 或 ONNX；`ai_workflow.py` 本身只依赖标准库和现有工程模块。

FFmpeg 查找顺序：`LINGJIAN_FFMPEG` 显式配置、Windows 仓库中的 `ffmpeg.exe`、系统 PATH、可选的 `imageio-ffmpeg`。没有系统 FFmpeg 时可运行 `python -m pip install imageio-ffmpeg`。找不到时工程接口仍可用，AI 能力返回不可用。

这是**本机单用户联调服务**：默认监听 `127.0.0.1:8000`，AI 接口同时检查本机来源地址与 Host。浏览器来源默认允许 `http://localhost:5173` 和 `http://127.0.0.1:5173`；其他开发端口通过逗号分隔的 `LINGJIAN_CORS_ORIGINS` 配置，不支持 `*`。后端自身 `/docs` 的同源请求也可访问。工程接口尚无多用户账号隔离；公网部署前需要对应成员实现认证、工程/素材归属与共享任务存储。

## 成员 2：当前素材桥接方式

上传服务尚未接入时，将测试视频放进 `workspace/media/`（或 `LINGJIAN_WORKSPACE` 指定目录下的 `media/`），在工程 `clips` 或 `overlays` 中引用它。相对路径从 workspace 根目录解析，例如 `media/demo.mp4`；绝对路径必须仍落在同一个 media 目录中。目录外文件、指向目录外的软链接和不支持的视频格式不会进入 AI 素材列表。

例如，对一段至少 5 秒的视频，先调用 `POST /api/v1/projects`：

```json
{"project":{"title":"AI 联调","clips":[{"path":"media/demo.mp4","start":0,"end":5}]}}
```

再用返回的工程 ID 调用 `GET /api/v1/projects/{project_id}/ai/sources`：

```json
{
  "items": [{"id":"<media_id>","name":"demo.mp4","duration":8,"has_audio":true}],
  "unavailable": [],
  "revision": 1
}
```

`duration` 和 `has_audio` 来自实际 FFmpeg 探测，示例数字仅用于说明格式。前端创建 AI 任务时使用 `items[].id`，**不能把 clip ID 或路径当成 media ID**。当前 ID 是规范化相对路径的摘要；重复引用同一视频只返回一项，`unavailable` 用于显示失效引用。

媒体成员接入上传目录后，应让 `ProjectStoreAIBackend` 从统一素材目录/索引解析媒体归属和路径，并复用媒体接口提供的预览地址；不需要修改 AI 请求格式。本次没有新增上传、媒体播放或导出接口。

## 后端适配约定

已实现的 `ProjectStoreAIBackend` 遵循以下 `WorkflowBackend` 协议；未来替换数据库或账号系统时保留这些约定：

| 方法 | 返回内容 | 要求 |
| --- | --- | --- |
| `get_project(project_id, owner_id)` | `ProjectSnapshot(project, revision, version_token)` | 检查访问权限；返回独立快照，不能返回共享可变对象 |
| `resolve_media(project_id, media_id, owner_id)` | `MediaSource(id, path, name, duration, has_audio, capture_order)` | 检查素材属于当前用户/工程；用服务端记录解析路径，不接受客户端路径 |
| `commit_project(project_id, owner_id, project, expected_revision, expected_token=...)` | 保存后的 `ProjectSnapshot` | **在同一事务或锁中比较版本、内容标识并保存**；冲突抛 `RevisionConflict()` |

找不到或无权访问的工程/素材应抛 `WorkflowError('not_found', '工程或素材不可用。', 404)`。不要在异常里带内部路径或密钥。如果后端以 `media_id` 为主键存储片段，由适配器负责转换到已有 `Project`/`Clip` 类型及恢复映射，不改变浏览器工程数据格式。

`backend/api.py:create_app()` 已负责实例化服务、挂载 `create_ai_router(..., prefix='/api/v1')`，并在 lifespan 结束时关闭 AI 工作线程。当前适配器将本机访问映射为一个 workspace 身份；多用户版本的身份依赖必须来自已验证的会话，不可直接信任请求体或任意身份请求头。每次读方案及应用/撤销都会重新检查工程权限。

工程与元数据分两次写入。如果工程文件已经成功替换、元数据写入失败，适配器会重新读取并核对完整工程和新 revision；能够确认本次提交时仍正确记录 applied/undone，避免把已生效方案当作未应用方案。无法确认时返回 503，前端应刷新工程后再处理。

## 服务端云端配置

| 环境变量 | 默认值 |
| --- | --- |
| `FIGSTUDIO_AI_API_KEY` | 空；不配置即可使用本地模式 |
| `FIGSTUDIO_AI_BASE_URL` | `https://api.openai.com` |
| `FIGSTUDIO_AI_MODEL` | `gpt-5-mini` |
| `FIGSTUDIO_AI_TRANSCRIPTION_MODEL` | `gpt-4o-mini-transcribe` |

模型默认值沿用项目原配置，实际可用性取决于服务账号。`config_from_environment()` 设置单次云端请求超时为 60 秒。可通过服务端传入 `APIConfig` 调整到 1–180 秒；Web 工作流仅接受服务端配置的 HTTPS 端点。地址既可不带 `/v1`，也可包含 `/v1`；有鉴权的请求不会跟随 HTTP 重定向。

密钥只进入服务端配置对象，`repr(APIConfig)` 隐藏密钥，前端请求不接受 `api_key`、接口地址或模型覆盖。云端上传包括抽帧联系图、提取音频、用户要求和分析上下文。Responses 请求设置 `store: false`，这并不代表供应商承诺零数据保留。错误响应不转发供应商原始响应体。临时音频和联系图在任务结束后删除。

## 成员 3：浏览器接口

所有接口位于同一个主应用，当前访问条件见“启动统一后端”。

| 请求 | 用途 |
| --- | --- |
| `GET /api/v1/ai/capabilities` | 本地/云端可用性、限制与用户提示 |
| `GET /api/v1/projects/{project_id}/ai/sources` | 当前工程可用素材 ID、失效引用与工程版本 |
| `POST /api/v1/projects/{project_id}/ai/plans` | 创建分析任务，返回 202 |
| `GET /api/v1/projects/{project_id}/ai/plans/{plan_id}` | 查询状态与镜头预览 |
| `POST /api/v1/projects/{project_id}/ai/plans/{plan_id}/cancel` | 取消任务或放弃未应用方案 |
| `POST /api/v1/projects/{project_id}/ai/plans/{plan_id}/apply` | 显式确认应用 |
| `POST /api/v1/projects/{project_id}/ai/plans/{plan_id}/undo` | 撤销一次应用 |

创建之前先保存当前工程，使用保存响应中的版本号。创建请求：

```json
{
  "media_ids": ["media-1", "media-2"],
  "revision": 3,
  "mode": "local",
  "target_duration": 30,
  "prompt": "按真实拍摄顺序，保留关键动作和结尾",
  "cloud_consent": false
}
```

`media_ids` 为 sources 接口返回的 1–20 个不同素材 ID，目标时长 5–180 秒，要求最多 2000 字符，每份源视频时长 0.5 秒–30 分钟。统一后端的工程 ID 为服务器生成的 32 位小写十六进制字符串。

立即返回任务：

```json
{
  "id": "<plan_id>",
  "project_id": "<project_id>",
  "base_revision": 3,
  "mode": "local",
  "status": "queued",
  "progress": 0,
  "message": "等待分析",
  "result": null,
  "error": null
}
```

建议每 1 秒轮询一次，在离开页面或进入终态时停止轮询。状态变化：

```text
queued → running → ready → applied → undone
   └─────────┴──────┴──→ cancelled
queued / running → failed
```

`ready.result` 包含：

```json
{
  "shots": [{
    "id": "<decision_id>", "media_id": "media-1", "name": "旅行.mp4",
    "start": 0, "end": 3.5, "role": "hook", "caption": "",
    "reason": "本地镜头", "transition": "none", "has_audio": true
  }],
  "duration": 3.5,
  "summary": "共 1 个镜头，预计 3.5 秒",
  "changes": {
    "replace_video_clips": 6, "remove_overlays": 2,
    "remove_sound_effects": 1, "preserve_background_music": true
  },
  "warnings": ["方案短于目标时长"],
  "repairs": [],
  "capture_order_locked": true
}
```

这是响应结构示例，数字不是运行结果。`shots` 按最终顺序排列，`start/end` 是相对原素材的秒数；预览播放地址待成员 2 的媒体接口接入。字幕在预览和落盘前统一限制为 120 字，与工程存储约束一致。`transition: none` 表示直接切换，其他值沿用已有剪辑引擎支持的转场。

前端应展示 `summary`、镜头清单、`warnings`、`repairs` 和 `changes` 后，才允许用户按“应用方案”。所有模型/素材文本按普通文本渲染，不插入 HTML。方案预览期间不要将 `shots` 直接写入正式时间线。

应用请求体为 `{"revision": 3, "confirm": true}`；服务端使用它保留的方案，不接受浏览器提交一份改写过的方案。成功响应带新 `revision`，随后通过成员 1 的工程读取接口刷新时间线。撤销请求体是应用成功响应中的版本，如 `{"revision": 4}`，成功后同样刷新工程。**若页面有未保存的人工编辑，应用/撤销前先提示用户处理这些修改**，因为服务端只能保护已经保存的版本。

可预期错误使用 `detail: {code, message}`；统一后端的请求格式错误返回 422 `detail: {code: "invalid_request", message, errors}`。AI 的 409 不附带完整工程，应重新调用工程 GET 接口读取：

| 状态码/状态 | 界面行为 |
| --- | --- |
| 401 / 404 | 登录或提示工程/方案不可用，勿自动重新提交 |
| 403 `local_only` / `origin_not_allowed` | 检查本机访问地址或服务端允许的前端来源配置 |
| 409 `revision_conflict` / `media_changed` | 保留当前人工编辑，刷新后重新生成方案 |
| 422 `consent_required` | 显示上传内容/用量提示，让用户明确选择 |
| 429 `busy` | 告知任务已满，等待现有任务结束 |
| 503 `cloud_unavailable` | 提供本地模式选项 |
| 503 `ffmpeg_unavailable` | 安装 FFmpeg 或设置 `LINGJIAN_FFMPEG` |
| 503 `save_failed` | 刷新工程，确认磁盘和当前版本后再处理 |
| `failed` | 展示 `error.message`；`retryable` 仅供提示，重试须由用户主动发起 |

## 运行边界与验证

本版本使用进程内计划缓存，默认 2 个工作线程、4 个排队名额、最多 100 份记录、方案保留 1 小时。**部署使用单个应用进程**；重启会丢失未应用方案和撤销记录，已保存工程由主存储保留。多进程/多副本部署前需将任务、方案与撤销事务迁移到共享持久化存储。

取消会立即禁止应用，并停止后续步骤；运行中的 FFmpeg 会被终止并回收。已发出的云端 HTTP 请求会等待返回或超时，取消不能撤回已上传的数据或供应商费用。本地模式使用低采样率场景规则，不能代替内容理解或逐句字幕对齐。

```sh
# 原有便携回归
python tests/run_regression_tests.py

# 新的工作流、路由和供应商边界检查；不访问付费服务
python -m pip install -r requirements-backend.txt httpx imageio-ffmpeg
python -m unittest tests.test_ai_workflow tests.test_ai_workflow_api tests.test_ai_provider tests.test_ai_media_analysis tests.test_backend_ai_integration -v
```

真实媒体检查从 `FIGSTUDIO_TEST_FFMPEG` 或 PATH 查找 FFmpeg，也支持可选的 `imageio-ffmpeg`。缺失时明确跳过真实媒体部分。测试自动生成视频和音频，不使用用户素材。

`tests/test_backend_ai_integration.py` 使用真实 ProjectStore、挂载后的 HTTP 路由和 FFmpeg，覆盖工程创建、素材解析、本地分析、应用落盘、重新读取、撤销、人工保存冲突、备份恢复、连续外部改写、路径/来源限制、120 字字幕、磁盘写入失败以及重启后的方案失效。没有调用真实付费云端服务，也没有验证前端界面或完整 MP4 导出（这些属于另外成员的接入范围）。

实现参考了 OpenAI 官方 [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 的拒绝/未完成响应处理、[File transcription](https://developers.openai.com/api/docs/guides/speech-to-text) 的上传限制，以及 FastAPI 官方 [APIRouter 接入方式](https://fastapi.tiangolo.com/tutorial/bigger-applications/)。音频上限设为 24,000,000 字节，低于官方 25 MB 限制。
