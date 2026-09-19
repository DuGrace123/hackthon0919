# 通过公网访问灵剪

这份部署运行完整的 Flask 网页、FFmpeg 和 AI 后台任务，平台提供 HTTPS 网址，访问者无需在自己的电脑启动程序。GPT API 是可选的 AI 服务，不承担网站托管。

当前是**一个团队共用一个工作区**：管理员创建账户后，所有已登录成员可以看到和修改同一份工程与素材。这适合五人团队协作演示；尚不适合让陌生用户分别保存私人项目。网址可以分享，素材与编辑 API 仍需登录。

## 选择托管方案

| 方案 | 配置文件 | 用途与限制 |
| --- | --- | --- |
| Render 免费演示（默认） | 仓库根目录 `render.yaml` | 免费实例会休眠，素材和账户在休眠、重启或更新后丢失。上传限制 50 MB，先用几秒钟的小视频测试，512 MB 内存不保证复杂导出成功。 |
| Render 持久化 | `deploy/render-persistent.yaml` | 1 核 / 2 GB，5 GB 磁盘，素材、账户、保存的工程和已完成导出可跨重启保留。基础费用约 $26.25/月，额外流量另计。 |
| 已有云服务器 | `Dockerfile` | 使用同一镜像，提供持久化卷、HTTPS 反向代理和进程管理即可。 |

价格核对日期：2026-09-19。[Render 定价](https://render.com/pricing)中 1 核 / 2 GB 为 $25/月，磁盘为 $0.25/GB/月。创建服务前以控制台报价为准；仓库中的配置文件本身不会购买资源。GPT API 用量由 AI 服务商另行计费。

普通 Vercel Functions 的请求/响应上限为 4.5 MB，并有执行时长限制。当前项目依赖本地素材、SQLite、进程内工程状态和后台渲染线程，不能直接把它作为函数部署。若将来必须使用 Vercel，需另外接入对象存储、数据库和后台视频服务，见 [Vercel 限制](https://vercel.com/docs/functions/limitations)。

## 在 Render 创建服务

1. 登录 [Render 控制台](https://dashboard.render.com/)，打开 [免费演示部署入口](https://render.com/deploy?repo=https://github.com/DuGrace123/hackthon0919)。也可选择 **New → Blueprint**，关联 GitHub 仓库 `DuGrace123/hackthon0919`，分支选 `main`。
2. 默认使用 `render.yaml` 的免费演示方案；如果明确需要付费持久化，再选择 `deploy/render-persistent.yaml`。核对实例、磁盘和费用后创建。无需另外部署 FastAPI，也无需填写前端构建命令。
3. 等待 Docker 构建及健康检查通过，在服务页面打开平台实际分配的 `https://….onrender.com` 地址。可先访问 `/api/health`，确认 `export_ready` 为 `true`。
4. 在服务的 **Environment** 中查看平台自动生成的 `LINGJIAN_SETUP_TOKEN`。在网站首次设置页输入该初始化密钥，再由管理员设置自己的用户名和密码。不要把初始化密钥、会话密钥或 AI API key 放进 Git、聊天或网址。
5. 管理员进入 **账户管理**，为四位组员创建各自的编辑者账户，再分享网址。初始化完成后无法再次通过设置页创建管理员；持久化方案可以移除 `LINGJIAN_SETUP_TOKEN`，免费方案应保留它以便数据重置后重新初始化。
6. 如需 GPT，在 **账户管理 → AI 接口** 中填写现有服务的 HTTPS 地址、API key、视觉模型及转录模型并测试连接。每次云端分析仍需用户确认。页面中的“本地分析”指在托管服务器运行 FFmpeg，不调用外部 AI；导入的素材本身仍会上传到该服务器。

生成的 `LINGJIAN_SECRET_KEY` 要在后续部署中保持不变，否则现有登录会失效。Render 自动为服务网址提供 HTTPS；生产模式的 Cookie 带 `Secure`，因此不要通过普通 HTTP 公网访问。

## 启动与存储

容器运行 `gunicorn --config gunicorn.conf.py web_app:app`，监听 `0.0.0.0:$PORT`（默认 10000）。**保持单实例、单 worker**，用线程处理并发请求；多进程会让当前工程、AI 方案和导出任务各有一份状态。每次只允许一个视频导出，避免多人同时渲染耗尽小实例内存。

| 配置项 | 说明 |
| --- | --- |
| `LINGJIAN_ENV=production` | 启用安全 Cookie、启动密钥检查及隐藏内部异常详情。 |
| `LINGJIAN_SECRET_KEY` | 至少 32 字符的随机会话密钥，持久保存。 |
| `LINGJIAN_SETUP_TOKEN` | 首次创建管理员所需的随机密钥，至少 32 字符。 |
| `LINGJIAN_WEB_WORKSPACE` | 持久化方案为 `/var/data/lingjian`；整个 `/var/data` 挂载磁盘。 |
| `LINGJIAN_MAX_UPLOAD_MB` | 单次请求总上传上限；持久化方案 512 MB，免费演示 50 MB。 |
| `PORT` | 由托管平台设置，Gunicorn 自动读取。 |

目录包含 `accounts.sqlite3`、`uploads/`、`exports/`、`media_catalog.json`、`project.ljproject` 和管理员保存的 AI 设置。镜像不会打包本地工作区、素材、账户或 `.env`。Linux 字幕使用仓库已有的开源中文字体。

普通编辑需要点击**保存**后才会跨重启保留；AI 应用会保存工程。正在运行的导出和 AI 方案位于内存中，重启后需重新生成。已完成的导出文件保留在磁盘，当前界面没有跨重启的导出历史列表，原下载地址仍然可用。部署前先保存工程并等待渲染完成。

GitHub Actions 会构建 Linux 镜像、执行网页回归测试，并启动真实 Gunicorn 完成带中文字幕的 MP4 导出和重启恢复验证。Render 配置为 `checksPass`，仅在 `main` 的检查通过后自动部署。挂载持久化磁盘的服务在部署时有短暂中断。

## 已有服务器运行方式

先在服务器的受限环境文件中配置上述生产密钥，避免放进命令历史。示例文件路径 `/etc/lingjian.env` 应由服务器管理员创建并设置 `chmod 600`，其中包含 `LINGJIAN_SECRET_KEY`、`LINGJIAN_SETUP_TOKEN`。

```sh
docker build -t lingjian-web .
docker volume create lingjian-data
docker run -d --name lingjian-web --restart unless-stopped \
  --env-file /etc/lingjian.env \
  -p 127.0.0.1:10000:10000 \
  -v lingjian-data:/var/data \
  lingjian-web
```

由 Nginx 或 Caddy 将公开的 HTTPS 站点代理到 `127.0.0.1:10000`，同时设置与应用匹配的上传大小和超时。定期在停止写入时备份整个工作区；SQLite、素材和工程文件需保持一致。磁盘不是无限空间，5 GB 仅适合小型演示素材，后续应补充清理、配额和备份流程。

## 验证

```sh
python -m pip install -r requirements-deploy.txt
python -m unittest discover -s tests -p 'test_web*.py'
python tests/cloud_smoke.py
```

`cloud_smoke.py` 使用独立临时目录与一次性测试凭据，不接触真实工作区或调用 GPT。部署后还应在公网 HTTPS 地址实测登录、上传、剪辑、导出，并让一位组员用自己的账户访问。

参考：[持久化磁盘](https://render.com/docs/disks)、[免费方案限制](https://render.com/docs/free)、[Blueprint 配置](https://render.com/docs/blueprint-spec)。
