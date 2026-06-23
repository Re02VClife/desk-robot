# Phase 3：VLA 视觉推理能力

> 状态：🔲 未开始 | 预估周期：1-2 周 | 前置：Phase 2 完成 + GPU 可用

---

## 1. 目标

部署 smolVLA-0.5B 视觉-语言-动作模型，实现「拍照 → 识别物体 → 生成抓取动作序列」的推理链路。

---

## 2. 功能点清单

| F# | 功能点 | 产出物 | 验证方式 |
|----|--------|--------|----------|
| F3.1 | smolVLA 环境搭建 | Python 环境 + 依赖 | `import smolvla` 成功 |
| F3.2 | FastAPI VLA 推理服务 | `vla_server.py` | `curl /health` 返回 200 |
| F3.3 | 模型权重下载 + 推理测试 | 权重文件 + 测试输出 | 给定图片，返回合理关节角度 |
| F3.4 | OpenClaw VLA 集成 | VLA 函数插件 + config | LLM 调用 VLA 工具成功 |
| F3.5 | 端到端 VLA 调用链路 | 测试记录 | 拍照 → VLA → 下发关节指令 |

---

## 3. F3.1 功能规格：smolVLA 环境搭建

### 需求描述

在 GPU 服务器上 clone smolVLA 仓库并安装依赖。

### 参考仓库

https://github.com/ZhangYizhe/smolVLA

### 硬件要求

| 方案 | 模型 | 显存需求 | 来源 |
|------|------|----------|------|
| **推荐** | smolVLA-0.5B | ≥ 4GB | Hugging Face |
| 备选 | Octo-Base | ≥ 2GB（CPU 可跑） | Hugging Face |

### 安装步骤

```bash
git clone https://github.com/ZhangYizhe/smolVLA.git
cd smolVLA
pip install -e .
pip install fastapi uvicorn pillow numpy
```

### 验收标准

```python
from smolvla import SmolVLA  # 或等效的模型加载接口
print("smolVLA 加载成功")
```

---

## 4. F3.2 功能规格：FastAPI VLA 推理服务

### 需求描述

编写 FastAPI 推理服务，接收图片和指令，返回关节动作序列。

### API 设计

```
POST /health
→ {"status": "ok", "model": "smolVLA-0.5B", "device": "cuda:0"}

POST /vla/infer
请求体:
{
    "image": "<base64 编码的 JPEG 图片>",
    "instruction": "抓取红色方块",
    "current_joints": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  // 可选
}

响应体:
{
    "success": true,
    "action_joints": [
        [90.0, 45.0, 0.0, 30.0, 0.0, 60.0],   // 第1步关节角度
        [90.0, 30.0, -10.0, 50.0, 0.0, 30.0],  // 第2步关节角度
        [90.0, 20.0, -20.0, 70.0, 0.0, 10.0]   // 第3步关节角度
    ],
    "gripper": [0.8, 0.8, 0.0],   // 夹爪动作序列 (1.0=全力合, 0.0=全开)
    "confidence": 0.85,
    "inference_time_ms": 150
}

错误响应:
{
    "success": false,
    "error": "模型未加载" | "图片解码失败" | "推理超时"
}
```

### 代码结构（产出文件：`vla_server.py`）

```python
"""
VLA 推理服务 — FastAPI 封装 smolVLA 模型

POST /vla/infer 接收照片和指令，返回机械臂动作序列。
"""
import base64
import io
import time
from contextlib import asynccontextmanager

import numpy as np
from PIL import Image
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# ---- 模型全局单例 ----
model = None
device = "cuda:0"  # 或 "cpu"


class InferRequest(BaseModel):
    image: str = Field(..., description="Base64 编码的 JPEG 图片")
    instruction: str = Field(..., description="自然语言指令")
    current_joints: list[float] | None = Field(
        default=None, description="当前 6 关节角度（可选）"
    )


class InferResponse(BaseModel):
    success: bool
    action_joints: list[list[float]] | None = None
    gripper: list[float] | None = None
    confidence: float = 0.0
    inference_time_ms: float = 0.0
    error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时加载模型，关闭时释放资源。"""
    global model
    # model = load_vla_model("smolVLA-0.5B", device=device)  # 待实现
    print(f"VLA 模型已加载，设备: {device}")
    yield
    # model = None


app = FastAPI(title="VLA Inference Server", lifespan=lifespan)


@app.get("/health")
async def health():
    return {"status": "ok", "model": "smolVLA-0.5B", "device": device}


@app.post("/vla/infer", response_model=InferResponse)
async def infer(req: InferRequest):
    """接收图片+指令，返回机械臂动作序列。"""
    # 1. 解码图片
    try:
        image_bytes = base64.b64decode(req.image)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"图片解码失败: {e}")

    # 2. 模型推理
    t0 = time.time()
    try:
        # action_joints, gripper, confidence = model.predict(
        #     image=image,
        #     instruction=req.instruction,
        #     current_joints=req.current_joints,
        # )
        ...
    except Exception as e:
        return InferResponse(success=False, error=str(e))

    elapsed = (time.time() - t0) * 1000

    return InferResponse(
        success=True,
        action_joints=action_joints,
        gripper=gripper,
        confidence=confidence,
        inference_time_ms=elapsed,
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
```

### 验收标准

1. `python vla_server.py` 启动成功
2. `curl http://localhost:8080/health` 返回 `{"status":"ok"}`
3. 用一张测试图片调用 `/vla/infer`，返回合理的 JSON 响应

---

## 5. F3.3 功能规格：模型权重下载 + 推理测试

### 需求描述

从 Hugging Face 下载 smolVLA-0.5B 预训练权重，运行推理测试。

### 参考命令

```bash
# 方式一：huggingface-cli
huggingface-cli download <model-repo> --local-dir ./weights/

# 方式二：Python
from huggingface_hub import snapshot_download
snapshot_download("<model-repo>", local_dir="./weights/")
```

### 验收标准

1. 权重文件下载完成（约 1-2GB）
2. 使用测试图片推理，输出关节角度序列
3. 推理时延 < 500ms（GPU）/ < 2s（CPU）
4. 推理结果关节角度在合理范围内（0-180°）

---

## 6. F3.4 功能规格：OpenClaw VLA 集成

### 需求描述

在 OpenClaw 服务器中新增「拍照→VLA 推理→下发指令」的工具链。

### 涉及文件

| 文件 | 改动 |
|------|------|
| `core/providers/tools/server_plugins/functions/vla_grasp.py` | 🆕 VLA 抓取函数插件 |
| `config.yaml` → `VLA` 段 | 🆕 VLA 服务 URL 配置 |
| `config.yaml` → `plugins` → `functions` | 注册 vla_grasp |

### VLA 抓取函数设计

```python
"""
VLA 抓取函数插件

在 OpenClaw 服务器的 function_call 模式中注册为可用函数。
LLM 调用此函数后，自动：拍照 → HTTP 调 VLA 服务 → 下发关节指令。
"""
import base64
import httpx

async def vla_grasp(conn, instruction: str):
    """根据自然语言指令，执行 VLA 视觉抓取。

    Args:
        conn: ConnectionHandler 实例
        instruction: 抓取指令（如"抓取红色方块"）

    Returns:
        dict: {"success": bool, "joints": [...], "confidence": float}
    """
    vla_url = conn.config.get("VLA", {}).get("server_url", "http://localhost:8080")

    # 1. 调用 ESP32 摄像头拍照
    photo_resp = await conn.call_device_mcp("camera.take_photo", {})
    if not photo_resp.get("success"):
        return {"success": False, "error": "拍照失败"}

    image_b64 = photo_resp["image"]

    # 2. 调用 VLA 推理服务
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            f"{vla_url}/vla/infer",
            json={"image": image_b64, "instruction": instruction},
        )
        result = resp.json()

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "VLA 推理失败")}

    # 3. 逐帧下发关节指令
    for i, joints in enumerate(result["action_joints"]):
        await conn.call_device_mcp("robot.arm.move_joints", {
            "angles": str(joints),
            "speed": 40,
        })
        # 每帧等待执行（机械臂完成动作约需 200-500ms）
        await asyncio.sleep(0.3)

    # 4. 控制夹爪
    if result.get("gripper"):
        for grip in result["gripper"]:
            await conn.call_device_mcp("robot.arm.gripper", {
                "open": grip < 0.5,
                "speed": 30,
            })
            await asyncio.sleep(0.3)

    return {
        "success": True,
        "joints": result["action_joints"],
        "confidence": result["confidence"],
    }
```

### config.yaml 追加

```yaml
# VLA 视觉推理配置
VLA:
  server_url: "http://localhost:8080"  # VLA 推理服务地址
  timeout: 30  # 推理超时（秒）
  enabled: false  # Phase 3 阶段开启

# 在 plugins 段注册
plugins:
  functions:
    - vla_grasp  # 🆕
```

### 验收标准

1. LLM 在 function_call 模式下能调用 `vla_grasp` 函数
2. 端到端流程：用户说"抓取红色方块" → ESP32 拍照 → 图片传到 VLA 服务 → 关节指令下发
3. 机械臂执行动作序列

---

## 7. F3.5 功能规格：端到端 VLA 链路测试

### 测试用例

| # | 测试场景 | 输入 | 期望 |
|---|----------|------|------|
| 1 | 单物体抓取 | 桌上放一个红色方块，"抓取红色方块" | 正确识别并生成抓取动作 |
| 2 | 多物体选择 | 桌上放红蓝两个方块，"抓取蓝色的" | 正确识别颜色并抓取蓝色 |
| 3 | 空场景 | 桌面无物体，"抓取积木" | 返回"未检测到目标物体" |
| 4 | 推理超时 | VLA 服务不可用 | 返回友好错误提示 |

### 验收标准

1. 静态场景下，VLA 根据照片生成合理的关节角度序列
2. 抓取成功率达到基准水平（smolVLA-0.5B 基线约 81.4%）

---

## 8. 依赖关系

```
F3.1 (环境搭建)
  └→ F3.2 (FastAPI 服务)
      └→ F3.3 (权重下载 + 测试)
          └→ F3.4 (OpenClaw 集成)
              └→ F3.5 (链路测试) ← 依赖 Phase 2 + ESP32 摄像头
```

## 9. 备选方案（无 GPU 时）

如果暂时没有 GPU，可以用 [Octo-Base](https://huggingface.co/rail-berkeley/octo-base) 在 CPU 上做流程验证：
- 显存需求仅 2GB，CPU 可跑（慢但能验证流程）
- 成功率约 71.5%（vs smolVLA-0.5B 的 81.4%）
- API 协议与 VLA 服务相同，只需替换模型加载代码
