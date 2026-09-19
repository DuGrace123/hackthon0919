# 后端接口与工程保存

后端把编辑引擎的工程能力封装为 HTTP 接口：创建、读取、保存、删除工程。工程以 `.ljproject` JSON 文件保存在服务器的 `workspace/projects/` 目录中，桌面版可以直接打开这些文件。

## 启动

```powershell
python -m pip install -r requirements-backend.txt
python -m backend
```

默认监听 `http://127.0.0.1:8000`，交互式接口文档在 `http://127.0.0.1:8000/docs`。

| 环境变量 | 默认值 | 说明 |
| --- | --- | --- |
| `LINGJIAN_HOST` | `127.0.0.1` | 监听地址 |
| `LINGJIAN_PORT` | `8000` | 监听端口 |
| `LINGJIAN_WORKSPACE` | `./workspace` | 工程文件根目录，首次启动自动创建 |
| `LINGJIAN_CORS_ORIGINS` | `*` | 允许的前端来源，逗号分隔 |

## 接口

所有路径以 `/api/v1` 开头，请求与响应均为 JSON。

| 方法 | 路径 | 请求体 | 成功 | 失败 |
| --- | --- | --- | --- | --- |
| GET | `/health` | – | `{status, version, workspace}` | – |
| GET | `/projects` | – | 工程摘要列表 | – |
| POST | `/projects` | `{title?, ratio?, project?}` | 201 工程记录 | 422 |
| GET | `/projects/{id}` | – | 200 工程记录 | 400 / 404 / 500 |
| PUT | `/projects/{id}` | `{revision, project}` | 200 工程记录（新 revision） | 400 / 404 / 409 / 422 |
| DELETE | `/projects/{id}` | – | 204 | 400 / 404 |

**工程记录**（`GET` / `POST` / `PUT` 的响应）：

```json
{
  "id": "3f1c2b6a9d8e4f70a1b2c3d4e5f60718",
  "revision": 3,
  "created_at": "2026-09-19T03:20:11Z",
  "updated_at": "2026-09-19T03:41:52Z",
  "recovered_from_backup": false,
  "project": { "version": 5, "title": "...", "clips": [ ... ], ... }
}
```

**工程摘要**（`GET /projects` 的每一项）：`id, title, revision, updated_at, clip_count, duration, recovered_from_backup`，按 `updated_at` 倒序。

### 示例

```bash
# 创建
curl -X POST http://127.0.0.1:8000/api/v1/projects -H 'Content-Type: application/json' -d '{"title":"我的旅行 Vlog"}'

# 读取
curl http://127.0.0.1:8000/api/v1/projects/<id>

# 保存：把读取时拿到的 revision 带回，project 是完整工程内容
curl -X PUT http://127.0.0.1:8000/api/v1/projects/<id> -H 'Content-Type: application/json' \
  -d '{"revision":1,"project":{"title":"改名","clips":[{"path":"D:/footage/a.mp4","start":0,"end":2.5}]}}'

# 导入桌面版工程文件
curl -X POST http://127.0.0.1:8000/api/v1/projects -H 'Content-Type: application/json' \
  -d "{\"project\": $(cat 我的作品.ljproject)}"
```

## 保存冲突（乐观锁）

1. 读取工程时记住响应中的 `revision`。
2. 保存时把它作为请求体的 `revision` 传回；成功后服务器返回新的 `revision`，前端用它替换本地值。
3. 如果其他人已经保存过，服务器返回 **409**，`detail.current` 是服务器当前的完整记录：

```json
{
  "detail": {
    "code": "revision_conflict",
    "message": "工程已被其他人修改：你基于 revision 1，服务器当前是 revision 2",
    "expected": 1,
    "current": { "id": "...", "revision": 2, "project": { ... } }
  }
}
```

前端可以用 `detail.current` 重新加载，或者把本地改动合并到它之上后再保存（带 `revision: 2`）。服务器不会覆盖任何一方的改动。

## 刷新后工程仍在

工程只保存在服务器文件中，不依赖浏览器状态。建议前端在每次修改后防抖（例如 800 ms）调用 `PUT`，页面刷新后用 URL 中的工程 `id` 调用 `GET /projects/{id}` 即可恢复到最近一次保存。

## 异常保存不损坏旧文件

- 写入先落到同目录临时文件，`fsync` 后用 `os.replace` 原子替换，任何时刻主文件要么是完整旧版、要么是完整新版，中途崩溃只会留下旧版。
- 每次成功保存前，上一版复制为 `<id>.ljproject.bak`。
- 如果主文件损坏（例如磁盘异常），`GET` 会自动返回备份并把 `recovered_from_backup` 置为 `true`。恢复出来的内容按**新版本**计（revision 比损坏前大），持有损坏前 revision 的客户端保存会得到 409，需要重新读取；之后的保存不会用损坏的文件覆盖这份备份。
- 桌面版 `Project.save()` 也改用同一套原子写。

## 外部改写（桌面版直接编辑 workspace 里的文件）

revision、时间戳和工程内容的指纹保存在 `<id>.meta.json` 中，而不只在 `.ljproject` 的信封字段里。桌面版打开 `workspace/projects/<id>.ljproject` 并原地另存时会去掉信封字段，后端读取时发现内容指纹与上次写入不一致，就把它当作一个**更新的 revision**（+1）：持有旧 revision 的网页端保存会得到 409，不会覆盖桌面端的改动；`created_at` 也不会被重置。

局限：连续两次外部改写之间如果没有经过后端读取，后端无法把它们区分开。

## 输入校验

`POST` 与 `PUT` 中的 `project` 会逐字段校验，并规范化为 version 5 的完整结构（缺省字段补默认值，旧版本文件自动升级）。校验失败返回 **422**，`detail.errors` 一次列出所有问题：

```json
{
  "detail": {
    "code": "invalid_project",
    "message": "clips[0].end: 出点必须大于入点（共 2 个问题）",
    "errors": [
      { "path": "clips[0].end", "message": "出点必须大于入点" },
      { "path": "clips[0].transition", "message": "不支持的值 'nope'，允许：..." }
    ]
  }
}
```

规则：未知字段拒绝；必填字段缺失拒绝；类型按定义检查（数字字段不接受布尔值和字符串）；数字必须是有限值（`NaN`、`Infinity`、`1e9999` 这类会解析成无穷的字面量，以及绝对值超过 1e15 的数都拒绝），`edit_plan` / `edit_log` 内部嵌套的数字同样如此；枚举字段只接受下表列出的值；`title_fill_segments` 每项只允许 `path`（必填）、`start`（≥ 0）、`duration`（> 0）、`name`；`clips/overlays/sfx` 内 `id` 不能重复，缺省时自动生成。`version` 大于 5 的工程拒绝。

## 访问边界

- 工程 `id` 由服务器生成（32 位小写十六进制），请求中的 `id` 必须完全匹配该格式，否则返回 **400** `invalid_project_id`；`../`、绝对路径、大小写变体都会被拒绝，请求永远不会触及 `workspace/projects/` 之外的文件。
- 片段中的素材 `path` 只作为字符串保存，服务器不读取它，也不检查它是否存在。

## 错误码

| HTTP | `detail.code` | 含义 |
| --- | --- | --- |
| 400 | `invalid_project_id` | 工程 ID 格式不正确 |
| 404 | `project_not_found` | 工程不存在 |
| 409 | `revision_conflict` | revision 已过期，`detail.current` 为服务器当前记录 |
| 422 | `invalid_request` | 请求信封格式错误（缺少 `revision` 等），`detail.errors` 列出字段 |
| 422 | `invalid_project` | 工程内容无效，`detail.errors` 列出每个问题 |
| 500 | `project_corrupt` | 主文件与备份都无法读取 |

## 工程数据结构（version 5）

数据结构由 [video_editing_engine.py](../video_editing_engine.py) 中的 dataclass 定义，后端不另建模型。未列出取值范围的字段只检查类型。

### Project

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `version` | int | 5 | 工程格式版本，≤ 5 可导入，保存后总是 5 |
| `title` | str | `未命名作品` | ≤ 120 字 |
| `ratio` | str | `9:16` | 画幅比例，格式 `宽:高` |
| `clips` | Clip[] | `[]` | 主视频轨（V1），按顺序拼接 |
| `overlays` | OverlayClip[] | `[]` | 叠加轨 V2–V8 |
| `sfx` | SFXCue[] | `[]` | 音效 |
| `bgm` | str | `""` | 背景音乐文件路径 |
| `bgm_id` | str | `""` | 内置音乐 ID |
| `bgm_volume` | float | 0.22 | 0–2 |
| `bgm_ducking` | bool | true | 人声闪避 |
| `bgm_fade_in` / `bgm_fade_out` | float | 1 / 2 | 秒，0–60 |
| `prompt` | str | `""` | 用户给 AI 的剪辑指令 |
| `edit_plan` | object | `{}` | AI 方案原文 |
| `edit_log` | object[] | `[]` | 编辑记录，保存时只保留最近 100 条 |

### Clip（主轨片段）

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `path` | str | 必填 | 素材路径 |
| `start` / `end` | float | 必填 | 素材内入点/出点（秒），`0 ≤ start < end` |
| `id` | str | 自动 | 工程内唯一 |
| `name` | str | `""` | 显示名 |
| `has_audio` | bool | true | |
| `volume` | float | 1.0 | 0–2 |
| `caption` | str | `""` | 字幕，≤ 120 字 |
| `position` | str | `bottom` | `top` `center` `lower_third` `bottom` |
| `caption_font` | str | `微软雅黑` | |
| `caption_size` | int | 42 | 1–400 |
| `caption_color` / `caption_bg` | str | `#FFFFFF` / `#000000` | |
| `caption_bg_opacity` | float | 0.55 | 0–1 |
| `caption_effect` | str | `clean` | `clean` `jelly` `kinetic` `typewriter` `stamp` `pop` `highlight` `minimal` |
| `transition` | str | `fade` | `none` `fade` `dissolve` `wipe_left` `wipe_right` `slide_left` `slide_right` `circle` `smooth` `pip_zoom` `tear_left` `tear_right` `pixelize` `squeeze` `radial` `fade_black` `fade_white` `cover_left` `reveal_right` |
| `transition_duration` | float | 0.35 | 秒，0.05–2 |
| `motion_effect` | str | `none` | `none` `slow_push` `punch_in` `handheld` |
| `mask_shape` | str | `none` | `none` `spotlight` `ellipse` `portrait_card` `cinema` `diamond` `vertical_strip` `split_left` `split_right` `privacy_blur` `vignette` |
| `mask_x` / `mask_y` | float | 0.5 | 0–1 |
| `mask_width` / `mask_height` | float | 0.72 | (0, 1] |
| `mask_feather` | float | 18 | ≥ 0 |
| `mask_opacity` | float | 1 | 0–1 |
| `title_effect` | str | `""` | `""` `bounce` `text_window` |
| `title_text` | str | `""` | ≤ 120 字 |
| `title_color` | str | `#FFFFFF` | |
| `title_fill_segments` | object[] | `[]` | `text_window` 用的填充素材，每项 `{path（必填）, start ≥ 0, duration > 0, name}` |
| `person_effect_path` | str | `""` | 人物效果预渲染文件 |
| `person_effect_start` / `person_effect_end` | float | 0 | ≥ 0 |
| `person_effect_mode` | str | `""` | `""` `blur` `dim` `color` |
| `role` / `reason` / `capture_order` | str | `""` | AI 方案元数据 |
| `ai_selected` | bool | false | |

### OverlayClip（叠加片段）

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `path` | str | 必填 | 素材路径 |
| `start` / `end` | float | 必填 | 素材内入点/出点，`0 ≤ start < end` |
| `timeline_start` | float | 必填 | 在成片时间线上的起点（秒），≥ 0 |
| `track` | int | 2 | 2–8 |
| `id` / `name` | str | 自动 / `""` | |
| `layout` | str | `pip_right` | `pip_right` `pip_left` `center` `full` |
| `mask_shape` | str | `ellipse` | `none` `ellipse` `circle` |
| `x` / `y` | float | 0.76 / 0.26 | 中心位置，0–1 |
| `width` / `height` | float | 0.36 / 0.30 | (0, 1] |
| `feather` | float | 10 | ≥ 0 |
| `opacity` | float | 1 | 0–1 |
| `border` | bool | true | |
| `role` / `reason` | str | `overlay` / `""` | |
| `ai_selected` | bool | false | |

### SFXCue（音效）

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `path` | str | 必填 | 音效文件路径 |
| `start` | float | 必填 | 时间线位置（秒），≥ 0 |
| `id` / `name` | str | 自动 / `""` | |
| `volume` | float | 0.65 | 0–2 |
| `effect_id` | str | `""` | 内置音效 ID |

## 存储布局

```
workspace/
└── projects/
    ├── <id>.ljproject        # 当前版本：信封字段 + version 5 工程内容
    ├── <id>.ljproject.bak    # 上一次保存前的版本
    └── <id>.meta.json        # revision、时间戳、内容指纹（并发控制的权威来源）
```

`.ljproject` 顶层多出 `id`、`revision`、`created_at`、`updated_at` 四个字段，桌面版打开时会忽略它们；它们只是 `.meta.json` 的副本，方便人工查看。

## 测试

```powershell
python tests/run_regression_tests.py
```

`tests/test_project_store.py` 覆盖校验、乐观锁、原子写、备份恢复、ID 边界、并发与桌面版兼容；`tests/test_backend_api.py` 覆盖 HTTP 状态码、错误体、CORS 与重启后读取，未安装 fastapi 时自动跳过。
