# Phase 2：基础语音对话 + 语音控制机械臂

> 状态：🔴 待启动 | 预估周期：1 周 | 前置：Phase 1 硬件接线完成

---

## 1. 目标

实现「语音/文字指令 → LLM 解析意图 → MCP 工具调用 → 机械臂动作」的完整链路。

---

## 2. 功能点清单

| F# | 功能点 | 产出物 | 验证方式 |
|----|--------|--------|----------|
| F2.1 | OpenClaw Docker 部署 | docker-compose.yml 配置 | WebSocket 端口可达 |
| F2.2 | LLM + TTS 配置 | config.yaml | 文字消息有 TTS 回复 |
| F2.3 | 角色提示词（机械臂控制） | prompt 字段 | LLM 正确调用 MCP 工具 |
| F2.4 | 固件 WS URL 编译烧录 | sdkconfig + 固件 | 设备连接自建服务器 |
| F2.5 | 基础语音对话测试 | 测试记录 | 一问一答正常 |
| F2.6 | 文字→MCP 控臂测试 | 测试记录 | 机械臂实际动作 |

---

## 3. F2.1 功能规格：OpenClaw Docker 部署

### 需求描述

在本地 Windows 机器或 Linux 服务器上，使用 Docker 部署 OpenClaw 后端服务。

### 服务器代码位置

```
c:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server\
```

### 参考文件

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | Docker 编排文件（Python 服务） |
| `Dockerfile-server` | 生产镜像（基于 server-base） |
| `Dockerfile-server-base` | 基础镜像（python:3.10-slim + 系统依赖） |
| `config.yaml` | 主配置文件（1152 行） |
| `app.py` | 服务入口（asyncio 启动） |
| `requirements.txt` | Python 依赖列表 |

### 关键配置项

```yaml
# docker-compose.yml 端口映射
ports:
  - "8000:8000"   # WebSocket 服务
  - "8003:8003"   # HTTP 服务（OTA + 视觉）
```

### 验收标准

- `docker compose ps` 显示服务 running
- `ws://<server_ip>:8000` WebSocket 可连接

---

## 4. F2.2 功能规格：LLM + TTS 配置

### 需求描述

配置 LLM（DeepSeek-V3）和 TTS（Edge-TTS），使文字消息能获得 TTS 语音回复。

### 配置文件

`config.yaml` 的 `selected_module` 部分：

```yaml
selected_module:
  VAD: SileroVAD
  ASR: SenseVoiceASR        # 或 FunASR
  LLM: DeepSeekLLM          # deepseek-chat（推荐，便宜好用）
  VLLM: ChatGLM4V           # 视觉 LLM（Phase 3 用）
  TTS: EdgeTTS              # 微软 Edge TTS（免费）
  Memory: nomem             # 暂不使用记忆
  Intent: function_call     # 函数调用模式（支持 MCP 工具调用）
```

### DeepSeek 凭据

```yaml
LLM:
  DeepSeekLLM:
    type: openai
    api_key: "<your-deepseek-api-key>"
    base_url: https://api.deepseek.com/v1
    model: deepseek-chat
    max_tokens: 2048
    temperature: 0.7
```

### 验收标准

1. 通过文字消息发送"你好"
2. 服务器返回 LLM 文本回复
3. ESP32 扬声器播放 TTS 语音
4. 屏幕显示回复文字

---

## 5. F2.3 功能规格：角色提示词编写

### 需求描述

编写含机械臂控制指令的角色提示词，使 LLM 在对话中正确识别控臂意图并调用 MCP 工具。

### 现有 MCP 工具（来自 ESP32）

| 工具名 | 参数 | 功能 |
|--------|------|------|
| `robot.arm.move_joints` | `angles`: 6 元素 JSON 数组，`speed`: 1-100 | 移动 6 个关节 |
| `robot.arm.gripper` | `open`: bool, `speed`: 1-100 | 夹爪开合 |
| `robot.arm.get_status` | 无 | 查询机械臂状态 |

### 角色提示词模板

在 `config.yaml` 的 `prompt:` 字段中，在现有角色设定基础上追加：

```yaml
prompt: |
  你是小智，一个有机械臂的 AI 助手。你来自中国台湾，讲话亲切可爱。
  
  ## 机械臂控制能力
  你可以控制一个 6 轴机械臂（SO101）。当用户要求操作机械臂时，使用以下工具：
  - robot.arm.move_joints：移动关节，angles 是 6 个角度的数组（单位：度），speed 1-100
  - robot.arm.gripper：开合夹爪，open=true 张开，open=false 闭合
  - robot.arm.get_status：查询机械臂当前状态
  
  ### 控臂指令映射
  - "抬起/举起" → 增加第 1-2 个关节角度
  - "放下/降低" → 减小第 1-2 个关节角度
  - "左转/右转" → 调整第 1 个关节角度
  - "抓/拿/夹" → gripper open=false
  - "放/松/开" → gripper open=true
  - "回零/归位" → 所有关节回到 0 度
  
  ### 安全规则
  - 夹爪速度默认 30（慢速，防止夹伤）
  - 关节移动速度默认 40（中速，防止碰撞）
  - 每次移动前告知用户即将执行的动作
  - 如果用户指令可能导致危险（如超出关节限位），提醒用户并拒绝执行
```

### 验收标准

1. 发送"抬起机械臂到90度"
2. LLM 返回 function_call，工具名 `robot.arm.move_joints`
3. 参数 `angles` 包含合理的关节角度值
4. MCP 工具调用成功，ESP32 通过 UART 发送对应 JSON 指令

---

## 6. F2.4 功能规格：固件编译烧录

### 需求描述

编译含 `CONFIG_WEBSOCKET_URL_OVERRIDE` 设置的固件，使 ESP32 启动后连接自建服务器。

### 配置入口

```
Kconfig: 小智AI 应用配置 → WebSocket 服务器地址覆盖
```

### 编译命令

```bash
cd c:\Users\24628\Desktop\vscode\xiaozhiAI
bash esp_idf_build.sh build
```

### 烧录命令

```bash
python -m esptool --chip esp32s3 -p COM6 -b 460800 \
  --before default_reset --after hard_reset write_flash \
  --flash_mode dio --flash_freq 80m --flash_size 16MB \
  0x0 build/bootloader/bootloader.bin \
  0x8000 build/partition_table/partition-table.bin \
  0xd000 build/ota_data_initial.bin \
  0x20000 build/xiaozhi.bin
```

### 烧录前步骤

1. IO0 接 GND → 按 RST → 拔掉 IO0-GND（进入下载模式）
2. 执行烧录命令

### 验收标准

1. 编译 0 错误 0 警告
2. 烧录后设备启动
3. 串口日志显示连接到自建服务器地址
4. 文字控制台可用（输入文字→回车→服务器回复）

---

## 7. F2.5-F2.6：测试验证

### F2.5 基础语音对话测试

| 测试用例 | 输入 | 期望输出 |
|----------|------|----------|
| 简单问候 | "你好" | TTS 语音回复 + 屏幕文字 |
| 知识问答 | "今天天气怎么样" | 自然语言回复 |
| 角色一致性 | "你是谁" | 小智角色回复 |

### F2.6 文字→MCP 控臂测试

| 测试用例 | 输入 | 期望行为 |
|----------|------|----------|
| 抬臂 | "把大臂抬到45度" | `move_joints` 被调用，关节 1-2 设为 ~45° |
| 抓取 | "合上夹爪" | `gripper(open=false)` 被调用 |
| 释放 | "张开夹爪" | `gripper(open=true)` 被调用 |
| 组合指令 | "抬起手臂然后张开夹爪" | 依次调用 `move_joints` + `gripper` |
| 状态查询 | "机械臂现在什么状态" | `get_status` 被调用 |

---

## 8. 依赖关系

```
F2.1 (Docker 部署)
  └→ F2.2 (LLM/TTS 配置)
      └→ F2.3 (角色提示词)
          └→ F2.4 (固件烧录)
              ├→ F2.5 (语音对话测试)
              └→ F2.6 (控臂测试) ← 依赖 Phase 1 硬件接线
```
