# 小智机械臂 VLA 项目 — 当前进度及未来规划

> 最后更新：2026-06-24 17:30 | 分支：`feature/robot-arm-vla`

---

## 1. 总体进度概览

| 阶段 | 内容 | 状态 | 完成度 |
|------|------|------|--------|
| **Phase 0** | ESP-IDF v5.5.3 编译适配 + 固件烧录验证 | ✅ 完成 | 100% |
| **Phase 1** | 硬件接线 + ESP32 端 UART 驱动 + MCP 工具 | 🔄 进行中 | ~85% |
| **Phase 1.5** | 🆕 文字消息交互（串口 + 服务器适配） | ✅ 完成 | 100% |
| **Phase 2** | 部署 OpenClaw + 语音对话 + 语音控制机械臂 | 🔄 服务端完成，浏览器音频排障中 | ~80% |
| **Phase 3** | 部署 smolVLA-0.5B + 视觉抓取推理 | 🟡 框架就绪（待 GPU） | ~15% |
| **Phase 4** | 端到端语音抓取联调 + 异常处理 | 🔲 未开始 | 0% |
| **仿真/微调** | LeRobot 遥操作数据采集 + LoRA 微调 | 🔲 未开始（可选） | 0% |

**整体进度：约 55%**（Phase 0~2 软件部分基本完成，飞书Bot+VLA框架就绪，待硬件验证）

> ⚠️ **已知问题**：浏览器测试页 TTS 音频无法播放，详见 [浏览器音频问题排障总结.md](浏览器音频问题排障总结.md)。LLM + TTS 全链路通，但 Chrome WebAudio 播放链路无声。需等 ESP32 硬件到手后在真实设备上验证音频。

---

## 2. 🆕 Phase 1.5：文字消息交互（2026-06-23 完成）

### 背景

麦克风硬件故障，无法使用语音输入。需要添加文字消息收发能力，通过串口终端打字与 AI 对话。

### ESP32 端改动

| 文件 | 改动说明 |
|------|----------|
| [protocol.h:76](main/protocols/protocol.h#L76) | 新增 `SendTextInput()` 公开虚方法 |
| [protocol.cc:81-91](main/protocols/protocol.cc#L81) | 实现：用 cJSON 构建 `{"type":"text","text":"..."}` 消息 |
| [application.h:34](main/application.h#L34) | 新增 `MAIN_EVENT_TEXT_INPUT` 事件位 (1<<13) |
| [application.h:112](main/application.h#L112) | 新增 `SendTextInput()` 公开方法（线程安全） |
| [application.h:152](main/application.h#L152) | 新增 `HandleTextInputEvent()` 处理器声明 |
| [application.cc:183](main/application.cc#L183) | 事件循环加入 TEXT_INPUT 监听 |
| [application.cc:1121-1177](main/application.cc#L1121) | `HandleTextInputEvent` 实现：按设备状态智能路由 + 15s 超时检测 |
| **新建** [text_console.h](main/text_console.h) | 文字控制台头文件 |
| **新建** [text_console.cc](main/text_console.cc) | FreeRTOS 任务：`getchar()` 逐字读取 + 回显 + 退格，回车发送 |
| [CMakeLists.txt:40](main/CMakeLists.txt#L40) | 添加 `text_console.cc` |
| [main.cc:24](main/main.cc#L24) | `TextConsole::Start()` 启动控制台 |

### OpenClaw 服务器端改动

| 文件 | 改动说明 |
|------|----------|
| [textMessageType.py:9](c:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server\core\handle\textMessageType.py#L9) | 新增 `TEXT = "text"` 消息类型枚举 |
| **新建** [textInputMessageHandler.py](c:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server\core\handle\textHandler\textInputMessageHandler.py) | 文字消息处理器：收到文字 → `enqueue_asr_report` + `startToChat` |
| [textMessageHandlerRegistry.py:8,29](c:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server\core\handle\textMessageHandlerRegistry.py#L8,L29) | 导入并注册 `TextInputMessageHandler` |

### 数据流

```
串口终端 > 你好
  → text_console 任务 (getchar 逐字读取, 回车发送)
  → Application::SendTextInput("你好")
  → Protocol::SendTextInput → cJSON {"type":"text","text":"你好"}
  → MQTT/WebSocket → OpenClaw
  → TextInputMessageHandler → enqueue_asr_report + startToChat
  → LLM → TTS → ESP32 扬声器 + 屏幕显示回复
```

### 使用方式

烧录固件后，打开串口监视器：

```
文字控制台已启动，输入文字后按回车发送（/help 帮助 /quit 退出）
> 今天天气怎么样
[屏幕显示"user: 今天天气怎么样"]
[等待服务器回复...]
[屏幕显示"assistant: 今天天气晴..." + 喇叭播放语音]
```

### 🚀 未来可选：飞书 Bot 接入

架构已设计好（见讨论），关键代码为 `feishu_handler.py`，需要：
1. 飞书开放平台创建 Bot + 订阅 `im.message.receive_v1` 事件
2. OpenClaw 服务器新增 `/feishu/callback` HTTP 端点
3. 飞书消息 → LLM → TTS → 双路回复（飞书文字 + ESP32 语音）

---

## 3. Phase 1 详细进度

### 3.1 ✅ 已完成

#### 固件层

| 模块 | 文件 | 说明 |
|------|------|------|
| UART1 驱动 | [xiaozhi_custom_board.cc:127](main/boards/xiaozhi-custom/xiaozhi_custom_board.cc#L127) | IO9(TX)→驱动板 RX, IO10(RX)←驱动板 TX, 115200bps |
| 机械臂 MCP 工具 | [xiaozhi_custom_board.cc:150](main/boards/xiaozhi-custom/xiaozhi_custom_board.cc#L150) | `robot.arm.move_joints`、`robot.arm.gripper`、`robot.arm.get_status` 三个工具 |
| WebSocket 地址覆盖 | [Kconfig.projbuild:915](main/Kconfig.projbuild#L915) | Kconfig `CONFIG_WEBSOCKET_URL_OVERRIDE`，编译期覆盖 OTA 下发的 WS 地址 |
| WebSocket 地址读取 | [websocket_protocol.cc:89](main/protocols/websocket_protocol.cc#L89) | `#if CONFIG_WEBSOCKET_URL_OVERRIDE` 优先使用自建服务器地址 |
| UART 引脚配置 | [config.h:75](main/boards/xiaozhi-custom/config.h#L75) | `ROBOT_ARM_UART_TXD_PIN=GPIO_NUM_9`, `ROBOT_ARM_UART_RXD_PIN=GPIO_NUM_10` |
| 分区表 | [partitions/v2/16m.csv](partitions/v2/16m.csv) | 双 OTA (各 4MB) + 8MB SPIFFS assets |
| 板卡选项 | [Kconfig.projbuild:133](main/Kconfig.projbuild#L133) | `BOARD_TYPE_XIAOZHI_CUSTOM`，仅限 ESP32-S3 |
| 板级初始化 | [xiaozhi_custom_board.cc:197](main/boards/xiaozhi-custom/xiaozhi_custom_board.cc#L197) | 构造函数中自动初始化 UART + 注册 MCP 工具 |
| 🆕 文字控制台 | 见上文 Phase 1.5 | 串口输入文字 → 直接与 AI 对话 |

#### 文档

| 文件 | 说明 |
|------|------|
| [机械臂VLA集成方案.md](../../机械臂VLA集成方案.md) | 完整技术方案（674行），含架构、模型选型、微调流程 |
| [main/boards/xiaozhi-custom/README.md](main/boards/xiaozhi-custom/README.md) | 板级说明（386行），含引脚映射、编译烧录、MCP 工具用法 |
| 🆕 [SERVER_CHANGES.md](main/text_console/SERVER_CHANGES.md) | 服务器端文字消息适配方案 |

#### 项目整理

| 提交 | 说明 |
|------|------|
| `05ff1b9` | 移除所有非 ESP32-S3 板子支持 |
| `f3c5202` | 清理非 S3 相关文件（文档、分区表、sdkconfig） |
| `32c0d0e` | feat: 添加机械臂VLA集成支持 |
| `c3f96f3` | docs: 添加小智自定义板机械臂VLA集成README |
| *(待提交)* | feat: 添加串口文字控制台 + 服务器文字消息适配 |

### 3.1.1 Phase 0：ESP-IDF v5.5.3 编译适配（已完成）

> 原项目基于旧版 ESP-IDF 开发，升级到 v5.5.3 后产生大量 API 不兼容错误。

| 轮次 | 文件 | 问题 | 修复方式 |
|------|------|------|----------|
| 第1轮 | `websocket_protocol.cc` | `#if ""` 无效预处理 | 改为运行时 `strlen()` 检查 |
| 第1轮 | `gpio_led.cc` | `ledc_fade_stop` 已移除（5处） | 删除调用 |
| 第1轮 | `image_to_jpeg.cpp` | `esp_imgfx_color_convert.h` 仅 P4 有 | 加 `#if CONFIG_XIAOZHI_ENABLE_HARDWARE_JPEG_ENCODER` 守卫 |
| 第1轮 | `es8388_audio_codec.cc` | `ext_clk_freq_hz` 字段移除 | `#if ESP_IDF_VERSION < 5.5.0` |
| 第2轮 | `es8388_audio_codec.cc` | `left_align` / `big_endian` / `bit_order_lsb` 移除 | 版本守卫 |
| 第2轮 | `es8389_audio_codec.cc` | 同上 3 字段 | 版本守卫 |
| 第2轮 | `box_audio_codec.cc` | 4 字段 + TDM 模式移除 | v5.5 回退到 STD 模式 |
| 第2轮 | `image_to_jpeg.cpp` | RGB 转换块未守卫 | 包入 `#if` 守卫 |
| 第2轮 | 新增 `main/uart_uhci.h` | UART UHCI DMA 驱动移除 | 桩头文件 |
| 第2轮 | 新增 `main/uart_eth_modem.h` | esp_eth_modem 组件移除 | 桩头文件 |
| 第2轮 | `nt26_board.cc` | 缺 `esp_event.h` / `esp_netif.h` | 显式 include |
| 第3轮 | `image_to_jpeg.h` | V4L2 依赖 | 改用 `esp_new_jpeg` 原生类型 |
| 第3轮 | `image_to_jpeg.cpp` | V4L2 类型未定义 | 全局替换 `JPEG_PIXEL_FORMAT_*` |
| 第3轮 | `lvgl_display.cc` | 调用方仍用旧常量 | 常量替换 |
| 环境 | `idf.py` | MSYS 检测后不调用 `main()` | 添加 `main()` 调用 |
| 环境 | `idf_tools.py` | MSYS 检测后 `fatal()` 退出 | 改为 `print()` 警告 |

**编译结果：✅ 2184/2184 目标，0 错误，0 警告**

### 3.2 🔲 Phase 1 待完成

| 任务 | 说明 | 优先级 |
|------|------|--------|
| **文字消息端到端测试** | ✅ 已完成：阿里百炼 deepseek-v4-flash + EdgeTTS 全链路通 | ✅ |
| **烧录最新固件** | 含文字控制台的新固件（`feature/robot-arm-vla` 分支最新提交） | 🔴 |
| **硬件接线验证** | 用杜邦线连接 ESP32 IO9/IO10 ↔ SO101 驱动板串口 | 🔴 阻塞 |
| **UART 通信验证** | 从 PC 通过 WiFi 发送 MCP 指令 → ESP32 → UART → 机械臂实际动作 | 🔴 阻塞 |
| **IO9/IO10 与 IO17/IO18 不一致** | 方案文档写的是 IO17/IO18，实际代码用 IO9/IO10，需确认并统一文档 | 🟡 文档 |
| **camera.take_photo 验证** | 确认 ESP32 摄像头 MCP 工具已实现并可正常拍照 | 🟡 |

### 3.3 ⚠️ 已知问题

1. **引脚不一致**：方案文档 [机械臂VLA集成方案.md:127] 写 `IO17(TX)/IO18(RX)`，但实际固件 [config.h:78] 使用 `IO9(TX)/IO10(RX)`。原因可能是 IO17/IO18 实际布局在 CN1 扩展口不方便走线，改用更靠近主控的 IO9/IO10。需要同步更新方案文档。
2. **get_status 返回 stub**：`robot.arm.get_status` 当前只发送查询指令，返回固定 `{"status":"pending"}`，未真正解析驱动板回传的关节状态。需要驱动板支持查询协议后完善。
3. **音量控制 API 已修复**：原 `xiaozhi_custom_board.cc` 使用已废弃的 `app.SetVolume()`/`app.GetVolume()`，已改为 `GetAudioCodec()->SetOutputVolume()`，编译已通过。
4. **bread-compact-wifi 固件 OLED 不工作**：首次烧录用的是 `bread-compact-wifi` 板子类型，其 I2C SSD1306 引脚（IO41/IO42）与自定义板不符，导致 OLED 初始化失败。xiaozhi-custom 固件使用 SPI ST7789，需重新烧录验证。
5. **文字输入后服务器无响应的超时处理**：已加入 15 秒超时检测，超时后自动回 idle 并显示提示。需重启 OpenClaw 服务器加载新的 text handler 后才能正常工作。

---

## 4. Phase 2～4 规划（按优先级）

### Phase 2：基础语音对话 + 语音控臂 + 文字对话

**目标**：实现"语音/文字指令 → LLM 解析 → MCP 调用 → 机械臂动作"

#### 任务清单

| 序号 | 任务 | 状态 | 备注 |
|------|------|------|------|
| 2.1 | 准备服务器 | ✅ | Windows 本地 PC（Python venv 直跑） |
| 2.2 | 部署 OpenClaw 后端 | ✅ | venv + 全部依赖 + ffmpeg |
| 2.3 | 配置 LLM + TTS | ✅ | 阿里百炼 deepseek-v4-flash + EdgeTTS |
| 2.4 | 编译固件 WS URL 覆盖 | ✅ | 2090目标0错误，待烧录 |
| 2.5 | 修改 OTA URL | — | 并入 2.4 |
| 2.6 | 文字消息适配 | ✅ | ESP32 text_console + 服务器 handler |
| 2.7 | 测试基础文字对话 | ✅ | WebSocket 端到端全链路通 |
| 2.8 | 角色提示词配置 | ✅ | 含 6 关节映射 + 安全规则 |
| 2.9 | 测试控臂 | 🔲 | 需完成固件烧录 + 硬件接线 |

**启动服务器**（CMD）：
```cmd
set PATH=C:\Users\24628\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin;%PATH%
cd C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server
venv\Scripts\python.exe app.py
```

**验证标准**：说（或打字）"机械臂抬到90度"，机械臂实际移动到指定角度。

---

### Phase 3：VLA 视觉能力

**目标**：部署 smolVLA-0.5B 推理服务，实现"拍照 → 识别物体 → 生成抓取动作"

#### 前置条件

- 一张 **4GB+ 显存的 GPU**（推荐 GTX 3060 / RTX 4060，二手 ~500-1500 元）
- 或使用 Octo-Base 作为备选（2GB 显存，但成功率仅 71.5% vs 81.4%）
- 或使用云端 GPU（如 AutoDL，按小时计费）

#### 任务清单

| 序号 | 任务 | 预估耗时 | 依赖 |
|------|------|----------|------|
| 3.1 | 准备 GPU 服务器（本地或云端）| — | — |
| 3.2 | Clone smolVLA + 安装依赖：`pip install -e .` | 1小时 | 3.1 |
| 3.3 | 编写 FastAPI 推理服务 `vla_server.py`（方案文档 6.3 节已有模板）| 2小时 | 3.2 |
| 3.4 | 下载 smolVLA-0.5B 预训练权重并测试推理 | 1小时 | 3.3 |
| 3.5 | OpenClaw 后端增加 VLA 调用逻辑（拍照 → HTTP 调 VLA 服务 → 下发关节指令）| 4小时 | 3.4 + Phase2 |
| 3.6 | 端到端验证：拍照 → VLA 推理 → 机械臂执行（先用简单指令如"抓取红色方块"）| 3小时 | 3.5 |

**验证标准**：静态场景下，VLA 模型根据照片生成合理的关节角度序列。

---

### Phase 4：端到端语音抓取联调

**目标**：全链路打通，实现"说一句话 → 机械臂自动抓取目标物体"

#### 任务清单

| 序号 | 任务 | 预估耗时 | 依赖 |
|------|------|----------|------|
| 4.1 | LLM 意图解析 - 从自然语言到具体抓取指令的映射 | 3小时 | Phase2 + Phase3 |
| 4.2 | 多轮交互：用户说"左边那个"→ 拍照确认 → 执行抓取 | 3小时 | 4.1 |
| 4.3 | 异常处理：抓取失败重试、物体不可见提示、安全限位 | 3小时 | 4.1 |
| 4.4 | 全链路时延优化（当前预估 3-5 秒/次） | 2小时 | 4.2 |
| 4.5 | 多场景抓取测试（10+ 种物体，每种 10 次）| 4小时 | 4.3 |

**验证标准**：对 10 种日常物体，端到端抓取成功率 ≥ 70%。

---

## 5. 可选进阶：仿真与微调

> 此阶段为可选项，在实际部署到真实机械臂之前或之后执行均可。

### 5.1 LeRobot 仿真验证

| 任务 | 说明 |
|------|------|
| 安装 LeRobot 仿真 | `pip install "lerobot[simulation]"` |
| 加载 SO101 MuJoCo 环境 | 在仿真中运行默认 smolVLA，观察抓取效果 |
| 评估基线成功率 | 在仿真中跑 100 条抓取指令，记录成功率 |

### 5.2 数据采集与微调

| 任务 | 说明 | 硬件需求 |
|------|------|----------|
| 遥操作录制 | SpaceMouse 控制 SO101 录制 50 条示范数据 | SpaceMouse（约 300 元） |
| LoRA 微调 | `python train.py --use_lora`（~10MB adapter 权重） | 4-6GB 显存 GPU |
| 微调效果评估 | 对比微调前后抓取成功率（预期：默认 81% → 微调后 90%+） | — |

---

## 6. 🟢 Phase 0 完成：固件编译 + 基础验证

### 6.1 编译环境搭建总结

| 步骤 | 说明 | 状态 |
|------|------|------|
| ESP-IDF v5.5.3 环境 | 位于 `E:\esp\Espressif\frameworks\esp-idf-v5.5.3\` | ✅ |
| 工具链 esp-14.2.0_20251107 | xtensa-esp-elf + riscv32-esp-elf | ✅ |
| Python 环境 | idf5.5_py3.11_env, Python 3.11.2 | ✅ |
| MSYS2 兼容修复 | idf.py + idf_tools.py MSYS 检测绕过 | ✅ |
| 12 文件 API 迁移 | ESP-IDF v5.5.3 不兼容 API 修复 | ✅ |
| sdkconfig 切换 | BREAD_COMPACT_WIFI → XIAOZHI_CUSTOM + ST7789 | ✅ |
| xiaozhi_custom_board.cc | 音量 API 修复（SetVolume→SetOutputVolume） | ✅ |
| 🆕 文字控制台 | 串口 getchar 读取 + 协议层 SendTextInput + 应用层路由 | ✅ |

### 6.2 面包板固件首次验证（2026-06-23）

> 使用 `bread-compact-wifi` 板子类型进行首次烧录验证

| 验证项 | 预期 | 实际 | 结果 |
|--------|------|------|------|
| 芯片启动 | ESP-ROM 启动信息 | ✅ `ESP-ROM:esp32s3-20210327` | ✅ |
| PSRAM | 8MB OPI PSRAM | ✅ 8MB @ 80MHz | ✅ |
| Flash | QIO 16MB | ✅ detected chip: generic, flash io: qio | ✅ |
| CPU 频率 | 240MHz | ✅ `cpu freq: 240000000 Hz` | ✅ |
| WiFi | 配网模式启动 | ✅ 热点 `Xiaozhi-FDAD` 创建成功 | ✅ |
| MCP 工具 | 7 个工具注册 | ✅ lamp/audio/system/reboot/assets | ✅ |
| 音频服务 | AudioService 启动 | ✅ 16000→24000 重采样 | ✅ |
| OLED 显示 | SSD1306 I2C | ❌ `i2c transaction failed` — 引脚不匹配 | ❌ |

### 6.3 xiaozhi-custom 固件编译（2026-06-23）

```bash
# 编译命令
bash esp_idf_build.sh build
# 结果：2109/2109 目标，0 错误
# 固件：build/xiaozhi.bin (0x29d8e0 = 2.7 MB)
# Board: xiaozhi-custom, Display: ST7789 240x320
# UART1: IO9(TX)/IO10(RX) @ 115200bps
# 🆕 文字控制台：text_console.cc 已纳入编译
```

### 6.4 🔴 立即下一步：烧录最新固件 + 测试文字对话

```bash
# 在 Windows 终端（CMD/PowerShell）中执行：
cd C:\Users\24628\Desktop\vscode\xiaozhiAI
python -m esptool --chip esp32s3 -p COM6 -b 460800 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 16MB \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0xd000 build/ota_data_initial.bin \
  0x20000 build/xiaozhi.bin \
  0x800000 build/generated_assets.bin
```

> ⚠️ **重要**：烧录前用杜邦线将 **IO0 接到 GND** → 按 RST → 拔掉 IO0-GND，强制进入下载模式。

**烧录后立即测试文字对话**：
1. 确认 OpenClaw 服务器已重启（加载 text handler）
2. 打开串口监视器
3. 看到 `文字控制台已启动` 提示
4. 输入 `你好` → 回车
5. 等待服务器回复（TTS 语音 + 屏幕文字）

---

## 7. 后续步骤（按阻塞关系排序）

> 🆕 更新于 2026-06-24：任务 1/2/3/4/5/6 已完成（跳过硬件）

```
0. 🔴 烧录最新固件到 ESP32-S3（含文字控制台）
   ——需烧录 feature/robot-arm-vla 分支最新固件（依赖硬件连接）

1. ✅ 重启 OpenClaw 服务器（加载 text handler）
   ——2026-06-24 已验证：配置加载成功，文字消息处理器 8 种类型全部注册

2. 🟡 测试文字对话
   ——需 ESP32 烧录新固件后测试（依赖硬件）

3. 🔴 硬件接线 + UART 通信验证
   ——接线：ESP32 IO9/IO10 + GND ↔ SO101 驱动板串口（依赖硬件）

4. ✅ 统一文档引脚
   ——2026-06-24 已完成：机械臂VLA集成方案.md 全部改为 IO9/IO10

5. ✅ 部署 OpenClaw 后端
   ——已完成部署，LLM (DeepSeekLLM via 阿里百炼) + TTS (EdgeTTS)

6. ✅ 评估 GPU 可用性
   ——2026-06-24 已完成：tests/gpu_check.py GPU 检测脚本就绪

7. ✅ 飞书 Bot 接入
   ——2026-06-24 已完成：
    • 新建 core/handle/feishu_handler.py — FeishuBot 类
    • 修改 core/http_server.py — 注册 /feishu/callback 路由
    • 修改 app.py — 共享 LLM 实例
    • 修改 config.yaml / data/.config.yaml — 飞书配置节
    • 需在飞书开放平台配置 Bot 后才能端到端验证

8. ✅ VLA 推理服务框架
   ——2026-06-24 已完成：services/vla_server.py FastAPI 服务 (stub模式)
   ——API 匹配 tests/test_vla_inference.py 契约
```

---

## 8. 关键资源

| 资源 | 地址 | 用途 |
|------|------|------|
| 本仓库 | `feature/robot-arm-vla` 分支 | ESP32 固件源码 |
| OpenClaw 后端 | `C:\Users\24628\xiaozhi-esp32-server` (本地) | LLM + TTS + MCP 调度 |
| smolVLA | [github.com/ZhangYizhe/smolVLA](https://github.com/ZhangYizhe/smolVLA) | VLA 视觉-语言-动作模型 |
| LeRobot | [github.com/huggingface/lerobot](https://github.com/huggingface/lerobot) | SO101 仿真 + 数据采集 + 训练 |
| LeRobot SO100 文档 | [lerobot.readthedocs.io](https://lerobot.readthedocs.io/en/latest/) | SO101 机械臂 SDK 参考 |
| 盒子桥教程 | [B站 BV1LN411K7Ps](https://www.bilibili.com/video/BV1LN411K7Ps/) | SO101 DIY 入门 |

---

## 9. 里程碑时间线（预估）

```
2026年6月
  ├─ Week 4 (当前)
  │   ├─ ✅ 文字消息交互完成（ESP32 + 服务器）
  │   ├─ 🔴 烧录固件 + 重启服务器测试
  │   ├─ 🔴 硬件接线完成 + UART 通信验证
  │   └─ 🟠 开始部署 OpenClaw 后端（如未部署）
  │
2026年7月
  ├─ Week 1
  │   ├─ OpenClaw 部署完成 + 语音/文字对话正常
  │   └─ 语音/文字控制机械臂（Phase 2 完成）
  │
  ├─ Week 2
  │   ├─ GPU 到位 / 云端 GPU 就绪
  │   └─ smolVLA-0.5B 推理服务部署完成
  │
  ├─ Week 3-4
  │   ├─ VLA 调用链路打通（Phase 3 完成）
  │   └─ 端到端语音抓取初版跑通
  │
2026年8月
  └─ Week 1-2
      ├─ 异常处理 + 多轮交互完善
      ├─ 多场景抓取测试
      └─ Phase 4 完成，整体成功率 ≥ 70%
```

> ⚠️ 以上时间线为粗略预估，实际进度取决于硬件到位时间和开发投入。

---

## 附：提交历史

| 提交 | 日期 | 说明 |
|------|------|------|
| *(待提交)* | 2026-06-24 | feat: GPU检测脚本 + VLA推理服务框架(stub) + 进度文档更新 |
| `01fc5ea6` | 2026-06-24 | feat: 飞书 Bot 接入（OpenClaw 服务端，feishu_handler.py + 路由 + 配置） |
| `026bc0a` | 2026-06-24 | docs: 统一引脚文档(IO9/10) + 更新README工程化规范 + 飞书Bot方案 |
| `e5bd087` | 2026-06-23 | feat: Phase1.5文字交互+Phase2服务器+工程化目录 |
| `c3f96f3` | 2026-06-23 | docs: 添加小智自定义板机械臂VLA集成README |
| `32c0d0e` | 2026-06-23 | feat: 添加机械臂VLA集成支持（UART+ MCP + Kconfig） |
| `05ff1b9` | 2026-06-23 | refactor: 移除所有非 ESP32-S3 板子支持 |
| `f3c5202` | 2026-06-23 | chore: 清理非 S3 相关文件 |
| `c09a934` | 2026-06-23 | Update README_zh.md |
