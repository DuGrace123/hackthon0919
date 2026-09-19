# 第三方组件与研究说明

- Qt for Python / PySide6：LGPL/GPL/商业多许可证，桌面界面运行库。
- FFmpeg：按发布构建所包含组件的相应许可证使用，媒体探测、代理和渲染引擎。
- Kdenlive、Shotcut、OpenShot：仅研究公开仓库中的时间线职责划分和交互模式；灵剪 AI 未复制这些项目的源代码。
- OpenAI API：可选云端能力，由用户自行提供密钥并承担相应服务条款和用量；程序不捆绑密钥。
- U²-Net / `u2net_human_seg.onnx`：Apache License 2.0，本地人物分割模型；模型来源由 rembg 官方模型清单指向 U²-Net 项目。
- ONNX Runtime：MIT License，本地 CPU 模型推理运行时。
- NumPy：BSD-3-Clause；Pillow：HPND，用于帧矩阵与遮罩图像处理。
- ZCOOL KuaiLe、ZCOOL QingKe HuangYou、LXGW WenKai：SIL Open Font License 1.1。字体原文件与对应 `OFL-*.txt` 随程序分发。
- `assets/sfx` 新增音效与 `assets/music` 六首循环配乐由本项目使用数学波形确定性生成，不采样或包含第三方录音。
- Remotion、PySceneDetect、auto-editor：只研究其公开文档中关于可编程合成、场景边界和静音/节奏检测的通用方法；本程序未复制其源码。

相关项目与许可证请以其官方仓库为准：

- https://github.com/KDE/kdenlive
- https://github.com/mltframework/shotcut
- https://github.com/OpenShot/openshot-qt
- https://doc.qt.io/qtforpython-6/
- https://ffmpeg.org/
- https://developers.openai.com/api/docs/
- https://github.com/xuebinqin/U-2-Net
- https://github.com/danielgatis/rembg
- https://onnxruntime.ai/
- https://github.com/googlefonts/zcool-kuaile
- https://github.com/google/fonts/tree/main/ofl/zcoolqingkehuangyou
- https://github.com/lxgw/LxgwWenKai
- https://www.remotion.dev/docs
- https://www.scenedetect.com/docs/latest/
- https://github.com/WyattBlue/auto-editor

仓库中的完整许可证文本位于 `licenses/U2NET_LICENSE.txt`、`licenses/ONNXRUNTIME_LICENSE.txt`，字体 OFL 文本随对应字体资源保留。
