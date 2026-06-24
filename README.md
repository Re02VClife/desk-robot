# 小智机械臂 VLA 项目

> ESP32-S3 语音助手 + OpenClaw 后端 + LeRobot SO101 机械臂，实现「说一句话 → 自动抓取目标物体」的端到端 VLA（Vision-Language-Action）系统。

---

## 整体架构

```
用户语音/文字指令
        │
        ▼
┌─── ESP32-S3 (小智板) ──────────────────────────┐
│  ├─ 麦克风/扬声器    → OPUS 音频流              │
│  ├─ 摄像头            → MCP camera.take_photo   │
│  ├─ 显示屏/状态灯     → 交互反馈                │
│  ├─ MCP Server        → JSON-RPC 工具注册       │
│  └─ UART 串口         → 转发关节角度到机械臂    │
└──────────────────────┬──────────────────────────┘
                   WebSocket (WiFi)
                       │
                       ▼
┌─── OpenClaw 后端 (小龙虾服务器) ────────────────┐
│  1. LLM  解析语音 → 理解意图                    │
│  2. VLA  模型推理 → 生成机械臂动作               │
│  3. TTS  语音反馈 → "已抓取成功"                │
│  4. MCP  调度     → 调 ESP32 拍照/控臂          │
└──────────────────────┬──────────────────────────┘
                   UART (IO9/IO10)
                       │
                       ▼
┌─── LeRobot SO101 机械臂 ────────────────────────┐
│  6-DOF 关节舵机 + 夹爪                          │
└─────────────────────────────────────────────────┘
```

**核心思路**：ESP32-S3 充当无线桥接（不再需要 PC 通过 USB 连接机械臂），既是语音助手又是通信网桥。

---

## 硬件

| 组件 | 型号 | 说明 |
|------|------|------|
| 主控 | ESP32-S3-WROOM-1-N16R8 | 16MB Flash + 8MB PSRAM |
| 显示 | ST7789 240×320 SPI | 2.0寸 TFT |
| 麦克风 | ZTS6672 MEMS | I2S 接口 |
| 功放 | CH98357 (兼容 MAX98357A) | I2S 输入 |
| IMU | MPU-6500 | 6轴姿态传感器 |
| LED | WS2812B (XL-5050RGBC) | RGB 可编程 |
| 机械臂 | LeRobot SO101 | 6-DOF + 夹爪 |

完整引脚映射和 BOM 清单 → [基本介绍.md](基本介绍.md)

<details>
<summary><b>关键引脚速查</b></summary>

| 功能 | 引脚 |
|------|------|
| 音频 I2S | IO4(LRC), IO5(DIN), IO6(BCLK), IO7(DAC) |
| 显示 SPI | IO21(SCL), IO47(SDA), IO45(RES), IO40(DC), IO41(CS), IO42(BLK) |
| IMU I2C | IO11(SDA), IO12(SCL) |
| 机械臂 UART | **IO9(TX)**, **IO10(RX)** |
| RGB LED | IO48 |
| 按键 | IO0(BOOT), IO38(VOL+), IO39(VOL-) |
| 电池 ADC | IO2 |

</details>

---

## 快速开始

### 1. 部署 OpenClaw 后端服务

本设备需要连接 OpenClaw 后端服务器。后端部署步骤：

```bash
# 1. 克隆后端
git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git
cd xiaozhi-esp32-server

# 2. 配置并启动
cp main/xiaozhi-server/config.yaml.example main/xiaozhi-server/config.yaml
# 编辑 config.yaml 填入你的 API key
docker-compose -f main/xiaozhi-server/docker-compose.yml up -d
```

> **运行后**，确认 WebSocket 地址（默认 `ws://<服务器IP>:8000/xiaozhi/v1/`），后续固件需配置该地址。

### 2. 编译 & 烧录固件

```bash
# 编译（ESP-IDF v5.5.3 环境）
cd xiaozhiAI
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
```

分支：`feature/robot-arm-vla` | 板卡：`BOARD_TYPE_XIAOZHI_CUSTOM` | 芯片：ESP32-S3

### 3. 机械臂接线

```
ESP32 IO9  (TX) → SO101 驱动板 RX
ESP32 IO10 (RX) → SO101 驱动板 TX
ESP32 GND       → SO101 驱动板 GND
```

---

## 功能特性

| 功能 | 说明 | 状态 |
|------|------|------|
| 🎙️ 语音对话 | ESP32 麦克风采集 → OPUS → WebSocket → LLM → TTS | ✅ |
| ⌨️ 文字对话 | 串口终端打字 → 直接与 AI 对话（Phase 1.5） | ✅ |
| 🦾 语音控臂 | "大臂抬到90度" → LLM 解析 → MCP 调用 → UART 控制舵机 | 🔄 |
| 📷 视觉抓取 | 拍照 → smolVLA-0.5B 推理 → 生成抓取动作 (Phase 3) | 🟡 |
| 🤖 飞书 Bot | 飞书消息 → LLM → 双路回复（飞书文字 + ESP32 语音） | ✅ 代码就绪 |

---

## 项目进度

| 阶段 | 内容 | 状态 | 完成度 |
|------|------|------|--------|
| Phase 0 | ESP-IDF v5.5.3 编译适配 | ✅ | 100% |
| Phase 1 | 硬件接线 + UART 驱动 + MCP 工具 | 🔄 | ~85% |
| Phase 1.5 | 文字消息交互 | ✅ | 100% |
| Phase 2 | 部署 OpenClaw + 语音对话 + 控臂 | 🔄 | ~80% |
| Phase 3 | smolVLA-0.5B + 视觉抓取推理 | 🟡 | ~15% |
| Phase 4 | 端到端语音抓取联调 | 🔲 | 0% |

**整体进度：约 55%**

---

## 文档索引

| 文档 | 内容 |
|------|------|
| [基本介绍.md](基本介绍.md) | 硬件引脚映射、BOM清单、编译烧录指南 |
| [机械臂VLA集成方案.md](机械臂VLA集成方案.md) | 完整技术方案：架构、模型选型（smolVLA/Octo）、微调流程 |
| [当前进度及未来规划.md](当前进度及未来规划.md) | 详细进度跟踪、Phase 0-4 任务清单、里程碑时间线 |
| [飞书接入.md](飞书接入.md) | 飞书 Bot 接入方案：架构、代码、实施步骤 |
| [progress.md](progress.md) | 原子化功能点推进记录 |
| [浏览器音频问题排障总结.md](浏览器音频问题排障总结.md) | Chrome WebAudio 播放链路排障 |

---

## 关键资源

| 资源 | 地址 | 用途 |
|------|------|------|
| 本仓库 | `feature/robot-arm-vla` 分支 | ESP32 固件源码 |
| OpenClaw 后端 | [xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server) | LLM + TTS + MCP 调度 |
| smolVLA | [github.com/ZhangYizhe/smolVLA](https://github.com/ZhangYizhe/smolVLA) | VLA 视觉-语言-动作模型（4GB 显存） |
| LeRobot | [github.com/huggingface/lerobot](https://github.com/huggingface/lerobot) | 仿真 + 数据采集 + 训练框架 |
| 盒子桥教程 | [B站 BV1LN411K7Ps](https://www.bilibili.com/video/BV1LN411K7Ps/) | SO101 DIY 入门 |
