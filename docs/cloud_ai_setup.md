# Cloud AI setup

Cloud analysis is optional. Configure a service only if you want content analysis and narrative planning through a cloud model. Manual editing, quick assembly, offline analysis, and rendering remain available without an API key.

## Configure the service

1. Launch LingJian and open the **AI 接口** tab on the right.
2. Enter the service's root URL in **接口地址**. The application's default is `https://api.openai.com`. The application appends `/v1/` when constructing requests, so the root URL should not already end in `/v1`.
3. Enter your API key.
4. Set **视觉模型** and **转写模型** to model IDs enabled by your provider. The source defaults are `gpt-5-mini` and `gpt-4o-mini-transcribe`; their availability depends on the configured service and your account.
5. Select **加密保存接口设置**.
6. Import video and add it to the timeline. Open **AI 导演**, enter your editing instructions, and choose a story style and target duration.
7. Select **生成完整方案并预览高级开头** to start cloud analysis.
8. Review the resulting edit plan before applying it to the timeline.

## Required API compatibility

The application uses both of these endpoints:

| Endpoint | Required support |
| --- | --- |
| `POST /v1/responses` | Image input and structured JSON output using JSON Schema. |
| `POST /v1/audio/transcriptions` | Multipart audio upload and transcription. |

A service that only implements Chat Completions does not support this application's current request flow. A proxy or private gateway must preserve the endpoint paths and expected request formats.

## Data and credentials

Cloud analysis sends generated contact sheets, extracted audio, editing instructions, and analysis context to the configured service. Requests consume that service's account usage. The original video is processed locally to produce the analysis inputs; local rendering does not call the cloud API.

On Windows, the API key is protected using DPAPI for the current user and saved in application settings. Project files do not contain the API key.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| HTTP 401 or 403 | Verify the API key, account permissions, and service URL. |
| Model unavailable | Replace the model ID with one enabled for the chosen service and account. |
| Wrong endpoint or unsupported request | Use the service root URL and confirm support for both endpoints above. |
| Analysis is slow | The first run must extract audio and contact sheets. Multiple source clips are analyzed in sequence. |
| You want local processing only | Use **快速节奏方案** or **离线分析并预览完整方案** in **AI 导演**. |

Return to the [project README](../README.md) for installation and the complete editing workflow.
