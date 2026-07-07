# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

小智机械臂 VLA 项目 — ESP32-S3 语音助手 + OpenClaw 后端 + LeRobot SO101 6-DOF 机械臂，实现「说一句话 → 自动抓取目标物体」的端到端 VLA（Vision-Language-Action）系统。

- **固件分支**: `feature/robot-arm-vla`
- **目标芯片**: ESP32-S3-WROOM-1-N16R8 (16MB Flash + 8MB PSRAM)
- **开发板**: `BOARD_TYPE_XIAOZHI_CUSTOM`（在 `main/Kconfig.projbuild` 中定义）
- **ESP-IDF 版本**: v5.5.3
- **构建系统**: CMake + Ninja + idf.py

## 构建与烧录

```bash
# 编译（需要在 ESP-IDF v5.5.3 环境下）
bash esp_idf_build.sh build

# 烧录（IO0 接 GND → 按 RST → 拔掉 IO0-GND 进入下载模式）
python -m esptool --chip esp32s3 -p COM6 -b 460800 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 16MB \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0xd000 build/ota_data_initial.bin \
  0x20000 build/xiaozhi.bin \
  0x800000 build/generated_assets.bin

# 串口监控
idf.py monitor
```

`esp_idf_build.sh` 封装了工具链路径（Xtensa esp-14.2.0 + RISC-V），将其它 idf.py 参数透传，如 `bash esp_idf_build.sh menuconfig`。

## 代码格式化

使用 `.clang-format`（基于 Google C++ 风格，4 空格缩进，100 字符行宽）：

```bash
clang-format -i path/to/file.cc                          # 格式化单文件
find main -iname *.h -o -iname *.cc | xargs clang-format -i  # 格式化全部
```

## 顶层架构

```
app_main() [main/main.cc]
  └─ TextConsole::Start()          // 串口文字控制台（FreeRTOS 后台任务）
  └─ Application::GetInstance()
       ├─ Initialize()             // 初始化板级、显示、音频、MCP、网络
       │    └─ Board::GetInstance() // DECLARE_BOARD 宏 → Kconfig 选择 → 具体板类
       └─ Run()                    // 事件循环，永不返回
            └─ EventGroup 等待 14 种事件 → Handle*Event() 分发
```

**核心设计模式**:
- `Application` 是单例，驱动所有子系统
- `Board` 是单例，通过 `DECLARE_BOARD(ClassName)` 宏注册，`Kconfig.projbuild` 选择
- 事件驱动：FreeRTOS `EventGroupHandle_t` 管理 14 种事件位（音频、网络、状态、时钟等）

## 关键子系统

### Board 板级支持 (`main/boards/`)

80+ 种开发板，`Board` 抽象基类定义在 `boards/common/board.h`。继承链：
- `Board` → `WifiBoard`（WiFi 板）→ `XiaozhiCustomBoard`（本项目）
- `Board` → `Ml307Board` / `DualNetworkBoard`（4G 模组板）

每个板目录含 `config.h`（引脚映射）、`config.json`（构建配置）、`*_board.cc`（初始化代码）。板型通过 `main/CMakeLists.txt` 中 `CONFIG_BOARD_TYPE_*` → `BOARD_TYPE` 变量 → glob 匹配目录来选择。

**xiaozhi-custom 板关键引脚** (`main/boards/xiaozhi-custom/config.h`):
- UART1 机械臂: **IO9(TX) / IO10(RX)**, 115200 bps
- I2S 音频: IO4(LRC), IO5(DIN), IO6(BCLK), IO7(DAC) — 单工模式
- SPI 显示: IO21(SCL), IO47(SDA), IO45(RES), IO40(DC), IO41(CS), IO42(BLK)
- I2C IMU: IO11(SDA), IO12(SCL)

### 协议层 (`main/protocols/`)

抽象基类 `Protocol` 定义通信接口。两个实现：
- **WebsocketProtocol** — 基于 WebSocket，与 OpenClaw 后端通信
- **MqttProtocol** — 基于 MQTT + UDP 音频通道，含 AES 加密

二进制音频帧格式: `BinaryProtocol2` (12 字节头) 或 `BinaryProtocol3` (4 字节头)。

### 音频子系统 (`main/audio/`)

3 个并行 FreeRTOS 任务：
1. **AudioInputTask** — I2S 采集 PCM → 音频处理器 (AEC/VAD)
2. **OpusCodecTask** — PCM ↔ Opus 编解码
3. **AudioOutputTask** — 解码后 PCM → I2S 扬声器

`AudioCodec` 是硬件抽象层，本板使用 `NoAudioCodec`（纯 I2S，无外部 codec 芯片）。

### MCP 服务器 (`main/mcp_server.cc`)

实现 Model Context Protocol (2024-11-05 规范)，允许 LLM 通过 JSON-RPC 调用设备工具。`McpServer` 单例管理工具注册。

**机械臂工具**（在 `xiaozhi_custom_board.cc` 注册）:
- `robot.arm.move_joints` — 控制 6 个关节角度
- `robot.arm.gripper` — 控制夹爪开合
- `robot.arm.get_status` — 获取当前状态

### 设备状态机 (`main/device_state_machine.cc`)

状态链路: `Unknown → Starting → WifiConfiguring → Idle → Connecting → Listening → Speaking`，也含 `Upgrading`、`Activating`、`FatalError` 状态。观察者模式，所有状态转换经过合法性校验。

### 文字控制台 (`main/text_console.cc`)

独立 FreeRTOS 任务，通过串口读取字符输入发送到 LLM。`!` 前缀命令直接透传到 UART1 机械臂（`!M104S+090` 格式）。

## 分区表

双 OTA 分区（16MB Flash）：`ota_0` + `ota_1` 各 4MB，`assets` 分区 8MB（SPIFFS 存储语言包/字体/表情）。分区表位于 `partitions/v2/16m.csv`。

## UART 兼容性桩头

`main/uart_eth_modem.h` 和 `main/uart_uhci.h` 是 ESP-IDF v5.5 兼容性桩头。v5.5 移除了 `esp_eth_modem` 和 `uart_uhci` 组件，这两个文件提供最小类型定义使 4G 模组板代码能通过编译。**在 v5.5 上 4G 模组板无法实际工作**，仅用于编译通过。修改与 UART/模组相关的代码时，需确保不破坏这些桩头。

## 开发注意事项

- 添加新板型需同时修改：`main/Kconfig.projbuild`（Kconfig 选项）→ `main/CMakeLists.txt`（BOARD_TYPE 映射 + 字体/表情配置）→ 创建 `boards/<name>/` 目录
- MCP 工具变更是运行时接口变更，需同步更新 OpenClaw 后端的工具定义
- `sdkconfig` 文件 106KB，修改构建配置优先用 `menuconfig` 或 `sdkconfig.defaults`
- ESP32-S3 PSRAM 使用 Octal SPI 模式，`CONFIG_SPIRAM_MODE_OCT=y` 必须保持
- 主循环是单线程事件驱动，回调中不要长时间阻塞

## SO101 机械臂通信与测试

### 两条通信链路

```
链路 A: PC → COM6(ESP32) → UART1(IO9/IO10) → SO101 RX/TX 排针 → MCU → 舵机
  协议: JSON  {"cmd":"move_joints","angles":[...],"speed":50}\n
  适用: 走完整链路测试（ESP32 MCP 工具也走这条）

链路 B: PC → COM11(USB) → SO101 CH343 → 舵机总线
  协议: Feetech SCServo 二进制（1M bps）
  适用: 直连舵机调试、读写 EEPROM、设置限位
```

**关键：JSON 指令只能走链路 A（ESP32），USB 直连只能走链路 B（SCServo 协议）。两条链路协议不同，不可混用。**

### SO101 舵机型号

舵机 ping 返回型号 **252**，不是标准 STS3215（型号 6）。EEPROM 地址表与标准 STS 不同，FD 调试软件使用**字节地址**（非字地址），2 字节值采用**小端序**。

| EEPROM 字节地址 | 名称 | 说明 |
|:-:|------|------|
| 9-10 | 最小角度限制 (CW) | 小端 uint16，换算: `值/4096×360°` |
| 11-12 | 最大角度限制 (CCW) | 同上 |
| 40 | 扭矩开关 | 0=关闭, 1=使能 (SRAM) |
| 42-43 | 目标位置 | 小端 uint16 (SRAM) |
| 56-57 | 当前位置 | 只读 (SRAM) |

当前各关节限位（2026-06-30）:

| ID | 关节 | CW 限位 | CCW 限位 | 有效范围 |
|----|------|---------|----------|----------|
| 1 | 底座 | 1100 (96.7°) | 2900 (254.9°) | 158.2° |
| 2 | 大臂 | 800 (70.3°) | 3100 (272.5°) | 202.1° |
| 3 | 小臂 | 800 (70.3°) | 2990 (262.8°) | 192.5° |
| 4 | 腕转 | 950 (83.5°) | 3000 (263.7°) | 180.2° |
| 5 | 腕俯 | 800 (70.3°) | 3900 (342.8°) | 272.5° |
| 6 | 夹爪 | 2000 (175.8°) | 3400 (298.8°) | 123.0° |

**当前物理 HOME 位置**（2026-06-30 读取，跳舞脚本以此为基准）：

| ID | 关节 | 位置(步) | 角度 | 限位安全余量 |
|----|------|----------|------|-------------|
| 1 | 底座 | 2019 | 177.5° | CW+919 / CCW-881 |
| 2 | 大臂 | 805 | 70.8° | CW+5 / CCW-2295 ⚠️贴下限 |
| 3 | 小臂 | 2979 | 261.8° | CW+2179 / CCW-11 ⚠️贴上限 |
| 4 | 腕转 | 2869 | 252.2° | CW+1919 / CCW-131 |
| 5 | 腕俯 | 1082 | 95.1° | CW+282 / CCW-2818 |
| 6 | 夹爪 | 2246 | 197.4° | CW+246 / CCW-1154 |

> ⚠️ 大臂(ID2)和小臂(ID3)已贴近限位边缘。跳舞脚本偏移量：大臂 -600~+700、小臂 -600~+600 仍在安全范围内。**重新摆放机械臂后需更新此表**，用 `so101_read_pos.py COM11` 重新读取。

### 测试脚本速查

| 脚本 | 链路 | 用途 |
|------|------|------|
| [tests/arm_cli.py](tests/arm_cli.py) | A (ESP32) | 交互式命令行，手动发送 `!{JSON}` 指令 |
| [tests/arm_direct_test.py](tests/arm_direct_test.py) | A (ESP32) | 自动化关节序列测试 **→ 实际走 JSON 到 SO101 排针，不可连 COM11** |
| [tests/arm_test.py](tests/arm_test.py) | A (ESP32) | 完整测试序列（旧格式 `!J:[...]` 已废弃） |
| [tests/so101_safe_test.py](tests/so101_safe_test.py) | B (USB) | 逐个关节 ±40步(~3.5°) 微动，零依赖 pyserial |
| [tests/so101_simple.py](tests/so101_simple.py) | B (USB) | 交互式单关节控制，`j2 +10` 细粒度调试 |
| [tests/so101_check_limits.py](tests/so101_check_limits.py) | B (USB) | 读取 6 关节 EEPROM 限位值 |
| [tests/so101_dump_eeprom.py](tests/so101_dump_eeprom.py) | B (USB) | Dump 舵机全部控制表，排障用 |
| [tests/so101_probe.py](tests/so101_probe.py) | — | 自动探测 SO101 波特率/协议格式 |

**小角度测试首选**: `so101_safe_test.py COM11`（DELTA=40, SPEED=150），确认限位后用 `arm_cli.py` 走 ESP32 链路测试 JSON 协议。

## 关键文档

| 文档 | 内容 |
|------|------|
| [README.md](README.md) | 项目总览、快速开始、硬件引脚速查 |
| [docs/code_style.md](docs/code_style.md) | clang-format 代码风格指南 |
| [docs/custom-board.md](docs/custom-board.md) | 自定义开发板完整流程 |
| [docs/mcp-protocol.md](docs/mcp-protocol.md) | MCP 协议说明 |
| [docs/websocket.md](docs/websocket.md) | WebSocket 通信协议 |
| [基本介绍.md](基本介绍.md) | 硬件引脚映射、BOM 清单 |
| [机械臂VLA集成方案.md](机械臂VLA集成方案.md) | VLA 技术方案、模型选型 |
