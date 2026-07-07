"""
VLA 推理服务 (smolVLA-0.5B)
===========================
Phase 3: 视觉-语言-动作模型推理服务

当前为 stub 版本，返回模拟关节序列。
部署真实模型时，将 `_stub_infer` 替换为实际的 smolVLA 调用。

API:
    GET  /health       — 健康检查
    POST /vla/infer    — VLA 推理（图片 + 指令 → 关节动作序列）

启动:
    python services/vla_server.py --port 8080
"""

import base64
import json
import random
import argparse
from io import BytesIO

import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


# ---- 数据模型 ----

class InferRequest(BaseModel):
    """VLA 推理请求"""
    image: str = Field(..., description="Base64 编码的 JPEG/PNG 图片")
    instruction: str = Field(..., description="自然语言抓取指令", min_length=1)
    current_joints: list[float] = Field(
        default=[0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        description="当前 6 个关节角度（度）"
    )


class InferResponse(BaseModel):
    """VLA 推理响应"""
    success: bool
    action_joints: list[list[float]] = Field(
        default=[],
        description="未来 N 步的关节角度序列，每步 6 个关节"
    )
    confidence: float = Field(default=0.0, description="推理置信度 (0-1)")
    model: str = Field(default="smolVLA-0.5B (stub)", description="模型版本")


# ---- FastAPI 应用 ----

app = FastAPI(
    title="小智 VLA 推理服务",
    description="smolVLA-0.5B 视觉-语言-动作模型推理",
    version="0.1.0",
)


@app.get("/health")
async def health():
    """服务健康检查"""
    return {
        "status": "ok",
        "model": "smolVLA-0.5B (stub)",
        "note": "当前为 stub 版本，返回模拟推理结果。部署真实模型后替换 _stub_infer()",
    }


@app.post("/vla/infer", response_model=InferResponse)
async def infer(req: InferRequest):
    """
    VLA 推理接口

    输入: 图片(base64) + 自然语言指令 + 当前关节角度
    输出: 未来 N 步的关节角度序列 (Action Chunking)
    """
    # 校验图片 base64
    try:
        img_data = base64.b64decode(req.image)
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="无效的 base64 编码图片"
        )

    if len(img_data) < 100:
        raise HTTPException(
            status_code=400,
            detail="图片数据过小（可能不是有效图片）"
        )

    # 校验指令
    if not req.instruction.strip():
        raise HTTPException(
            status_code=422,
            detail="指令不能为空"
        )

    # 校验当前关节
    joints = req.current_joints
    if joints and len(joints) != 6:
        raise HTTPException(
            status_code=400,
            detail="current_joints 必须包含 6 个浮点数"
        )

    # 执行推理（stub）
    result = _stub_infer(joints, req.instruction)

    return InferResponse(
        success=True,
        action_joints=result["action_joints"],
        confidence=result["confidence"],
    )


# ---- Stub 推理逻辑 ----

def _stub_infer(current_joints: list[float], instruction: str) -> dict:
    """
    Stub 推理 — 返回模拟的关节动作序列
    部署真实模型时替换此函数

    真实调用示例:
        from smolVLA import SmolVLA
        model = SmolVLA.from_pretrained("ZhangYizhe/smolVLA-0.5B")
        action_chunk = model.predict(image, instruction)
    """
    # Action Chunking: 预测未来 5 步动作
    num_steps = 5
    noise = random.Random(hash(instruction) % (2 ** 31))

    action_joints = []
    for step in range(num_steps):
        # 每步在当前位置基础上微调 ±5 度（模拟平滑轨迹）
        step_joints = []
        for j, base in enumerate(current_joints or [0.0] * 6):
            # 逐步增加偏移，模拟向目标移动
            delta = (step + 1) * noise.uniform(-3, 5)
            new_angle = max(0.0, min(180.0, base + delta))
            step_joints.append(round(new_angle, 1))
        action_joints.append(step_joints)

    confidence = round(noise.uniform(0.75, 0.95), 2)

    return {
        "action_joints": action_joints,
        "confidence": confidence,
    }


# ---- 启动入口 ----

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VLA 推理服务")
    parser.add_argument("--host", default="0.0.0.0", help="监听地址")
    parser.add_argument("--port", type=int, default=8080, help="监听端口")
    args = parser.parse_args()

    print(f"[VLA] 启动 smolVLA-0.5B 推理服务 (stub 模式)")
    print(f"[VLA] 地址: http://{args.host}:{args.port}")
    print(f"[VLA] 健康检查: http://{args.host}:{args.port}/health")
    print(f"[VLA] 推理接口: http://{args.host}:{args.port}/vla/infer")
    print(f"[VLA] 注意: 当前为 stub 版本，返回模拟推理结果")

    uvicorn.run(app, host=args.host, port=args.port)
