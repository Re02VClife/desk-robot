# 小智机械臂 VLA

> ESP32-S3 语音助手 + OpenClaw 后端 + LeRobot SO101 机械臂
> "说一句话 → AI 理解意图 → 控制机械臂执行动作"

## 快速开始

### 1. 启动服务器

```cmd
set PATH=C:\Users\24628\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin;%PATH%
cd C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server
venv\Scripts\python.exe app.py
```

### 2. 烧录固件

```bash
bash esp_idf_build.sh build
python -m esptool --chip esp32s3 -p COM12 -b 460800 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 16MB \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0xd000 build/ota_data_initial.bin \
  0x20000 build/xiaozhi.bin \
  0x800000 build/generated_assets.bin
```

### 3. 在串口控制台输入指令

```
左转45度                  → 秒级响应（关键词直路）
归位                       → 回 HOME
左转45度然后归位           → 多步串联
抬起来然后张开夹爪         → 多步串联
跳个舞                     → LLM 自主编排
看看桌上有什么             → USB 摄像头（如已连接）
```

## 架构

```
┌─ 文字/语音输入 ──────────────────────────────────────────┐
│  串口控制台  │  WebSocket  │  MQTT  │  触摸传感器(IO3)  │
└──────────────────────┬──────────────────────────────────┘
                       ▼
┌─ ESP32-S3 固件 (xiaozhi-custom) ────────────────────────┐
│  • SCServo 直连协议 (UART1, 1Mbps)                     │
│  • MCP Server → 6 个机械臂工具                          │
│  • 安全锁: J2<15°→锁定J1, J3<20°→禁降J2               │
│  • 触摸交互: IO3 传感器 → 14种随机反应                  │
└──────────────────────┬──────────────────────────────────┘
                       │ WebSocket (WiFi)
                       ▼
┌─ OpenClaw 服务器 (本地 PC) ─────────────────────────────┐
│  • deepseek-v4-flash (阿里百炼)                         │
│  • move_arm 增量式控制 + 多步指令解析                   │
│  • camera_usb: OpenCV 抓图 → LLM 看图                  │
│  • 静音模式 (TTS 关闭)                                  │
└──────────────────────┬──────────────────────────────────┘
                       │ UART (ESP32 ↔ SO101)
                       ▼
┌─ SO101 6-DOF 机械臂 ────────────────────────────────────┐
│  底座/大臂/小臂/腕转/腕俯/夹爪 (STS3215 舵机)          │
└─────────────────────────────────────────────────────────┘
```

## 硬件引脚

| 功能 | 引脚 | 说明 |
|------|------|------|
| 机械臂 UART1 TX | IO9 | → 驱动板 R |
| 机械臂 UART1 RX | IO10 | ← 驱动板 T |
| 触摸传感器 | IO3 | 摸头交互 |
| 显示 SPI | IO21/47/45/40/41/42 | ST7789 240x320 |
| I2C IMU | IO11/IO12 | MPU-6500 |
| I2S 音频 | IO4/5/6/7 | 单工模式 |
| 按键 | IO0/38/39 | Boot/音量+/音量- |
| LED | IO48 | 状态灯 |

## MCP 工具清单

| 工具 | 说明 |
|------|------|
| `robot.arm.move_joints` | 同时控制6关节，支持增量模式 |
| `robot.arm.move_joint` | 单关节控制 |
| `robot.arm.home` | 一键归位到 HOME 安全姿态 |
| `robot.arm.stop` | 急停释放扭矩 |
| `robot.arm.gripper` | 夹爪开合/精确位置 |
| `robot.arm.get_status` | 读取当前位置+角度+扭矩 |
| `self.camera.take_photo` | ESP32 摄像头拍照 (需硬件) |

## 服务端插件

| 插件 | 说明 |
|------|------|
| `move_arm` | 自然语言→关节动作 (增量式+多步) |
| `camera_usb` | USB 摄像头拍照→LLM 看图 |
| `vla_grasp` | VLA 视觉抓取 (需 GPU) |

## 测试脚本速查

| 脚本 | 用途 |
|------|------|
| [tests/camera_test.py](tests/camera_test.py) | USB 摄像头预览 |
| [tests/so101_diag.py](tests/so101_diag.py) | 舵机总线诊断 |
| [tests/so101_safe_test.py](tests/so101_safe_test.py) | 安全小角度测试 |
| [tests/so101_dance.py](tests/so101_dance.py) | 跳舞脚本(直连) |
| [tests/so101_read_pos.py](tests/so101_read_pos.py) | 读取当前位置 |
| [tests/arm_cli.py](tests/arm_cli.py) | 交互式串口控制 |

## 当前状态

- ✅ 硬件链路: ESP32 → SCServo → 6舵机
- ✅ MCP 工具: 6个控臂工具
- ✅ LLM 直控: deepseek-v4-flash 自由调用工具
- ✅ 多步指令: "X 然后 Y 两秒后 Z"
- ✅ USB 摄像头: 自检+降级+LLM看图
- ✅ 触摸交互: IO3 摸头→随机反应
- ✅ 安全约束: 固件锁 + 提示词 + 限位
- 🔲 VLA 视觉抓取 (需 GPU)
- 🔲 TTS 语音 (暂时静音)

## 关键文档

| 文档 | 内容 |
|------|------|
| [CLAUDE.md](CLAUDE.md) | AI 协作规则 + 项目速查 |
| [progress.md](progress.md) | 开发进度原子记录 |
| [机械臂VLA集成方案.md](机械臂VLA集成方案.md) | 原始架构设计 |
| [基本介绍.md](基本介绍.md) | 硬件 BOM 清单 |
