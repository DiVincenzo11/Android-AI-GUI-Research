# v0.1.0 验证记录

验证日期：2026-11-01。Windows 11、Python 3.12、Android Emulator / Android 15（API 35）。这是本机执行记录，不代表所有平台或应用已验证。

- 干净 Python 虚拟环境安装便携包与测试依赖成功，13 项测试通过。覆盖 XML 解析、密码/编辑框排除、跨包及越界目标、歧义选择器、父容器误点击、ADB 转义、新旧回答区分、失败证据及完整工作流。
- 三个真实历史应用案例的离线分析入口实际执行。Otter / Perplexity 的 AI 身份文字被记录；Brave 无响应与 Perplexity 登录门槛保留为未完成输出验证。
- 独立测试 APK 使用 Android SDK Build Tools 36.0.0、Platform android-37.0、JDK 21 编译与签名成功。
- 新建隔离测试模拟器运行测试 APK；自动发现 AI Assistant 按钮、进入、填写带随机 nonce 的测试输入、提交、识别新目标文本均通过。分别执行原生 UI 版本与原生 UI + RapidOCR 版本，保留完整阶段截图、XML、节点、JSONL、HTML、录屏与 SHA-256 清单。
- 首次设备联调暴露并修正了 Android 15 的窗口焦点查询差异、EditText 将占位符暴露为文字的问题，以及全屏可点击容器误当入口的问题。早期失败结果保留于本机工作目录；公开首版的成功路径不作为首次尝试成功率。

实际记录：`artifacts/live-fixture/` 与 `artifacts/live-fixture-ocr/`。其中 SIMULATED 回答是测试 APK 的确定性文本，**不是第三方应用的模型生成结果**。真实 Android 操作与录屏不能证明 AI 模型性能。

默认测试与 CI 无需 ADB。GitHub Actions 配置了 Windows/Linux、Python 3.10/3.12；工作流是否通过应查看 GitHub 实际状态，不能把已添加配置等同于已完成云端验证。

已验证 RapidOCR 1.4.4 的 CPU 图像识别；未验证 Tesseract 外部引擎、中文 IME 输入、物理手机、跨应用大规模冻结基准或完整 ScenGen 原模型复现。
