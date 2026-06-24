# 搁置搁置da小智 ESP32 + OpenClaw + LeRobot SO101 机械臂 VLA 集成方案

> 使用小龙虾（OpenClaw）后端替代官方后端，实现语音控制 LeRobot SO101 机械臂进行 VLA（Vision-Language-Action）视觉抓取。
>
> ESP32-S3 充当无线桥接，代替 USB 连接 PC 的传统方式。

---

## 1. 整体架构

```
┌───── 用户语音指令 ─────────────────────────────────────────────────┐
│  "把那杯水拿过来" / "把红色方块放到左边"                              │
└────────────────────────────────────────────────────────────────────┘
                              ↓ 语音采集
┌───────── ESP32-S3 (小智硬件 + 无线桥接) ───────────────────────────┐
│  ├─ 麦克风 / 扬声器       → OPUS 音频流                            │
│  ├─ 摄像头                → MCP 工具: camera.take_photo            │
│  ├─ 显示屏 / 状态灯       → 交互反馈                                │
│  ├─ MCP Server            → JSON-RPC 协议                          │
│  └─ UART 串口             → 转发关节角度到机械臂驱动板              │
└──────────────────────────────────┬──────────────────────────────────┘
                           WebSocket (WiFi)
                              ↓
┌───────── OpenClaw 后端 (小龙虾服务器) ─────────────────────────────┐
│                                                                    │
│  1. LLM 解析语音 → 理解意图（"抓取红色杯子"）                       │
│     ├─ 触发 MCP: 调 ESP32 拍照获取当前画面                          │
│     └─ 识别目标物体和操作                                           │
│                                                                    │
│  2. VLA 模型推理 → 生成机械臂动作                                   │
│     ├─ 输入: 当前画面 + 文本指令                                    │
│     ├─ 模型: smolVLA-0.5B（推荐）/ smolVLA-7B / Octo-Base         │
│     └─ 输出: 关节角度序列 / 末端位姿 (Action Chunking)              │
│                                                                    │
│  3. 下发关节指令 → WebSocket → ESP32 → UART → 机械臂               │
│                                                                    │
│  4. TTS 语音反馈 → "已抓取成功"                                     │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
                              │ UART (代替 USB)
                              ▼
┌───────── LeRobot SO101 机械臂 ─────────────────────────────────────┐
│  ├─ 原装驱动板 (解析串口命令 → PWM 舵机)                            │
│  ├─ 6-DOF 关节舵机                                                  │
│  ├─ 夹爪舵机                                                        │
│  └─ 位置/力反馈 (可选)                                              │
└────────────────────────────────────────────────────────────────────┘
```

---

## 2. 无线桥接原理

### 为什么不需要 PC？

SO101 默认架构：

```
PC (运行 LeRobot Python SDK) ──USB── SO101 驱动板 ──PWM── 舵机组
```

无线化后：

```
OpenClaw 后端 (VLA推理) ──WiFi── ESP32-S3 ──UART── SO101 驱动板 ──PWM── 舵机组
                                        ↑
                                  不再需要 PC，
                                  小智板 = 语音助手 + 无线网桥 二合一
```

VLA 模型推理仍需在服务器（带 GPU）上跑，但控制链路完全去掉了 PC。

---

## 3. 数据流详解

### 3.1 语音指令 → 抓取动作（端到端）

```
[用户] → "把那杯水拿过来"
         ↓
[ESP32 mic] → OPUS 编码 → WebSocket 发送
         ↓
[OpenClaw] → LLM 解析意图
         │   识别结果: 目标="水杯", 动作="抓取并移动"
         ↓
[OpenClaw] → MCP 调用: camera.take_photo(question="找到桌子上的水杯")
         │              ↓
         │    [ESP32 camera] → 拍照 → MCP 返回图片
         │              ↓
[OpenClaw] → 图片 + 指令 → VLA 模型推理
         │    模型: smolVLA-0.5B ← 推荐（仅需 ~4GB 显存）
         │    输入: [图片, "pick up the cup"]
         │    输出: action_chunk = [θ₁...θ₆, gripper] × N 步 (Action Chunking)
         │
[OpenClaw] → WebSocket 下发关节角度 → ESP32
         │              ↓
[ESP32] → MCP 工具 robot.arm.move(angles)
         │  → UART 发送到 SO101 驱动板
         │              ↓
[SO101 驱动板] → 解析串口命令 → PWM → 舵机执行
         │              ↓
         └── → TTS: "好的，水杯已经拿过来了"
```

### 3.2 通信协议

| 链路                  | 协议            | 格式                                    |
| --------------------- | --------------- | --------------------------------------- |
| ESP32 ↔ OpenClaw     | WebSocket (WSS) | BinaryProtocol v2/v3 (OPUS) + JSON 信令 |
| ESP32 MCP 工具调用    | JSON-RPC 2.0    | 通过 WebSocket 透传                     |
| ESP32 ↔ SO101 驱动板 | UART (串口)     | 自定义二进制/JSON 协议                  |
| SO101 驱动板 → 舵机  | PWM             | 50Hz 标准舵机信号                       |

---

## 4. 硬件连接

### 4.1 引脚接线

SO101 原装驱动板通常有串口接口（或通过 USB 转 TTL 模块）：

| 小智 ESP32-S3             | → | SO101 驱动板 | 说明                 |
| ------------------------- | -- | ------------ | -------------------- |
| **IO9** (UART1 TX)  | → | RX           | ESP32 发送关节指令   |
| **IO10** (UART1 RX) | ← | TX           | 接收状态反馈（可选） |
| **GND**             | → | GND          | 共地                 |
| **5V**              | → | VCC          | 可选：给驱动板供电   |

> 注：IO9/IO10 位于 ESP32-S3 主控附近板载焊盘，走线方便。IO17/IO18 在 CN1 扩展接口上作为预留引脚保持空闲。

如果你的 SO101 驱动板只有 USB 口，可以用一个 **USB 转 TTL 模块** 接线：

```
ESP32 TX (IO9) → USB转TTL模块 RX → 模块 USB → SO101 USB口
ESP32 RX (IO10) ← USB转TTL模块 TX
```

### 4.2 SO101 机械臂使用的空闲引脚

参考你的 [板级定义](main/boards/xiaozhi-custom/) 和 [基本介绍](基本介绍.md)：

| 引脚      | 用途                 | 说明                 |
| --------- | -------------------- | -------------------- |
| IO9       | UART TX → 机械臂 RX | 板载焊盘（主控附近） |
| IO10      | UART RX ← 机械臂 TX | 板载焊盘（主控附近） |
| IO17      | (预留)               | CN1 扩展接口·空闲   |
| IO18      | (预留)               | CN1 扩展接口·空闲   |
| IO19      | (预留)               | CN1 扩展接口         |
| IO20      | (预留)               | CN1 扩展接口         |
| IO13-IO16 | (完全空闲)           | 可用于舵机 PWM 直驱  |

### 4.3 直驱舵机模式（可选，更彻底的无线化）

如果想绕过 SO101 原装驱动板，直接用 ESP32-S3 驱动舵机：

| 小智 ESP32-S3 | → | 舵机             | 说明         |
| ------------- | -- | ---------------- | ------------ |
| IO13          | → | 舵机1 (肩部)     | 空闲引脚     |
| IO14          | → | 舵机2 (大臂)     | 空闲引脚     |
| IO15          | → | 舵机3 (小臂)     | 空闲引脚     |
| IO16          | → | 舵机4 (腕部旋转) | 空闲引脚     |
| IO19          | → | 舵机5 (腕部俯仰) | CN1 扩展接口 |
| IO20          | → | 舵机6 (末端旋转) | CN1 扩展接口 |
| IO8           | → | 夹爪舵机         | CN2 扩展接口 |

**优点**：不依赖 SO101 驱动板，完全自主控制
**缺点**：需要额外供电电路，丢失 LeRobot 生态的固件功能

---

## 5. 当前已有资产（无需开发）

| 组件           | 位置                                                                      | 说明                         |
| -------------- | ------------------------------------------------------------------------- | ---------------------------- |
| WebSocket 协议 | [main/protocols/websocket_protocol.cc](main/protocols/websocket_protocol.cc) | 已实现握手、音频流、信令     |
| MCP 工具框架   | [main/mcp_server.h](main/mcp_server.h)                                       | JSON-RPC 2.0 工具注册与调用  |
| 拍照工具       | [main/mcp_server.cc:102](main/mcp_server.cc#L102)                            | `camera.take_photo` 已实现 |
| 音频编解码     | [main/audio/](main/audio/)                                                   | OPUS 编解码、AEC             |
| UART 驱动      | ESP-IDF 内置`driver/uart.h`                                             | 直接可用                     |

---

## 6. 需要开发的部分

### 6.1 OpenClaw 后端部署

```bash
git clone https://github.com/xinnan-tech/xiaozhi-esp32-server.git
cd xiaozhi-esp32-server
# 配置 docker-compose.yml + config.yaml
# 配置 LLM (DeepSeek/ChatGLM) + TTS (Edge TTS)
docker compose up -d
```

### 6.2 ESP32 端：添加机械臂 MCP 工具

在 [mcp_server.cc](main/mcp_server.cc) 的 `AddCommonTools()` 或板级初始化中添加：

```cpp
// 初始化 UART（在板级初始化中执行一次）
uart_config_t uart_config = {
    .baud_rate = 115200,
    .data_bits = UART_DATA_8_BITS,
    .parity = UART_PARITY_DISABLE,
    .stop_bits = UART_STOP_BITS_1,
    .flow_ctrl = UART_HW_FLOWCTRL_DISABLE
};
uart_param_config(UART_NUM_1, &uart_config);
uart_set_pin(UART_NUM_1, GPIO_NUM_9, GPIO_NUM_10, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE);
uart_driver_install(UART_NUM_1, 256, 0, 0, NULL, 0);

// MCP 工具：机械臂关节控制
AddTool("robot.arm.move_joints",
    "Move the robot arm joints to specified angles. "
    "Accepts an array of 7 joint angles: [joint1..joint6, gripper]. "
    "Each joint range is 0-180 degrees, gripper range is 0-100.",
    PropertyList({
        Property("joints", kPropertyTypeString, 
            "JSON array of 7 angles, e.g. [90,45,120,60,30,0,50]")
    }),
    [](const PropertyList& props) -> ReturnValue {
        auto joints_str = props["joints"].value<std::string>();
        // 解析 JSON 数组
        cJSON* arr = cJSON_Parse(joints_str.c_str());
        if (!arr || !cJSON_IsArray(arr)) {
            return std::string("Invalid joint angles format");
        }
        // 打包成二进制通过 UART 发送
        uint8_t cmd[7];
        for (int i = 0; i < 7 && i < cJSON_GetArraySize(arr); i++) {
            auto item = cJSON_GetArrayItem(arr, i);
            cmd[i] = (uint8_t)item->valueint;
        }
        uart_write_bytes(UART_NUM_1, cmd, 7);
        cJSON_Delete(arr);
        return std::string("ok");
    });

// MCP 工具：夹爪控制（快捷方式）
AddTool("robot.arm.gripper",
    "Control the gripper. Set to 0 for closed, 100 for fully open.",
    PropertyList({
        Property("position", kPropertyTypeInteger, 0, 100)
    }),
    [](const PropertyList& props) -> ReturnValue {
        uint8_t pos = (uint8_t)props["position"].value<int>();
        uint8_t cmd[1] = {pos};
        uart_write_bytes(UART_NUM_1, cmd, 1);
        return true;
    });

// MCP 工具：获取机械臂状态
AddTool("robot.arm.get_status",
    "Get the current status of the robot arm, including joint positions.",
    PropertyList(),
    [](const PropertyList& props) -> ReturnValue {
        uint8_t buf[7];
        int len = uart_read_bytes(UART_NUM_1, buf, 7, pdMS_TO_TICKS(100));
        if (len > 0) {
            cJSON* json = cJSON_CreateObject();
            cJSON* joints = cJSON_CreateArray();
            for (int i = 0; i < len; i++) {
                cJSON_AddItemToArray(joints, cJSON_CreateNumber(buf[i]));
            }
            cJSON_AddItemToObject(json, "joints", joints);
            return json;
        }
        return std::string("no data");
    });
```

### 6.3 VLA 模型服务 — smolVLA-0.5B（推荐方案）

> 论文: [smolVLA: Just how small can we make a VLA?](https://arxiv.org/abs/2503.19277)
> 代码: [github.com/ZhangYizhe/smolVLA](https://github.com/ZhangYizhe/smolVLA)

smolVLA 是目前**性价比最高的开源 VLA 模型**，0.5B 版本仅需 **~4GB 显存**，在真实世界抓取任务上成功率 **81.4%**。

#### 模型规格

| 版本                      | 总参数量 | 推理显存       | 推荐显卡                        | 抓取成功率 (Fractal) | 动作策略        |
| ------------------------- | -------- | -------------- | ------------------------------- | -------------------- | --------------- |
| **smolVLA-0.5B** ⭐ | ~1B      | **~4GB** | GTX 3060 / 4060 / 任何 4GB+ GPU | **81.4%**      | Action Chunking |
| **smolVLA-7B**      | ~8B      | ~16GB          | RTX 4090 / A4000+               | **87.9%**      | Action Chunking |

#### 为什么选 smolVLA-0.5B

| 优势                        | 说明                                                  |
| --------------------------- | ----------------------------------------------------- |
| 🔥**显存门槛极低**    | 4GB 就能跑，GTX 3060（二手 ~500元）轻松带得动         |
| 📈**抓取成功率高**    | 81.4%，比 Octo-Base 的 71.5% 高 10 个百分点           |
| 🎯**Action Chunking** | 一次预测未来 N 步动作序列，轨迹平滑不抖动             |
| 🗣️**语言理解强**    | 基于更强 LLM 骨干，能理解"红色杯子放左边"这类组合指令 |
| 🧩**SO101 可适配**    | 可通过 LoRA 微调适配 SO101 的关节空间                 |

#### 部署方式

在 OpenClaw 后端所在服务器上，启动一个独立的 VLA 推理服务：

```python
# vla_server.py — 在 OpenClaw 服务器上运行
from smolVLA import SmolVLA
import uvicorn
from fastapi import FastAPI, File, Form
from PIL import Image
import io

app = FastAPI()
model = SmolVLA.from_pretrained("ZhangYizhe/smolVLA-0.5B")

@app.post("/predict")
async def predict(image: bytes = File(...), instruction: str = Form(...)):
    img = Image.open(io.BytesIO(image))
    # 输入: 当前画面 + 语言指令
    # 输出: 未来 N 步的关节角度序列 (Action Chunking)
    action_chunk = model.predict(img, instruction)
    return {"action_chunk": action_chunk.tolist()}

uvicorn.run(app, host="0.0.0.0", port=8001)
```

OpenClaw 后端收到 LLM 的"抓取"意图后，调拍照 MCP 工具 → 拼装图片+指令 → 调 VLA 推理 → 将关节角度通过 WebSocket 下发到 ESP32。

#### 备选模型对比

| 模型                              | 显存   | 抓取成功率 | 动作平滑度         | 上手难度 | 适用场景                       |
| --------------------------------- | ------ | ---------- | ------------------ | -------- | ------------------------------ |
| **smolVLA-0.5B** 🥇         | ~4GB   | 81.4%      | ✅ Action Chunking | 低       | **最佳性价比，主力推荐** |
| **smolVLA-7B** 🥈           | ~16GB  | 87.9%      | ✅ Action Chunking | 中       | 有 RTX 4090 时选它             |
| **Octo-Base** 🥉            | ~2GB   | 71.5%      | ❌ Diffusion 易抖  | 低       | 无独显时的备选                 |
| **Octo-Small**              | <1GB   | 29.3%      | ❌                 | 最低     | 纯验证用                       |
| **Pi0**                     | ~24GB  | 较高       | ✅ Flow Matching   | 高       | 精细操作（叠衣服等）           |
| **RT-2**                    | 不可行 | -          | -                  | -        | 未开源，不适用                 |
| **自训练 Diffusion Policy** | ~2GB   | 取决于数据 | ✅                 | 中       | 固定场景精准抓取               |

#### 选型决策树

```
你的硬件情况？
    │
    ├── 4~8GB 显存（GTX 3060/4060、笔记本独显）
    │   └── 🥇 smolVLA-0.5B ← 最佳性价比
    │       └── Octo-Base（备选，显存更低但效果差一截）
    │
    ├── 12~16GB 显存（RTX 4070/4080、A4000）
    │   └── 🥇 smolVLA-7B（有 RTX 4070 Ti Super 16GB 可上）
    │       └── smolVLA-0.5B（轻松跑 + 量化）
    │
    ├── 24GB+（RTX 4090、A6000）
    │   └── 🥇 smolVLA-7B（最佳效果）
    │       └── Pi0（更精细操作，但适配工作量大）
    │
    └── 无独立显卡 / 只想快速验证
        └── Octo-Small（CPU 都能跑，但仅 29% 成功率）
```

**结论**：smolVLA-0.5B 是当前性价比天花板，一张 GTX 3060 就能让 SO101 实现 81% 抓取成功率的视觉抓取。

### 6.4 固件配置调整

将当前固件的 OTA/WebSocket 地址从官方后端指向自建的 OpenClaw 服务器：

- [main/Kconfig.projbuild:5](main/Kconfig.projbuild#L5) — OTA URL
- [main/protocols/websocket_protocol.cc:84-86](main/protocols/websocket_protocol.cc#L84-L86) — WebSocket 地址（从 NVS 读取）

---

## 7. 仿真与模型微调

在实际部署到真实机械臂之前，可以在仿真环境中验证 VLA 模型效果，并用自采数据集微调模型以获得更好性能。

### 7.1 仿真环境

#### 7.1.1 LeRobot + MuJoCo 仿真

LeRobot 内置了 SO-100 / SO101 兼容的仿真环境，基于 MuJoCo 物理引擎 + Gymnasium 接口：

```bash
# 安装 LeRobot 仿真依赖
pip install "lerobot[simulation]"
```

```python
# 启动 SO101 仿真环境
from lerobot.envs import set_env

env = set_env(
    "lerobot/so100/sim",    # SO101 兼容的仿真环境
    rendering=True,          # 可视化渲染
)

obs, info = env.reset()
for _ in range(1000):
    # 加载训练好的 VLA 模型推理
    action = model.predict(obs["image"], instruction="pick up the red cube")
    obs, reward, terminated, truncated, info = env.step(action)
    env.render()
```

#### 7.1.2 仿真环境下验证全链路

```
OpenClaw 后端 (模拟 LLM 意图)
    │ 模拟语音指令 "把那杯水拿过来"
    ▼
VLA 推理服务 (smolVLA-0.5B)
    │ 输入: 仿真画面 + "pick up the red cube"
    │ 输出: action_chunk
    ▼
仿真环境 (MuJoCo + Gymnasium)
    │ 执行动作 → 物理仿真 → 新画面
    │ 可视化渲染，实时观察抓取效果
    ▼
评估指标: 成功率 / 轨迹平滑度 / 碰撞次数
```

**优势**：不需要真实机械臂即可验证模型效果，零成本反复迭代。

### 7.2 模型微调 (Fine-tuning)

#### 7.2.1 数据采集

用 LeRobot 的遥操作（Teleoperation）功能，在真实 SO101 上录制示范数据：

```
┌──────────── 遥操作模式 ─────────────────────────────────┐
│                                                          │
│  操作员通过以下方式控制机械臂:                              │
│  ├─ SpaceMouse / 3D鼠标（推荐）—— 直观，精度高             │
│  ├─ VR 手柄 —— 沉浸式                                      │
│  └─ 键盘/游戏手柄 —— 简单但精度低                          │
│                                                          │
│  每录制一次 = 一条 demonstration（图像 + 动作序列）         │
│  建议: 每种物体/场景采集 20~50 条示范                       │
└──────────────────────────────────────────────────────────┘
```

```bash
# 使用 LeRobot 录制数据集
python lerobot/scripts/control_robot.py \
    record \
    --robot-path so100 \
    --fps 30 \
    --root ~/data/so101_grasp_dataset \
    --num-episodes 50
```

数据集结构：

```
~/data/so101_grasp_dataset/
├── episode_0/
│   ├── observation.images.camera_0/   ← 每帧图像
│   ├── action.joints/                  ← 对应的关节角度
│   └── task.json                       ← 指令描述
├── episode_1/
│   ...
└── meta.json
```

推荐采集的示范场景：

| 物体类型   | 指令示例                         | 采集次数 |
| ---------- | -------------------------------- | -------- |
| 彩色方块   | "pick up the red cube"           | 30       |
| 水杯       | "grasp the cup"                  | 20       |
| 笔/小物体  | "pick up the pen"                | 20       |
| 多物体排序 | "put the blue block on the left" | 30       |

#### 7.2.2 转换数据集格式

将采集的数据转为 smolVLA 可用的格式：

```bash
# 转为 HuggingFace Dataset 格式
python lerobot/scripts/export_dataset.py \
    --dataset-path ~/data/so101_grasp_dataset \
    --hf-repo your-name/so101-grasp-dataset \
    --push-to-hub  # 可选：推送到 HuggingFace
```

#### 7.2.3 LoRA 微调 smolVLA-0.5B

smolVLA 原生支持 LoRA 微调，只需少量显存（4~6GB）：

```bash
# 克隆 smolVLA 仓库
git clone https://github.com/ZhangYizhe/smolVLA.git
cd smolVLA

# LoRA 微调（4~6GB 显存即可）
python train.py \
    --model_name ZhangYizhe/smolVLA-0.5B \
    --dataset_path your-name/so101-grasp-dataset \
    --use_lora true \
    --lora_rank 16 \
    --batch_size 4 \
    --learning_rate 1e-4 \
    --num_epochs 50 \
    --output_dir ./checkpoints/so101_finetuned
```

关键参数说明：

| 参数                | 建议值    | 说明                                    |
| ------------------- | --------- | --------------------------------------- |
| `--use_lora`      | true      | 启用 LoRA，只训练 adapter，冻结基座模型 |
| `--lora_rank`     | 8~16      | 秩越高表达能力越强，但显存需求也越大    |
| `--batch_size`    | 4~8       | 根据显存调整，4GB 可用 batch_size=2     |
| `--learning_rate` | 1e-4~5e-5 | LoRA 通常比全参数微调用更大的 LR        |
| `--num_epochs`    | 30~50     | 50 条示范数据，30 轮左右收敛            |

训练完成后输出：

```
checkpoints/so101_finetuned/
├── adapter_model.safetensors   ← LoRA 权重 (仅 ~10MB)
├── adapter_config.json
└── training_args.json
```

#### 7.2.4 部署微调后的模型

```python
# 加载微调后的模型
from smolVLA import SmolVLA

model = SmolVLA.from_pretrained(
    "ZhangYizhe/smolVLA-0.5B",
    lora_weights="./checkpoints/so101_finetuned/adapter_model.safetensors"
)

# 在你的 SO101 上使用
action_chunk = model.predict(image, "pick up the red cube")
```

整个 LoRA 权重文件仅 **~10MB**，加载时基座模型 + adapter 总显存 ~4GB。

#### 7.2.5 微调效果预期

| 场景                 | 默认 smolVLA-0.5B    | 微调后 (50 条示范) |
| -------------------- | -------------------- | ------------------ |
| 通用物体抓取         | 81.4%                | 85~90%             |
| 你的桌面固定场景     | ~70%（未见过该环境） | **90~95%**   |
| 特定物体（你的水杯） | 可能失败             | **稳定抓取** |
| 语言指令跟随         | 英文为主             | 可微调支持中文指令 |

### 7.3 仿真 → 微调 → 部署 工作流总结

```
数据采集（真实机械臂）
    │ SpaceMouse 遥操作录制 50 条示范
    ▼
仿真验证（MuJoCo）
    │ 用默认 smolVLA 在仿真里跑一遍，看基线效果
    ▼
LoRA 微调
    │ 用自采数据微调 smolVLA-0.5B，产出 ~10MB adapter
    ▼
仿真验证微调后模型
    │ 对比微调前后的抓取成功率
    ▼
部署到真实机械臂
    │ 加载 adapter → OpenClaw 调 VLA 服务 → ESP32 → SO101
```

## 8. 分步实施路线

### Phase 1: 基础无线桥接

```
ESP32-S3 ←WiFi→ 接收命令 → UART → SO101 驱动板
```

- [ ] 接线：ESP32 IO9/IO10 → SO101 串口
- [ ] ESP32 端编写 UART 驱动 + MCP 工具
- [ ] 验证：PC 发 WiFi 命令 → ESP32 转发 → 机械臂动作

### Phase 2: 基础语音对话

```
ESP32 ←WebSocket→ OpenClaw 后端 ←配置→ LLM + TTS
```

- [ ] 部署 OpenClaw 后端（Docker）
- [ ] 修改固件 URL 指向自建服务器
- [ ] 验证语音对话正常
- [ ] 测试语音控制机械臂（"大臂抬到90度" → LLM 解析 → MCP 调用）

### Phase 3: 添加 VLA 视觉能力

```
ESP32 + 摄像头 ←MCP→ OpenClaw ←HTTP→ smolVLA-0.5B 推理服务
```

- [ ] 部署 smolVLA-0.5B 推理服务（独立进程，提供 HTTP API）
- [ ] OpenClaw 后端增加 VLA 调用逻辑（拍照 → 推理 → 下发关节指令）
- [ ] 验证拍照 + 推理链路

### Phase 4: 端到端语音抓取

```
语音指令 → LLM 解析 → 拍照 → VLA 推理 → ESP32转发 → 机械臂执行 → TTS 反馈
```

- [ ] LLM 意图到 VLA 动作的映射
- [ ] 异常处理与重试逻辑
- [ ] 全链路测试

---

## 9. 硬件连接示意

```
                         WiFi
                    ┌──────────┐
                    │  OpenClaw │  ← VLA 模型推理 (GPU)
                    │  后端     │
                    └─────┬────┘
                          │ WebSocket
                          │
                    ┌─────┴─────┐
                    │ ESP32-S3  │  ← 小智语音助手 + 无线桥接
                    │ (小智板)   │
                    ├───────────┤
                    │ IO9 TX ───┼──────────┐
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
            (肩部) (大臂)(小臂)(腕旋)(腕摆)(末端)
```

---

## 10. 优势对比

### 无线桥接 vs USB 连 PC

| 对比项     | USB 连 PC          | ESP32-S3 无线桥接           |
| ---------- | ------------------ | --------------------------- |
| 使用场景   | 必须开电脑         | 随时随地语音操控            |
| 设备体积   | PC + 线缆          | 一块芯片搞定                |
| 与语音集成 | 需要 PC 端额外软件 | 小智板本身就是语音助手      |
| 控制延迟   | USB 直连 < 1ms     | WiFi < 20ms（对机械臂足够） |
| 移动性     | 线缆束缚           | 全屋 WiFi 覆盖              |
| 开发量     | 现成 LeRobot SDK   | 需写 ESP32 端 UART 驱动     |

### 无线桥接 vs 直驱舵机

| 对比项       | UART 桥接（方案A）       | 直驱舵机（方案B）       |
| ------------ | ------------------------ | ----------------------- |
| 改硬件       | 只需杜邦线接串口         | 需重新布线、外加供电    |
| 利用原厂固件 | ✅ 保留 SO101 驱动板功能 | ❌ 完全绕过，需自写 PID |
| LeRobot 兼容 | ✅ 可通过转接使用        | ❌ 需要适配层           |
| 开发难度     | 低                       | 高                      |

---

## 11. 参考资源

- **OpenClaw 后端**: [github.com/OpenClaw/xiaozhi-esp32-server](https://github.com/OpenClaw/xiaozhi-esp32-server) / [github.com/xinnan-tech/xiaozhi-esp32-server](https://github.com/xinnan-tech/xiaozhi-esp32-server)
- **LeRobot**: [github.com/huggingface/lerobot](https://github.com/huggingface/lerobot) — 仿真/数据采集/训练框架
- **smolVLA (推荐)**: [github.com/ZhangYizhe/smolVLA](https://github.com/ZhangYizhe/smolVLA) / [arXiv 2503.19277](https://arxiv.org/abs/2503.19277) — 轻量 VLA，0.5B 仅需 4GB 显存
- **Octo**: [github.com/rail-berkeley/octo](https://github.com/rail-berkeley/octo) — 备选 VLA，显存更低但效果弱于 smolVLA
- **LeRobot 仿真环境**: [docs.lerobot.org](https://lerobot.readthedocs.io/en/latest/) — MuJoCo + Gymnasium
- **盒子桥 B站系列**: [全民DIY机械臂 EP1~EP4](https://www.bilibili.com/video/BV1LN411K7Ps/)
- **当前固件**: xiaozhi-esp32 v2.2.4
- **主控**: ESP32-S3-WROOM-1-N16R8 (16MB Flash + 8MB PSRAM)
- **空闲引脚**: IO13-IO20（CN1/CN2 扩展接口）
