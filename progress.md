# 进度记录板

> 小智机械臂 VLA 集成项目 · 原子化推进记录
>
> 每完成一个功能点（F#），立即更新此文件。

---

## 当前状态

- **当前轮次**：第 6 轮 — Phase 2 硬件联调（SCServo 直连 + 服务端 MCP 链路）
- **当前功能点**：F2.6 电平匹配 / MCP 调用链路
- **上次更新**：2026-07-04 23:30

---

## 进度总览

| F# | 功能点 | 状态 | 完成时间 | 备注 |
|----|--------|------|----------|------|
| — | 工程目录骨架搭建 | ✅ | 2026-06-23 | specs/ + tests/ + progress.md |
| — | specs/ 文档（4 份） | ✅ | 2026-06-23 | 项目行动手册 + Phase2/3/4 规格 |
| F2.1 | OpenClaw 服务器部署 | ✅ | 2026-06-23 | Python venv 直跑 |
| F2.2 | LLM + TTS 配置 | ✅ | 2026-06-25 | qwen-turbo via 阿里百炼 + EdgeTTS |
| F2.3 | 角色提示词编写 | ✅ | 2026-06-23 | 含机械臂 6 关节控制 + 安全规则 |
| F2.4 | 固件烧录到 ESP32 | ✅ | 2026-06-25 | 编译烧录成功，WebSocket 直连打通 |
| F2.5 | 文字→AI 端到端测试 | ✅ | 2026-06-25 | 中文输入 LLM 回复全链路通 |
| F3.4 | OpenClaw VLA 集成 | ✅ | 2026-06-25 | vla_grasp 插件 + 配置 + 测试 |
| F4.3 | 安全限位（固件端） | ✅ | 2026-06-25 | 关节角度 0-180° 裁剪 + 编译通过 |
| — | 中文 UTF-8 修复 | ✅ | 2026-06-25 | text_console.cc: c<127 → c!=127 |
| F2.6 | 文字→MCP 控臂测试 | 🔄 | — | SCServo直连已改，3.3V↔5V 电平问题 |
| F2.7 | SO101 硬件调试工具 | ✅ | 2026-07-04 | 限位读取/EEPROM dump/跳舞/安全测试 |
| — | 服务端 function_call 修复 | ✅ | 2026-07-04 | intent_type+func_handler+关键词 |
| F2.8 | UART 电平匹配 | 🔲 | — | ESP32 3.3V → SO101 5V 总线，需上拉 |
| F3.1 | smolVLA 环境搭建 | 🔲 | — | 需 GPU |
| F3.2 | FastAPI VLA 推理服务 | 🔲 | — | stub 已就绪，待 GPU |
| F3.3 | 模型权重下载 + 测试 | 🔲 | — | 需 GPU |
| F3.5 | VLA 链路测试 | 🔲 | — | 依赖硬件 + GPU |
| F4.1 | LLM 意图解析 | 🔲 | — | |
| F4.2 | 多轮交互 | 🔲 | — | |
| F4.4 | 时延优化 | 🔲 | — | |
| F4.5 | 多场景抓取测试 | 🔲 | — | |

---

## 详细记录

### 2026-06-23：工程目录骨架搭建 ✅

**产出**：
- `specs/项目行动手册.md` — Agent 执行总纲领（5原则+执行链+分层映射）
- `specs/phase2-语音对话控臂.md` — Phase 2 功能规格
- `specs/phase3-VLA视觉推理.md` — Phase 3 功能规格
- `specs/phase4-端到端联调.md` — Phase 4 功能规格
- `tests/conftest.py`, `tests/test_vla_inference.py`, `tests/test_mcp_arm_tools.py`
- `progress.md` — 本文件

### 2026-06-23：F2.1 服务器部署 ✅

**服务器**：OpenClaw Python 直跑（Windows，非 Docker）

**环境**：
- Python 3.11.2 venv（`xiaozhi-esp32-server/main/xiaozhi-server/venv/`）
- 全部依赖已安装（含 torch, openai, edge_tts, websockets 等）
- ffmpeg 8.1.1（winget 安装）

**启动命令**（CMD）：
```cmd
set PATH=C:\Users\24628\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin;%PATH%
cd C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server
venv\Scripts\python.exe app.py
```

**服务地址**：
- WebSocket: `ws://192.168.123.25:8000/xiaozhi/v1/`
- OTA: `http://192.168.123.25:8003/xiaozhi/ota/`

### 2026-06-23：Windows 兼容适配

| 适配项 | 文件 | 方案 |
|--------|------|------|
| opus 编码 | 9 个文件 3 级回退 | opuslib_next → opuslib → opus_stub |
| opus stub | `core/utils/opus_stub.py` (新建) | 纯 Python 桩，返回最小有效 opus 帧 |
| ASR 容错 | `core/utils/modules_initialize.py` | 初始化失败 → None，不阻塞启动 |
| ffmpeg 检查 | `app.py` | try/except → warning 不致命 |
| opus constants | `opus_encoder_utils.py` | 修正 stub 回退的模块引用 |

### 2026-06-23：F2.2 LLM 配置 ✅

**LLM**：阿里百炼 `deepseek-v4-flash`
- base_url: `https://dashscope.aliyuncs.com/compatible-mode/v1`
- api_key: 阿里百炼 Key
- model_name: `deepseek-v4-flash`

**TTS**：微软 Edge TTS（免费）
- voice: `zh-CN-XiaoxiaoNeural`

### 2026-06-23：F2.3 角色提示词 ✅

角色设定：小智（台湾女生）+ 机械臂操控能力
- MCP 工具：`robot.arm.move_joints`, `robot.arm.gripper`, `robot.arm.get_status`
- 6 关节角度参考位置 + 安全规则

### 2026-06-23：F2.5 文字→AI 端到端测试 ✅

**全链路验证通过**：
```
WebSocket 连接 → Hello 握手 → MCP 初始化
  → 发送文字 "用一句话介绍你自己"
  → STT 识别 → LLM (deepseek-v4-flash) 回复
  → TTS (EdgeTTS) 生成语音 → Opus 编码 → 44 帧音频发送
⏱️ 时延 ~2-3 秒
```

---

### 2026-06-25：F4.3 安全限位（固件端）✅

**改动文件**：
- `main/boards/xiaozhi-custom/xiaozhi_custom_board.cc` — 修改 `robot.arm.move_joints` 回调
- `tests/test_joint_safety.py` — 🆕 11 个算法测试

**改动内容**：
- 在 `move_joints` MCP 回调中添加 cJSON 解析 + 0-180° 裁剪
- 越界时输出 ESP_LOGW 警告日志（含原始值和裁剪后值）
- 不对 SendRobotCommand 做修改，只在回调层防护

**验证结果**：
- ✅ `bash esp_idf_build.sh build` 编译通过，0 错误 0 警告
- ✅ `pytest tests/test_joint_safety.py -v` 11/11 全部通过
  - 边界值：正常值不变、负值→0、>180→180、0/180不变
  - 多越界：4个同时越界正确裁剪
  - 序列化往返：JSON 序列化/反序列化后裁剪逻辑一致

### 2026-06-25：F3.4 OpenClaw VLA 集成 ✅

**改动文件**：
- `plugins_func/functions/vla_grasp.py` — 🆕 VLA 视觉抓取函数插件
- `data/.config.yaml` — 修改：Intent 切换到 function_call + 注册 vla_grasp + 新增 VLA 配置段
- `tests/test_vla_grasp.py` — 🆕 10 个单元测试 + 3 个集成测试

**插件实现**：
- 三步流程：① 拍照(camera.take_photo) → ② VLA推理(HTTP /vla/infer) → ③ 逐帧执行动作(move_joints + gripper)
- 容错设计：MCP未就绪、VLA不可达、推理超时、动作执行失败 → 全部优雅降级
- 图片提取：兼容纯base64、JSON、dict、bytes 四种格式
- ToolType: SYSTEM_CTL，参数：instruction（抓取指令）

**配置变更**：
```yaml
selected_module.Intent: nointent → function_call  # 启用工具调用
VLA:
  server_url: "http://localhost:8080"
  timeout: 30
  enabled: true
```

**验证结果**：
- ✅ `pytest tests/test_vla_grasp.py -v -k "not requires_server"` 10/10 全部通过
  - 图片提取 8 个用例：纯base64、JSON格式、dict格式、bytes、短字符串、空dict
  - 错误处理 2 个用例：MCP未初始化、VLA未启用
- ⏭️ 集成测试 3 个跳过（VLA stub 服务未启动，需手动运行）

### 2026-06-25：F2.4 固件烧录 + F2.5 中文端到端 ✅

**排障历程**：
1. ❌ WebSocket 8000 → 不通（ESP32 websocket client 库问题）
2. ❌ OTA + WS URL override 混淆（端口不一致）
3. ❌ MQTT 模式 TLS 加密不兼容（`ESP_ERR_ESP_TLS_CONNECTION_TIMEOUT`）
4. ❌ API Key 过期 → 返回 `system_error_response`
5. ❌ 中文被过滤（`text_console.cc` ASCII 限定 `c<127`）
6. ✅ WebSocket 8003 直连 + 新 API Key + UTF-8 修复 → 全通

**最终配置**：
- 服务器：WS=8003, HTTP/OTA=8000
- ESP32：OTA_URL=`http://192.168.123.25:8000/xiaozhi/ota/`, WS override=空（OTA 下发）
- LLM：qwen-turbo via 阿里百炼
- TTS：LinkerAI

**验证结果**：
```
> 你好
<< 嗨～你好呀！今天过得怎么样？
```

### 2026-06-25：中文 UTF-8 修复 ✅

**改动**：`main/text_console.cc:78` — `c >= 32 && c < 127` → `c >= 32 && c != 127`

UTF-8 中文编码使用 >127 的字节，旧代码只接受 ASCII 可打印字符，中文被丢弃。

---

### 2026-07-04：固件 SCServo 直连改造 ✅

**背景**：SO101 排针接的是舵机总线（SCServo 二进制协议，1M bps），不是 JSON 串口。之前发 JSON 到排针，MCU 不认识。

**固件改动**：
- `config.h`: UART1 波特率 115200 → **1000000** bps
- `xiaozhi_custom_board.cc`:
  - 新增 SCServo 协议函数：`ScsChecksum`, `ScsWriteByte`, `ScsWriteWord`, `ScsReadWord`
  - 新增 6 关节限位表 `JOINT_LIMITS[6][2]`，角度→步值映射 `AngleToSteps()`
  - `move_joints` MCP 工具：角度度数值 → 步值 → SCServo 写入
  - `gripper` MCP 工具：open=true→2100, open=false→2400
  - `get_status` MCP 工具：读取 6 舵机当前位置，返回 JSON
  - 启动时自动使能 6 舵机扭矩（`ScsWriteByte(sid, 40, 1)`）
- `text_console.cc`: 新增 `!GOPEN`/`!GCLOSE` 命令，直发 SCServo 二进制包（纯硬件测试）
- `mcp_server.cc`: 新增 `ESP_LOGI` 诊断日志 `🔧 MCP tools/call`

**验证**：
- ✅ `bash esp_idf_build.sh build` 编译通过
- ✅ 启动日志：`1000000 bps (SCServo直连)` + `6 个舵机扭矩已使能`
- ✅ `!GOPEN` → `SCServo 夹爪: 张开 → 2100` + `GRIPPER_OPEN`
- ❌ 舵机实际未动 — **3.3V ↔ 5V 电平不匹配**，需加 1kΩ 上拉电阻

### 2026-07-04：服务端 function_call 链路修复 ✅

**4 个依次修复的 Bug**：
1. `ARM_KEYWORDS` 缺少「打开」→ 补全
2. `intent_type` 始终 `"nointent"` → `__init__` 中直接从 config 读取
3. `func_handler` 未初始化 → 把 `_initialize_intent()` 移到音频初始化**之前**
4. `func_handler` 重复初始化清理

**验证**：
- ✅ `intent_type='function_call'`
- ✅ `检测到机械臂指令，直接路由到 move_arm`
- ✅ `func_handler` 包含 `move_arm`
- ⚠️ `call_mcp_tool` 后续卡住（待排查，可能与 WebSocket 不稳定有关）

### 2026-07-04：SO101 测试工具集 ✅

新增/改进的测试脚本：
- `so101_safe_test.py` — 零依赖 pyserial，内联 SCServo 协议，±40步微动
- `so101_check_limits.py` — 读取 6 关节 EEPROM 限位（地址 9/11，小端序）
- `so101_dump_eeprom.py` — Dump 舵机控制表（排障用）
- `so101_read_pos.py` — 读取当前位置 + 限位（用于记录 HOME）
- `so101_dance.py` — 跳舞脚本，基于 HOME 偏移 + 限位裁剪 + 平滑插值
- `quick_test.py` — ESP32 串口通信快速诊断
- `ws_mcp_test.py` — WebSocket MCP 直连测试

---

## 服务器启动清单

每次启动服务器前确认：

```cmd
# 1. 杀掉旧进程（如果端口被占）
taskkill -PID <pid> -F  # 或重启电脑

# 2. 启动
cd C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server
venv\Scripts\python.exe app.py
```

**当前服务端口**：
- WebSocket: `ws://192.168.123.25:8003/xiaozhi/v1/`
- OTA: `http://192.168.123.25:8000/xiaozhi/ota/`

每次启动服务器前确认：

```cmd
# 1. 设置 ffmpeg PATH
set PATH=C:\Users\24628\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin;%PATH%

# 2. 启动
cd C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server
venv\Scripts\python.exe app.py
```

---

## 熔断记录

（暂无）

---

## 关键阻塞项

| 阻塞项 | 影响阶段 | 状态 |
|--------|----------|------|
| 硬件接线（IO9/IO10 ↔ SO101） | F2.6 控臂测试 | 🔴 |
| GPU 可用性 | Phase 3 全部 | 🟡 |
| 麦克风硬件故障 | 语音输入 | 🟡 文字输入可用 |

> 🆕 2026-06-25：F2.4 固件烧录 + F2.5 中文端到端已打通。VLA 插件就绪，待 GPU + 机械臂接线后进入 Phase 3。
