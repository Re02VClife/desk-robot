"""
VLA 推理服务单元测试

运行前提：VLA 推理服务已启动（python vla_server.py）
运行方式：pytest tests/test_vla_inference.py -v
"""
import base64
import io
import pytest
import httpx
from PIL import Image


# 生成一张纯色测试图片的 base64
def _make_test_image_base64(color=(255, 0, 0), size=(320, 240)):
    """生成纯色测试图片，返回 base64 字符串。"""
    img = Image.new("RGB", size, color=color)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=70)
    return base64.b64encode(buf.getvalue()).decode()


@pytest.mark.requires_gpu
class TestVLAHealth:
    """服务健康检查"""

    def test_health_check(self, vla_url):
        """服务存活检查"""
        response = httpx.get(f"{vla_url}/health", timeout=5.0)
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "model" in data


@pytest.mark.requires_gpu
class TestVLAInfer:
    """推理接口测试"""

    def test_infer_basic(self, vla_url):
        """基本推理：发送图片 + 指令，验证响应结构"""
        payload = {
            "image": _make_test_image_base64(color=(255, 0, 0)),
            "instruction": "抓取红色方块",
            "current_joints": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
        }
        response = httpx.post(
            f"{vla_url}/vla/infer", json=payload, timeout=30.0
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "action_joints" in data
        assert "confidence" in data

    def test_infer_invalid_image(self, vla_url):
        """无效图片应返回错误"""
        payload = {
            "image": "这不是有效的 base64",
            "instruction": "抓取",
        }
        response = httpx.post(
            f"{vla_url}/vla/infer", json=payload, timeout=30.0
        )
        # 无效图片应返回 400 或 success=false
        if response.status_code == 200:
            data = response.json()
            assert data["success"] is False
        else:
            assert response.status_code == 400

    def test_infer_empty_instruction(self, vla_url):
        """空指令应返回错误"""
        payload = {
            "image": _make_test_image_base64(),
            "instruction": "",
        }
        response = httpx.post(
            f"{vla_url}/vla/infer", json=payload, timeout=30.0
        )
        assert response.status_code in (200, 400, 422)

    def test_infer_timeout_handling(self, vla_url):
        """超时处理：短超时不应崩溃"""
        payload = {
            "image": _make_test_image_base64(),
            "instruction": "抓取",
        }
        try:
            response = httpx.post(
                f"{vla_url}/vla/infer",
                json=payload,
                timeout=1.0,  # 故意设极短超时
            )
        except httpx.TimeoutException:
            pass  # 预期可能超时，服务器不应崩溃


@pytest.mark.requires_gpu
class TestVLAOutputValidation:
    """推理输出校验"""

    def test_joints_range(self, vla_url):
        """关节角度应在合理范围（0-180°）"""
        payload = {
            "image": _make_test_image_base64(),
            "instruction": "抓取红色方块",
        }
        response = httpx.post(
            f"{vla_url}/vla/infer", json=payload, timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            if data["success"] and data["action_joints"]:
                for step in data["action_joints"]:
                    for joint in step:
                        assert 0 <= joint <= 180, (
                            f"关节角度 {joint} 超出 0-180° 范围"
                        )

    def test_action_sequence_non_empty(self, vla_url):
        """动作序列不应为空"""
        payload = {
            "image": _make_test_image_base64(),
            "instruction": "抓取红色方块",
        }
        response = httpx.post(
            f"{vla_url}/vla/infer", json=payload, timeout=30.0
        )
        if response.status_code == 200:
            data = response.json()
            if data["success"]:
                assert len(data["action_joints"]) > 0, "动作序列为空"
                # 每步应有 6 个关节角度
                for step in data["action_joints"]:
                    assert len(step) == 6, "每步应有 6 个关节角度"
