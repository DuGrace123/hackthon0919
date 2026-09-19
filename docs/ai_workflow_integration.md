# 成员 4：AI 工作流接入说明

本分支提供可独立测试的 AI 工作流和 FastAPI 路由，复用 `ai_story_planner.py`、`edit_plan.py`、`video_editing_engine.py`。现有桌面入口继续使用原流程。Web 主应用、工程存储、上传及前端由对应成员接入，本模块不创建另一套工程接口。

## 已实现的行为

- 本地模式：通过 FFmpeg 检测场景，按时长与拍摄顺序生成剪辑方案；不调用云端、不编造语音字幕。
- 云端模式：服务器生成联系图和压缩音频，调用现有 Responses/转写流程；必须先收到明确的 `cloud_consent: true`。
- 分析作为后台任务运行；生成过程中工程不变，只有确认应用时才提交一次工程事务。
- 浏览器只获得素材 ID、镜头入/出点、字幕、理由、转场和检查提醒，内部工程路径不出现在 AI API 响应中。
- 应用前检查原工程版本、素材内容标识及访问权限；期间有人工保存时返回 409，保护新修改。
- 应用会替换视频片段，清除与旧时间线位置绑定的叠加层和音效，保留背景音乐。预览的 `changes` 返回受影响数量，前端应在确认前展示。
- 应用后可撤销，恢复完整原工程；应用之后又有人工编辑时，撤销也返回 409，避免覆盖后续编辑。
- 支持任务查询、取消、队列上限、FFmpeg 超时和失败反馈。云端失败不会静默冒充本地结果，不自动重试收费请求。

## 成员 1：后端集成

安装可选路由依赖：

```sh
python -m pip install -r requirements-ai-web.txt
```

`ai_workflow.py` 本身只依赖标准库和现有工程模块，不需要 Qt、ONNX 或 FastAPI。

实现 `WorkflowBackend` 的三个方法：

| 方法 | 返回内容 | 要求 |
| --- | --- | --- |
| `get_project(project_id, owner_id)` | `ProjectSnapshot(project: Project, revision: int)` | 检查访问权限；返回独立快照，不能返回共享可变对象 |
| `resolve_media(project_id, media_id, owner_id)` | `MediaSource(id, path, name, duration, has_audio, capture_order)` | 检查素材属于当前用户/工程；用服务端记录解析路径，不接受客户端路径 |
| `commit_project(project_id, owner_id, project, expected_revision)` | 保存后的 `ProjectSnapshot` | **在同一事务或锁中比较版本并保存**；每次保存递增版本；冲突抛 `RevisionConflict()` |

找不到或无权访问的工程/素材应抛 `WorkflowError('not_found', '工程或素材不可用。', 404)`。不要在异常里带内部路径或密钥。如果后端以 `media_id` 为主键存储片段，由适配器负责转换到已有 `Project`/`Clip` 类型及恢复映射，不改变浏览器工程数据格式。

将生命周期和路由接入已有 FastAPI 主应用，代码示例如下（`project_backend`、`resolved_ffmpeg`、`require_user_id` 由主应用提供）：

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from ai_workflow import AIWorkflow, config_from_environment
from ai_workflow_api import create_ai_router

workflow = AIWorkflow(
    project_backend,
    resolved_ffmpeg,
    cloud_config=config_from_environment(),
)

@asynccontextmanager
async def lifespan(app):
    yield
    # 合并到已有 lifespan；停止服务时回收所有 AI 任务。
    workflow.close()

app = FastAPI(lifespan=lifespan)
app.include_router(create_ai_router(workflow, current_user=require_user_id))
```

`require_user_id` 必须返回已验证的用户身份；不可直接信任请求头或请求体中的用户 ID。主应用继续负责认证、CSRF、上传限制和素材生命周期。每次读方案及应用/撤销都会重新检查工程权限。

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

所有接口位于同一个主应用，沿用主应用会话认证。

| 请求 | 用途 |
| --- | --- |
| `GET /api/ai/capabilities` | 本地/云端可用性、限制与用户提示 |
| `POST /api/projects/{project_id}/ai/plans` | 创建分析任务，返回 202 |
| `GET /api/projects/{project_id}/ai/plans/{plan_id}` | 查询状态与镜头预览 |
| `POST /api/projects/{project_id}/ai/plans/{plan_id}/cancel` | 取消任务或放弃未应用方案 |
| `POST /api/projects/{project_id}/ai/plans/{plan_id}/apply` | 显式确认应用 |
| `POST /api/projects/{project_id}/ai/plans/{plan_id}/undo` | 撤销一次应用 |

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

`media_ids` 为 1–20 个不同的素材 ID，目标时长 5–180 秒，要求最多 2000 字符，每份源视频时长 0.5 秒–30 分钟。工程和素材 ID 限 ASCII 字母、数字、下划线、连字符，长度 1–128。

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

这是响应结构示例，数字不是运行结果。`shots` 按最终顺序排列，`start/end` 是相对原素材的秒数；预览播放地址由成员 2 的媒体接口通过 `media_id` 获取。`transition: none` 表示直接切换，其他值沿用已有剪辑引擎支持的转场。

前端应展示 `summary`、镜头清单、`warnings`、`repairs` 和 `changes` 后，才允许用户按“应用方案”。所有模型/素材文本按普通文本渲染，不插入 HTML。方案预览期间不要将 `shots` 直接写入正式时间线。

应用请求体为 `{"revision": 3, "confirm": true}`；服务端使用它保留的方案，不接受浏览器提交一份改写过的方案。成功响应带新 `revision`，随后通过成员 1 的工程读取接口刷新时间线。撤销请求体是应用成功响应中的版本，如 `{"revision": 4}`，成功后同样刷新工程。**若页面有未保存的人工编辑，应用/撤销前先提示用户处理这些修改**，因为服务端只能保护已经保存的版本。

可预期错误使用 `detail: {code, message}`，请求字段格式错误使用 FastAPI 标准 422 格式：

| 状态码/状态 | 界面行为 |
| --- | --- |
| 401 / 404 | 登录或提示工程/方案不可用，勿自动重新提交 |
| 409 `revision_conflict` / `media_changed` | 保留当前人工编辑，刷新后重新生成方案 |
| 422 `consent_required` | 显示上传内容/用量提示，让用户明确选择 |
| 429 `busy` | 告知任务已满，等待现有任务结束 |
| 503 `cloud_unavailable` | 提供本地模式选项 |
| `failed` | 展示 `error.message`；`retryable` 仅供提示，重试须由用户主动发起 |

## 运行边界与验证

本版本使用进程内计划缓存，默认 2 个工作线程、4 个排队名额、最多 100 份记录、方案保留 1 小时。**部署使用单个应用进程**；重启会丢失未应用方案和撤销记录，已保存工程由主存储保留。多进程/多副本部署前需将任务、方案与撤销事务迁移到共享持久化存储。

取消会立即禁止应用，并停止后续步骤；运行中的 FFmpeg 会被终止并回收。已发出的云端 HTTP 请求会等待返回或超时，取消不能撤回已上传的数据或供应商费用。本地模式使用低采样率场景规则，不能代替内容理解或逐句字幕对齐。

```sh
# 原有便携回归
python tests/run_regression_tests.py

# 新的工作流、路由和供应商边界检查；不访问付费服务
python -m pip install -r requirements-ai-web.txt httpx
python -m unittest tests.test_ai_workflow tests.test_ai_workflow_api tests.test_ai_provider tests.test_ai_media_analysis -v
```

真实媒体检查从 `FIGSTUDIO_TEST_FFMPEG` 或 PATH 查找 FFmpeg，也支持可选的 `imageio-ffmpeg`。缺失时明确跳过真实媒体部分。测试自动生成视频和音频，不使用用户素材。API 路由测试使用内存后端适配器；上线仍需对成员 1 的真实持久化适配器做集成验证。

本次验证包含生成真实视频后的本地分析、联系图/音频提取、素材变更缓存失效、应用和撤销；没有调用真实付费云端服务，也没有验证前端界面或完整 MP4 导出（这些属于另外成员的接入范围）。

实现参考了 OpenAI 官方 [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 的拒绝/未完成响应处理、[File transcription](https://developers.openai.com/api/docs/guides/speech-to-text) 的上传限制，以及 FastAPI 官方 [APIRouter 接入方式](https://fastapi.tiangolo.com/tutorial/bigger-applications/)。音频上限设为 24,000,000 字节，低于官方 25 MB 限制。
