# 真实应用实验：准备与复跑

本轮是三个真实应用的适配与证据采集实验，非自主探索或跨应用准确率基准。固定的应用版本、APK 哈希、模型哈希与实际环境见 `artifacts/real-apps-v0.2.0/`。不要把调试后选出的案例当成首次尝试通过率。

## 依赖和设备

Python 3.10+，Android SDK Platform Tools；本轮实际使用 Windows / Python 3.12 / Android Emulator API 35，x86_64 系统带 arm64 翻译能力，4 GiB 模拟器内存。不是物理手机测试。启动原有研究模拟器时遇到未解锁状态，后改用独立测试 AVD，没有清空原模拟器数据。

```shell
python -m pip install -e ".[device,ocr,test]"
adb devices -l
```

指定 `--ui-backend uiautomator2` 时会连接并可能部署该驱动的 Android 端组件，固定 Python 版本为 3.5.2，`waitForIdleTimeout=0`、`waitForSelectorTimeout=0`、dump max_depth=100。系统 shell dump 在流式输出和 WebView 动画中可能取不到树，不能把取树失败解释为模型未回复。

本轮 Duck.ai 提交后发生一次模拟器退出；恢复后使用软件渲染并禁用 Vulkan，后续流程完成。记录了恢复配置，但没有确认崩溃的根本原因，不能仅凭恢复成功归因于 Vulkan。若自己的模拟器稳定，不必照搬渲染参数。

## 下载应用和本地模型

仅从 `apk-provenance.json` 中的官方 Release 下载 APK，并核对 SHA-256。本仓库不分发 APK。注意 ChatterUI 的应用内版本是 **0.10.1**，对应上游 **v0.10.0 Release** 中的 `ChatterUI_v0.10.1.apk`，两者名称不同。

PocketPal 和 ChatterUI 使用同一个模型：

- 仓库：`Qwen/Qwen2.5-0.5B-Instruct-GGUF`
- revision：`9217f5db79a29953eb74d5343926648285ec7e67`
- 文件：`qwen2.5-0.5b-instruct-q4_k_m.gguf`
- 大小：491,400,032 bytes
- SHA-256：`74a4da8c9fdbcd15bd1f6d01d621410d31c6fc00986f5eb687824e7b93d7a9db`

按官方许可从 Hugging Face 获取，模型不包含在本仓库中。下载到电脑后可以 `adb push <模型文件> /sdcard/Download/`，再在两个应用的本地文件选择器中导入。模型准备是人工配置，不算自动发现能力。

## PocketPal 1.20.0

先跳过首次介绍，导入唯一的上述 GGUF 文件。回到无待发送文本的 Chat 页面。适配器会点击 **Select Pal → Models → 指定 GGUF**，在目标包内完成加载，然后输入和提交。

```shell
aigui --adb /path/to/adb --ui-backend uiautomator2 run --serial emulator-5556 --config examples/real-apps/pocketpal.json --out runs/pocketpal-01 --ocr --record
```

PocketPal 进入后台可能释放模型，聊天标题仍可能保留模型名。只看到标题不能认定模型就绪。加载后的输入框应为空或显示已声明的 `Type your message here`；出现“模型未加载”会被拒绝继续。回答必须来自 `ai-message` 容器中的非编辑文本。

## ChatterUI 0.10.1

导入同一 GGUF，保持 Local 模式；确保只有一个模型。保留默认的 AI Bot / User 名称，因为适配器使用这些实际 UI 标签归属回答。

从仅有一个 AI Bot 的聊天列表开始，可自动进入、打开菜单、加载模型并返回聊天：

```shell
aigui --adb /path/to/adb --ui-backend uiautomator2 run --serial emulator-5556 --config examples/real-apps/chatterui-cold-start.json --out runs/chatterui-01 --ocr --record
```

如果已经手动加载好模型并位于聊天页，可改用 `examples/real-apps/chatterui.json`。前者的图标选择器使用该版本实际暴露的 Unicode 字形，换版本可能失效；这属于版本固定的适配器，不是图标语义理解。模型/上下文加载可能耗时，不能用首屏可见代替就绪检查。

## DuckDuckGo 5.300.0 / Duck.ai

手动完成浏览器首次介绍并开启可选 Duck.ai 入口。本轮拒绝通知权限、取消默认浏览器更改、跳过桌面小组件；没有登录账号或购买订阅。

手动打开新的 Duck.ai 对话，使原生输入框可见。第一轮输入后按钮为 `nativeInputAskButton`，续聊为 `nativeInputSubmitButton`；提供两个明确配置，不猜测未知按钮：

```shell
# 新对话第一轮；空输入框提示为 Ask anything privately…
aigui --adb /path/to/adb --ui-backend uiautomator2 run --serial emulator-5556 --config examples/real-apps/duckduckgo-first-chat.json --out runs/duck-first --ocr --record
# 已有对话的后续轮次；空输入框提示为 Reply…
aigui --adb /path/to/adb --ui-backend uiautomator2 run --serial emulator-5556 --config examples/real-apps/duckduckgo.json --out runs/duck-reply --ocr --record
```

点击发送会按应用本身规则向联网服务提交合成测试文本，并可能应用其显示的条款。执行器不会自动处理登录、验证码、权限或额外确认弹窗；遇到这些情况应保留记录后停止。联网服务、区域和页面版本变化可能使流程不可用。记录的模型名称只来自可见界面，没有独立认证服务端模型身份。

最终回答使用同一气泡祖先下的 **Duck.ai said** 标签归属，并排除带 **You said** 的共同聊天容器。本轮后续适配器按此角色约束重新执行通过。

## 批量执行与失败保存

每个配置都要求文档约定的起始页面已经就绪。批处理不会重置应用数据、准备模型、登录或自动完成首次介绍；请先分别核对页面和版本。

```shell
python scripts/run_real_app_suite.py --adb /path/to/adb --ui-backend uiautomator2 --serial emulator-5556 --configs examples/real-apps/pocketpal.json examples/real-apps/chatterui.json examples/real-apps/duckduckgo.json --out runs/real-suite --ocr --record
aigui verify runs/real-suite/01-pocketpal
```

目录必须不存在。失败也写 `result.json`、观察记录、HTML 和 SHA-256；批处理继续下一项，最后有任何案例未通过则返回退出码 2。设备完全断开等前置错误可能使批处理不能继续，不能据此推断未执行案例的状态。安装/升级 Python 包前先结束正在使用同一虚拟环境的 `aigui.exe`，Windows 会锁住运行中的启动器。

如果只想记录一个已知入口而不测试回答，可以用 `scripts/probe_real_entry.py`。它明确标记 `new_output_verified=false`，不能把入口探测成功当作 AI 生成成功。

## 本版适配字段

- `entry: "already_open"`：明确表示已处于功能页，不声称自动识别了入口；`entry` 也支持原有 exact selector 和 `discover`。
- `entry_steps`：最多 8 次目标包内的精确点击，每次等待不超过 10 秒。`if_present` 仅允许跳过零匹配，多个匹配仍失败。
- `input_placeholders`：至多 8 个明确已观察到的占位符；只允许空输入或声明的占位符，不覆盖未知已有内容。
- `response.ancestor`：回答文本必须属于指定的原生祖先容器。
- `response.role`：回答所在祖先必须包含指定标签，且不能包含排除标签，避免把整个聊天列表当成回答容器。
- `stable_polls: 2`：需要两次实际采集到相同回答；仍不保证模型完全停止生成。

回答还必须包含本轮随机 nonce 和预期文本、在提交前不存在，并排除包含完整提示词的回显。拒绝回传 nonce、引用整段提示词或尚未暴露角色节点的真实回答可能被保守漏判。该检查验证新目标文本，不是模型能力、后端身份、透明度合规或科研准确率的证明。
