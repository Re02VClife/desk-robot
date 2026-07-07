# 进度记录板

> 小智机械臂 VLA 集成项目 · 原子化推进记录
>
> 每完成一个功能点（F#），立即更新此文件。

---

## 当前状态

- **当前轮次**：第 9 轮 — LLM 直控机械臂 + 多步指令 + 安全约束
- **当前功能点**：F2.13 LLM 自由控臂 + 视觉 + 触摸交互 完成
- **上次更新**：2026-07-08

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
| F2.6 | 文字→MCP 控臂测试 | ✅ | 2026-07-07 | 端到端打通：文字→LLM→move_arm→MCP→SCServo→舵机 |
| F2.7 | SO101 硬件调试工具 | ✅ | 2026-07-04 | 限位读取/EEPROM dump/跳舞/安全测试 |
| — | 服务端 function_call 修复 | ✅ | 2026-07-04 | intent_type+func_handler+关键词 |
| F2.8 | UART 电平匹配 | ✅ | 2026-07-06 | Bus Servo Adapter V1.1: 3.3V必须接, TX/RX交叉 |
| F2.9 | 机器狗固件开发 | ✅ | 2026-07-06 | bread-compact-wifi + 4路舵机 + 3路触摸 + SH1106 OLED |
| F2.10 | 服务端机器狗适配 | ✅ | 2026-07-06 | prompt切换 + /ota命令 + IP迁移 |
| F2.11 | ZZPET 固件逆向 | ✅ | 2026-07-06 | 提取 7.6MB flash → 分区解析 + 字符串分析 + Ghidra 准备 |
| F2.12 | MCP 工具完善 | ✅ | 2026-07-07 | 3→6工具，增量模式，归位，急停，安全锁 |
| F2.13 | LLM 直控机械臂 | ✅ | 2026-07-08 | 关键词路由移除，deepseek-v4-flash直调MCP工具 |
| F2.14 | 多步指令支持 | ✅ | 2026-07-08 | "X 然后 Y 两秒后 Z" → 自动拆分顺序执行 |
| F2.15 | USB 摄像头模块 | ✅ | 2026-07-08 | camera_usb.py: opencv抓图→base64→LLM看图 |
| F2.16 | IO3 触摸交互 | ✅ | 2026-07-08 | 摸头传感器 + 14种轮换提示词 + LLM动作回应 |
| F2.17 | 静音/安全/超时 | ✅ | 2026-07-08 | TTS关闭、安全区域锁、文字超时15s→60s、排队修复 |
| F3.1 | smolVLA 环境搭建 | 🔲 | — | 需 GPU |
| F3.2 | FastAPI VLA 推理服务 | 🔲 | — | stub 已就绪，待 GPU |
| F3.3 | 模型权重下载 + 测试 | 🔲 | — | 需 GPU |
| F3.5 | VLA 链路测试 | 🔲 | — | 依赖硬件 + GPU |
| F4.1 | LLM 多轮推理 | 🔲 | — | 单轮OK，多轮函数调用链未闭环 |
| F4.2 | TTS 恢复 | 🔲 | — | EdgeTTS连不上，Linkerai 502 |
| F4.4 | 时延优化 | 🔲 | — | deepseek-v4-flash 每次5-20s |
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

---

### 2026-07-06：F2.8 UART 电平匹配 ✅

**背景**：ESP32 !GOPEN 指令日志显示发送成功但舵机不动，排查电平问题。

**发现**：Bus Servo Adapter V1.1 驱动板丝印 `G T R V V`：
- 3.12V V 脚 = 3.3V 输出（始终有电）
- 0.09V V 脚 = 5V 输出（插 USB 才有电）
- VCC 必须接！否则 UART 逻辑电路不供电
- TX/RX 是标准**交叉接法**（ESP32 TX → 板子 R, ESP32 RX → 板子 T）
- 跳线帽 2 针：短接=USB模式, 断开=UART模式

**正确接线**（商家确认）：
```
ESP32          驱动板
 TX  (IO9)  →   R
 RX  (IO10) ←   T
 3.3V       →   V (3.12V脚)
 GND        →   G
```

### 2026-07-06：F2.9 机器狗固件开发 ✅

**产出**：
- `feature/machine-dog` 分支（commit 1424ed7）
- 修改 `main/boards/bread-compact-wifi/config.h` — 4路舵机 + 3路触摸引脚
- 修改 `main/boards/bread-compact-wifi/compact_wifi_board.cc` — LEDC PWM驱动 + MCP工具
- 修改 `main/text_console.cc` — 新增 `/ota` 命令
- 修改 `sdkconfig` — BREAD_COMPACT_WIFI + SH1106 128x64 OLED

**编译踩坑**：
1. `LEDC_TIMER_16_BIT` → ESP-IDF v5.5 最高 14bit → 改为 `LEDC_TIMER_14_BIT`
2. 屏幕雪花 → 1.3" OLED 是 SH1106 不是 SSD1306 → 切换 OLED 类型
3. 镜像方向 → 多次调试 → 最终 `MIRROR_X=false, MIRROR_Y=true`

**MCP 工具**：`dog.servo.set_angle`, `dog.servo.set_all`, `dog.servo.center`, `dog.touch.read`

### 2026-07-06：F2.10 服务端机器狗适配 ✅

**服务端改动**：
- `.config.yaml` IP → 10.183.125.233（WiFi 热点切换导致 IP 漂移）
- 注释掉 `move_arm` 函数，避免 LLM 误调
- prompt 切换为机器狗角色（4条腿 + 3根触须）
- LLM 模型 qwen-plus → qwen-flash（解决超时无响应）
- ASR：`pip install funasr` (v1.3.14)
- Opus：`pip install opuslib-next` (v1.3.0)

**踩坑**：
1. IP 漂移：ESP32 IP 10.183.125.x vs OTA URL 192.168.123.x → 两个子网不通 → 改 URL
2. LLM 无回应：qwen-plus 2分钟超时 → 降级 qwen-flash
3. OTA 成功后 WS 连不上：.config.yaml websocket 写死 192.168.123.25
4. 无声音：全链路通但硬件功放侧 SD 脚悬空

### 2026-07-06：F2.11 ZZPET 固件逆向 ✅

**固件**：`ZZPET-BOT v1.3.4.bin` (7.6MB, ESP32-S3, IDF v5.5.1)

**发现**：
- 板型 `zzpet-s3`，5路舵机（4腿+1尾），SH1106/SSD1306 OLED，摄像头
- MCP 工具：`self.zzpet.get_status/stop/set_trim/get_trims`
- 云端 API：`admin.zzpet.top/prod-api`
- 配置项：battery_detection, display_type(0-2), pcb_version, screen_flip, led_num

**提取**：完整分区 + Segments + 21805 字符串 → `zzpet_extracted/`
**下一步**：Ghidra 12.1.2 + Xtensa LX7 反编译

---

### 2026-07-07~08：F2.12~F2.17 MCP全链路打通 ✅

**背景**：Phase 2 核心目标——用户说一句话→机械臂执行动作。经过两天密集开发和踩坑，完整链路已通。

**硬件层确认**：
- ✅ SCServo 协议链路：ESP32 UART1(1Mbps) → Bus Servo Adapter → 6舵机全部在线
- ✅ 接线方案：IO9(TX)→R, IO10(RX)→T, 3.3V→V, GND→G, 跳线帽断开
- ✅ 启动时序修复：舵机比ESP32慢启动，EnsureTorqueEnabled()自动恢复扭矩

**固件 MCP 工具**（`xiaozhi_custom_board.cc`）：
- robot.arm.move_joints — 支持 relative 增量模式 + 安全区域锁
- robot.arm.move_joint — 🆕 单关节控制
- robot.arm.home — 🆕 一键归位
- robot.arm.stop — 🆕 急停
- robot.arm.gripper — 支持精确 position 参数
- robot.arm.get_status — 增强：物理角度+归一化角度+扭矩+home偏移

**安全约束**（固件+提示词双重保护）：
- 固件安全锁：J2<15°→锁定J1旋转±15°，J3<20°→禁止J2下降
- 提示词安全区：跳舞范围 [70-110, 20-120, 40-160, 80-170, 20-160]
- 文字超时 15s→60s，连接中文字排队不丢弃

**服务端关键修复**：
1. `plugin_executor.py`: async 函数调用缺 await → 协程从未执行（根因排查最久）
2. `mcp_handler.py`: has_tool() 不匹配净化名（robot.arm.gripper vs robot_arm_gripper）
3. `move_arm.py`: 重构为增量式+多步指令+中文数字支持
4. `intentHandler.py`: 静音模式 + ARM_KEYWORDS 移除
5. TTS 全局关闭（`_TTS_ENABLED=False`）

**LLM 直控**：
- 模型：deepseek-v4-flash via 阿里百炼
- MCP工具描述精简 ~70%
- 所有指令交LLM推理，自行选择调用 move_arm 或直调 MCP 工具
- LLM 可自由编排多步动作序列（通过 move_arm 的多步指令）

**当前限制**：
- LLM 多轮函数调用未闭环（只能单轮规划→move_arm 多步执行）
- TTS 不可用（EdgeTTS 连不上，Linkerai 502），暂时静音
- LLM 每次推理 5-20s，复杂指令可能超时

**触动总结**：
```
用户: "跳个舞吧"
  → ESP32 WebSocket → 本地服务器
  → LLM(deepseek-v4-flash) 推理 5-10s
  → 调 move_arm("归位然后抬起再左转20度再右转20度再点头…")
  → 拆成9步顺序执行 → 机械臂跳舞
  → 响应回ESP32 → idle
```
完整链路：**语音/文字 → LLM推理 → MCP工具 → SCServo → 舵机动作** ✅

---

### 2026-07-07：F2.12 MCP 工具完善 ✅

**背景**：原有3个基础MCP工具（move_joints/gripper/get_status），功能单一：
- move_joints 始终覆盖全部6关节，无法增量移动
- 无归位/急停功能
- get_status 返回信息不足
- move_arm.py 硬编码未指定关节为90°，导致机械臂突然跳变

**参考项目**：[IliaLarchenko/robot_MCP](https://github.com/IliaLarchenko/robot_MCP)（MCP+SO101）、[beam-bots/bb_so101](https://github.com/beam-bots/bb_so101)（STS3215完整协议）

**固件端改动** (`xiaozhi_custom_board.cc`):
- 🆕 `robot.arm.move_joint` — 单关节控制（joint+angle+speed）
- 🆕 `robot.arm.home` — 一键归位到HOME步值 [2019,805,2979,2869,1082,2246]
- 🆕 `robot.arm.stop` — 急停：释放6舵机扭矩
- 🔧 `move_joints` — 新增 `relative` 参数支持增量模式（相对当前位置偏移）
- 🔧 `gripper` — 新增 `position` 参数支持精确开度控制（二态开合仍然可用）
- 🔧 `get_status` — 新增 `home_offset_steps`、`torque_enabled`、`physical_deg`、`angle` 字段
- 🆕 `EnsureTorqueEnabled()` — 急停后自动恢复扭矩（move_joints/move_joint/home 自动调用）
- 📝 所有工具描述加入关节索引和参考角度信息

**服务端改动** (`move_arm.py`):
- 🔧 `_get_current_angles()` — 调用 get_status 获取当前姿态
- 🔧 `_parse_instruction()` → 增量式：只修改指定关节，其他关节保持当前值
- 🆕 相对指令：「再高一点」→ +10°，「再低一点」→ -10°
- 🆕 新增路由：归位→robot.arm.home, 急停→robot.arm.stop
- 🆕 降级策略：get_status 失败时使用 HOME 参考角度

**角色提示词** (`.config.yaml`):
- 🆕 追加机械臂模式 prompt（注释状态），含增量控制说明和安全规则

**验证**：
- ✅ `bash esp_idf_build.sh build` 编译通过，0 错误
- ⏭️ 硬件测试待进行（需烧录固件 → ESP32上线 → 测试各MCP工具）

**下一步**：烧录固件 → 通过 arm_cli.py 或 text_console 测试新工具

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
| ~~硬件接线（IO9/IO10 ↔ SO101）~~ | F2.6 控臂测试 | ✅ 已确认接线方案 |
| 舵机位置命令不执行 | F2.9 | ⚠️ 扭矩使能通但位置不动 |
| GPU 可用性 | Phase 3 全部 | 🟡 |
| Ghidra 安装 | ZZPET 反编译 | 🟡 |
| 麦克风/扬声器 | 语音输入输出 | 🟡 文字输入可用，ASR+Opus已装，硬件功放待查 |

> 🆕 2026-06-25：F2.4 固件烧录 + F2.5 中文端到端已打通。VLA 插件就绪，待 GPU + 机械臂接线后进入 Phase 3。
