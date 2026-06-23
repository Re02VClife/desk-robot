# 小智自定义PCB — 机械臂VLA语音抓取

> 基于 ESP32-S3 的 AI 语音助手 + LeRobot SO101 机械臂 VLA（Vision-Language-Action）视觉抓取方案。

---

## 1. 项目概述

本项目在开源 [小智AI](https://github.com/78/xiaozhi-esp32) 框架基础上，定制了 ESP32-S3 主板硬件，并通过 OpenClaw（小龙虾）后端 + smolVLA 模型实现了**语音控制 6-DOF 机械臂**的端到端视觉抓取能力。

### 核心能力

| 功能 | 说明 |
|------|------|
| 🎙️ 语音对话 | 唤醒词 → 语音识别 → LLM 理解意图 → TTS 语音反馈 |
| 📷 视觉识别 | ESP32 摄像头拍照 → MCP 回传 → VLA 模型理解场景 |
| 🦾 机械臂控制 | LLM 解析指令 → MCP 下发关节角度 → UART → 驱动板 → 舵机 |
| 🧠 VLA 推理 | smolVLA-0.5B 模型根据画面+指令生成抓取动作序列 |
| 📡 无线桥接 | ESP32-S3 代替 USB 连接 PC，WiFi 全屋覆盖 |

---

## 2. 硬件规格

### 主控

| 项目 | 参数 |
|------|------|
| 芯片 | ESP32-S3-WROOM-1-N16R8 |
| Flash | 16MB（内置） |
| PSRAM | 8MB（内置，Octal SPI） |
| 供电 | 3.3V / 5V（电池经升压板至5V） |
| LDO | ME6211C33M5G-N（5V→3.3V） |

### 引脚映射

#### 音频（I2S 单工模式）

| 引脚 | 功能 | 说明 |
|------|------|------|
| IO4 | 麦克风 LRC / 功放 LRCK | ZTS6672 + CH98357 共享 |
| IO5 | 麦克风 DIN | ZTS6672 数据输出 |
| IO6 | 麦克风 BCLK / 功放 BCLK | 共享位时钟 |
| IO7 | 功放 DIN | CH98357 / MAX98357A 数据输入 |

#### 显示屏（ST7789 SPI，U7 连接器）

| 引脚 | 功能 |
|------|------|
| IO21 | SCL（SPI 时钟） |
| IO47 | SDA（SPI MOSI） |
| IO45 | RES（复位） |
| IO40 | DC（数据/命令） |
| IO41 | CS（片选） |
| IO42 | BLK（背光 PWM） |

#### 传感器与按键

| 引脚 | 功能 | 说明 |
|------|------|------|
| IO11 | MPU-6500 SDA | I2C 数据（地址 0x68） |
| IO12 | MPU-6500 SCL | I2C 时钟 |
| IO48 | RGB LED | WS2812B |
| IO0 | BOOT 按键 | 短按切换对话 / 长按进配网 |
| IO38 | VOL+ | 音量增大 |
| IO39 | VOL- | 音量减小 |
| IO2 | ADC1_CH1 | 电池电压检测（100k+100k 分压） |

#### 机械臂 UART（连接 SO101 驱动板）

| 引脚 | 功能 | 说明 |
|------|------|------|
| **IO9** | UART1 TX | → SO101 驱动板 RX |
| **IO10** | UART1 RX | ← SO101 驱动板 TX |
| GND | 共地 | → SO101 GND |

#### 扩展与空闲引脚

| 接口 | 引脚 | 说明 |
|------|------|------|
| CN1（4P 1.0mm） | IO17, IO18, IO19, IO20 | 扩展接口 1 |
| CN2（4P 1.0mm） | IO8, IO37, IO42, IO1 | 扩展接口 2（IO42 与背光共享） |
| 空闲 | IO13, IO14, IO15, IO16 | 可用于舵机直驱等扩展 |

> ⚠️ **注意**：显示必须用 U7 连接器，8pin 连接器与 MPU-6500 的 IO11/IO12 冲突。CN2 的 IO42 与背光共用，使用时注意。

---

## 3. 机械臂控制架构

```
┌───── 用户语音指令 ──────────────────────────────────────┐
│  "把那杯水拿过来" / "把红色方块放到左边"                    │
└──────────────────────────────────────────────────────────┘
                          ↓ 语音采集
┌─────── ESP32-S3（小智硬件 + 无线桥接）───────────────────┐
│  ├─ 麦克风/扬声器    → OPUS 音频流                       │
│  ├─ 摄像头           → MCP 工具: camera.take_photo       │
│  ├─ 显示屏/状态灯    → 交互反馈                           │
│  ├─ MCP Server       → JSON-RPC 协议                     │
│  └─ UART1 (IO9/IO10) → 转发关节指令到机械臂驱动板         │
└────────────────────────┬─────────────────────────────────┘
                     WebSocket (WiFi)
                          ↓
┌─────── OpenClaw 后端（小龙虾服务器）─────────────────────┐
│                                                          │
│  1. LLM 解析语音 → 理解意图（"抓取红色杯子"）              │
│     ├─ 触发 MCP: 调 ESP32 拍照获取画面                    │
│     └─ 识别目标物体和操作                                 │
│                                                          │
│  2. VLA 模型推理 → 生成机械臂动作                         │
│     ├─ 输入: 当前画面 + 文本指令                          │
│     ├─ 模型: smolVLA-0.5B（仅需 ~4GB 显存）               │
│     └─ 输出: 关节角度序列（Action Chunking）              │
│                                                          │
│  3. 下发关节指令 → WebSocket → ESP32 → UART → 机械臂     │
│  4. TTS 语音反馈 → "已抓取成功"                           │
└──────────────────────────────────────────────────────────┘
                          │ UART（代替 USB）
                          ▼
┌─────── LeRobot SO101 机械臂 ────────────────────────────┐
│  ├─ 原装驱动板（解析串口 → PWM 舵机）                     │
│  ├─ 6-DOF 关节舵机 + 夹爪舵机                            │
│  └─ 位置/力反馈（可选）                                   │
└──────────────────────────────────────────────────────────┘
```

### 无线桥接优势

| 对比项 | USB 连 PC | ESP32-S3 无线桥接 |
|--------|-----------|-------------------|
| 使用场景 | 必须开电脑 | 随时随地语音操控 |
| 设备体积 | PC + 线缆 | 一块芯片搞定 |
| 语音集成 | 需 PC 端额外软件 | 小智板本身即语音助手 |
| 控制延迟 | USB 直连 < 1ms | WiFi < 20ms（对机械臂足够） |
| 移动性 | 线缆束缚 | 全屋 WiFi 覆盖 |

---

## 4. 机械臂 MCP 工具

ESP32 端已注册以下 3 个 MCP 工具，LLM 可直接调用：

### robot.arm.move_joints

控制机械臂 6 个关节角度。

| 参数 | 类型 | 说明 |
|------|------|------|
| `angles` | string | 6 个关节角度的 JSON 数组，如 `[90,45,120,60,30,0]`，单位：度 |
| `speed` | integer | 速度百分比 1-100，默认 50 |

### robot.arm.gripper

控制夹爪开合。

| 参数 | 类型 | 说明 |
|------|------|------|
| `open` | boolean | `true` 张开，`false` 闭合 |
| `speed` | integer | 速度百分比 1-100，默认 50 |

### robot.arm.get_status

获取机械臂当前关节角度和夹爪状态，无参数。

---

## 5. 编译与烧录

### 环境要求

- **ESP-IDF**: v5.5.3
- **工具链**: VSCode + ESP-IDF 扩展
- **芯片目标**: `esp32s3`

### 首次编译

```bash
cd xiaozhiAI
idf.py set-target esp32s3
idf.py menuconfig
```

在 menuconfig 中配置：

```
Xiaozhi Assistant
  ├─ Board Type → XiaoZhi Custom PCB
  ├─ WebSocket 服务器地址覆盖 → ws://<你的服务器IP>:8000/xiaozhi/v1/
  └─ OTA URL → https://<你的服务器>/xiaozhi/ota/
```

```bash
idf.py build
```

### 烧录（通过 CH340 串口模块）

连接 CH340 到 JP1（IO43=RXD0, IO44=TXD0），然后：

```bash
idf.py -p COMx flash monitor
```

**手动进入下载模式**：按住 BOOT(IO0) → 按 EN → 松开 EN → 松开 BOOT

### OTA 更新

首次烧录后，后续固件通过 WiFi OTA 自动更新（双分区回滚，安全可靠）。

---

## 6. 后端部署

### 6.1 OpenClaw 后端（必需）

```bash
git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git
cd xiaozhi-esp32-server
# 配置 config.yaml（LLM + TTS）
docker compose up -d
```

**推荐配置**：
- LLM: DeepSeek-V3（性价比高）或 ChatGLM
- TTS: Edge-TTS（免费）或 CosyVoice（效果更好）

### 6.2 VLA 模型（Phase 3，需 GPU）

```bash
git clone https://github.com/ZhangYizhe/smolVLA.git
cd smolVLA
pip install -e .
```

部署 FastAPI 推理服务（示例见方案文档 6.3 节）。

**硬件要求**：

| 模型 | 显存需求 | 推荐显卡 | 抓取成功率 |
|------|----------|----------|-----------|
| **smolVLA-0.5B** ⭐ | ~4GB | GTX 3060 / 4060 | 81.4% |
| smolVLA-7B | ~16GB | RTX 4090 / A4000+ | 87.9% |
| Octo-Base（备选） | ~2GB | 无独显也可 | 71.5% |

---

## 7. 硬件接线示意

```
                         WiFi
                    ┌──────────┐
                    │ OpenClaw │  ← VLA 模型推理（GPU）
                    │  后端    │
                    └────┬─────┘
                         │ WebSocket
                         │
                    ┌────┴──────┐
                    │ ESP32-S3  │  ← 小智语音助手 + 无线桥接
                    │ (小智板)   │
                    ├───────────┤
                    │ IO9  TX ──┼──────────┐
                    │ IO10 RX ──┼──────────┤
                    │ GND     ──┼──────────┤
                    └───────────┘          │
                                           │ 杜邦线
                                           │
                    ┌──────────────────────┘
                    │
                    ▼
               ┌──────────┐
               │ SO101    │  ← 原装驱动板解析串口命令
               │ 驱动板    │
               ├──────────┤
               │ PWM 信号  │
               ├────┬──┬──┴──┬────┬────┬────┐
               ▼    ▼  ▼     ▼    ▼    ▼    ▼
             舵机1 舵机2 舵机3 舵机4 舵机5 舵机6 夹爪
            (肩部)(大臂)(小臂)(腕旋)(腕摆)(末端)
```

---

## 8. 数据流（端到端抓取）

```
[用户] → "把那杯水拿过来"
           ↓
[ESP32 mic] → OPUS 编码 → WebSocket 发送
           ↓
[OpenClaw] → LLM 解析意图
           │   识别: 目标="水杯", 动作="抓取并移动"
           ↓
[OpenClaw] → MCP 调用: camera.take_photo(question="找到桌子上的水杯")
           │              ↓
           │    [ESP32 camera] → 拍照 → MCP 返回图片
           │              ↓
[OpenClaw] → 图片 + 指令 → VLA 模型推理
           │    模型: smolVLA-0.5B
           │    输入: [图片, "pick up the cup"]
           │    输出: action_chunk = [θ₁...θ₆, gripper] × N 步
           │
[OpenClaw] → WebSocket 下发关节角度 → ESP32
           │              ↓
[ESP32] → MCP 工具 robot.arm.move_joints(angles)
           │  → UART 发送到 SO101 驱动板
           │              ↓
[SO101 驱动板] → 解析串口命令 → PWM → 舵机执行
           │              ↓
           └── → TTS: "好的，水杯已经拿过来了"
```

---

## 9. 分步实施路线

| 阶段 | 内容 | 状态 |
|------|------|------|
| **Phase 1** | 硬件接线 + UART 驱动 + MCP 工具 | ✅ 已完成 |
| **Phase 2** | 部署 OpenClaw + 语音对话 + 语音控制机械臂 | 🔲 待部署 |
| **Phase 3** | 部署 smolVLA-0.5B + 视觉抓取推理 | 🔲 需 GPU |
| **Phase 4** | 端到端语音抓取联调 + 异常处理 | 🔲 待联调 |

---

## 10. 仿真与微调（可选）

在真实部署前，可用 LeRobot 的 MuJoCo 仿真环境验证模型效果：

```bash
pip install "lerobot[simulation]"
```

用 SpaceMouse 遥操作录制示范数据（建议 50 条），然后 LoRA 微调 smolVLA：

```bash
python train.py \
    --model_name ZhangYizhe/smolVLA-0.5B \
    --dataset_path your-name/so101-grasp-dataset \
    --use_lora true \
    --lora_rank 16 \
    --batch_size 4 \
    --num_epochs 50
```

微调后 LoRA 权重仅 **~10MB**，可显著提升特定场景抓取成功率至 90%+。

---

## 11. 参考资源

- **小智AI 框架**: [github.com/78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32)
- **OpenClaw 后端**: [github.com/xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
- **smolVLA 模型**: [github.com/ZhangYizhe/smolVLA](https://github.com/ZhangYizhe/smolVLA)
- **LeRobot 框架**: [github.com/huggingface/lerobot](https://github.com/huggingface/lerobot)
- **Octo 模型（备选）**: [github.com/rail-berkeley/octo](https://github.com/rail-berkeley/octo)
- **盒子桥 B站教程**: [全民DIY机械臂 EP1~EP4](https://www.bilibili.com/video/BV1LN411K7Ps/)
- **MCP 协议**: [modelcontextprotocol.io](https://modelcontextprotocol.io)

---

## 12. OpenClaw 角色提示词参考

在 OpenClaw 后台可配置以下角色提示词，让 LLM 更好地控制机械臂：

> **我的身份**：我是一个集成视觉和机械臂控制能力的 AI 助手，运行在 ESP32-S3 小智硬件上。我可以通过摄像头观察环境，并控制一个 6-DOF LeRobot SO101 机械臂。
>
> **我的能力**：
> - 拍照观察：使用 `self.camera.take_photo` 获取当前画面
> - 机械臂控制：使用 `robot.arm.move_joints` 控制 6 个关节（0-180°），使用 `robot.arm.gripper` 控制夹爪开合
> - 状态查询：使用 `robot.arm.get_status` 获取机械臂当前状态
>
> **关节参考范围**（SO101，单位：度）：
> - 关节1（底座旋转）：0-180
> - 关节2（大臂俯仰）：30-150
> - 关节3（小臂俯仰）：0-180
> - 关节4（腕部旋转）：0-180
> - 关节5（腕部俯仰）：30-150
> - 关节6（末端旋转）：0-180
>
> **工作时原则**：
> 1. 收到抓取指令后，先拍照观察目标位置
> 2. 看到目标物体后，根据物体位置规划抓取动作
> 3. 先移动到物体上方（预抓取位姿），再下降到抓取位置
> 4. 抓取前先确保夹爪张开，抓取后闭合夹爪
> 5. 动作完成后用 TTS 语音反馈结果
