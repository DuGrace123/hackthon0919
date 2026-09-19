# 使用指南维护

- 网页：`/guide`，无需登录；登录页、剪辑台和账户管理页均有入口。
- 下载：`/guide/download`，返回一页中文 PDF 附件。
- 内容源：`web/user_guide.json`。网页读取它，PDF 也由它生成，避免两份说明分别修改。
- 当前内容适用于 `render.yaml` 中的免费演示站：50 MB 上传请求上限、临时文件系统、共享工程。更换存储或上传配置后请同步说明。

修改 JSON 后，在开发环境安装 `reportlab` 并运行：

```sh
python scripts/build_user_guide.py
```

提交生成的 `web/static/guides/lingjian-quick-start.pdf`。PDF 使用仓库已有的 LXGW WenKai 字体，授权见 `assets/fonts/OFL-LXGWWenKai.txt`。`reportlab` 仅用于维护文档，无需加入服务器依赖。

生成后用 PDF 阅读器检查仍是一页，文字没有溢出。运行既有 Web 回归测试，再检查 `/guide` 的手机布局、各页面的入口与下载响应。网页链接在新标签页打开，不中断当前剪辑会话。

## 发布规则

Render 跟踪 `main`，配置为 `autoDeployTrigger: checksPass`。自动部署还要求通过 Git Provider 连接本仓库；只有设置部署选项、但未完成 GitHub 仓库授权时，不会自动更新。连接完成后，PR 合并且主分支的 GitHub Actions 全部通过才触发构建。个人分支更新和未合并的 PR 不会更新正式网站。

如果 Deploys 页面没有出现新部署，在确认 `main` 的检查通过后，使用 `Manual Deploy → Deploy latest commit` 发布。不要用 `Deploy a specific commit` 代替，它会关闭自动部署。发布成功后域名不变。

2026-09-19 发布指南时，控制台的 Git Provider 显示 `No repositories found`，因此本次使用手动发布。后续应在 Render 的 Settings → Build → Source 中连接仓库，并在下一次主分支更新时验证自动触发。

当前免费实例的上传、工程、账户及网页保存的 AI 设置都在临时文件系统。重新部署会丢失这些数据，上线前应告知团队并下载需要保留的成片。参见 [Render 自动部署](https://render.com/docs/deploys#automatic-deploys) 与 [免费服务限制](https://render.com/docs/free)。
