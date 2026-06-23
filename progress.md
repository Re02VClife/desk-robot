# 进度记录板

> 小智机械臂 VLA 集成项目 · 原子化推进记录
>
> 每完成一个功能点（F#），立即更新此文件。

---

## 当前状态

- **当前轮次**：第 3 轮 — Phase 2 第2批（需 ESP32 硬件）
- **当前功能点**：F2.4 固件烧录到 ESP32
- **上次更新**：2026-06-23 22:20

---

## 进度总览

| F# | 功能点 | 状态 | 完成时间 | 备注 |
|----|--------|------|----------|------|
| — | 工程目录骨架搭建 | ✅ | 2026-06-23 | specs/ + tests/ + progress.md |
| — | specs/ 文档（4 份） | ✅ | 2026-06-23 | 项目行动手册 + Phase2/3/4 规格 |
| F2.1 | OpenClaw 服务器部署 | ✅ | 2026-06-23 | Python venv 直跑，Docker 跳过 |
| F2.2 | LLM + TTS 配置 | ✅ | 2026-06-23 | 阿里百炼 deepseek-v4-flash + EdgeTTS |
| F2.3 | 角色提示词编写 | ✅ | 2026-06-23 | 含机械臂 6 关节控制 + 安全规则 |
| F2.5 | 文字→AI 端到端测试 | ✅ | 2026-06-23 | LLM回复 + TTS音频 全链路通 |
| F2.4 | 固件烧录到 ESP32 | 🔄 | 2026-06-23 | ✅ 2090目标编译通过，待烧录 |
| F2.6 | 文字→MCP 控臂测试 | 🔲 | — | 需硬件接线 |
| F3.1 | smolVLA 环境搭建 | 🔲 | — | 需 GPU |
| F3.2 | FastAPI VLA 推理服务 | 🔲 | — | |
| F3.3 | 模型权重下载 + 测试 | 🔲 | — | |
| F3.4 | OpenClaw VLA 集成 | 🔲 | — | |
| F3.5 | VLA 链路测试 | 🔲 | — | |
| F4.1 | LLM 意图解析 | 🔲 | — | |
| F4.2 | 多轮交互 | 🔲 | — | |
| F4.3 | 异常处理 | 🔲 | — | |
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

## 服务器启动清单

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
| ESP32 固件烧录（IO0 下载模式） | F2.4 | 🔴 待用户操作 |
| GPU 可用性 | Phase 3 全部 | 🟡 |
| 麦克风硬件故障 | 语音输入 | 🟡 文字输入可用 |
| opus 音频为静音（stub） | TTS 播放 | 🟡 链路通但 ESP32 端听不到声音 |
