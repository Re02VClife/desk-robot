"""
F3.4 VLA 抓取插件测试

测试 vla_grasp 函数插件的核心逻辑：
- 拍照结果解析（base64 图片提取）
- VLA 服务不可达降级
- 动作序列执行流程
"""
import json
import base64
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---- 导入被测试模块 ----
import sys
sys.path.insert(0, r"C:\Users\24628\xiaozhi-esp32-server\main\xiaozhi-server")

# 模拟 plugins_func.functions.vla_grasp 的独立函数
# 直接导入 _extract_image_base64 测试图片提取逻辑


class TestExtractImageBase64:
    """从拍照结果中提取 base64 图片"""

    def _get_extractor(self):
        """延迟导入以避开服务器依赖"""
        from plugins_func.functions.vla_grasp import _extract_image_base64
        return _extract_image_base64

    def test_pure_base64_string(self):
        """纯 base64 字符串直接返回"""
        extract = self._get_extractor()
        b64 = "a" * 200  # 模拟长 base64 字符串
        result = extract(b64)
        assert result == b64

    def test_json_with_image_field(self):
        """JSON 格式 {"image": "..."} 正确提取"""
        extract = self._get_extractor()
        b64 = base64.b64encode(b"fake_image_data_12345").decode()
        photo = json.dumps({"image": b64, "success": True})
        result = extract(photo)
        assert result == b64

    def test_dict_with_image_field(self):
        """dict 格式 {"image": "..."} 正确提取"""
        extract = self._get_extractor()
        b64 = base64.b64encode(b"fake_image_data_12345").decode()
        result = extract({"image": b64})
        assert result == b64

    def test_dict_with_data_field(self):
        """dict 格式 {"data": "..."} 正确提取"""
        extract = self._get_extractor()
        b64 = base64.b64encode(b"fake_image_data_12345").decode()
        result = extract({"data": b64})
        assert result == b64

    def test_dict_with_base64_field(self):
        """dict 格式 {"base64": "..."} 正确提取"""
        extract = self._get_extractor()
        b64 = base64.b64encode(b"fake_image_data_12345").decode()
        result = extract({"base64": b64})
        assert result == b64

    def test_short_string_returns_none(self):
        """过短的字符串（不可能是图片）返回 None"""
        extract = self._get_extractor()
        result = extract("too short")
        assert result is None

    def test_empty_dict_returns_none(self):
        """空 dict 返回 None"""
        extract = self._get_extractor()
        result = extract({})
        assert result is None

    def test_bytes_input(self):
        """bytes 输入自动 base64 编码"""
        extract = self._get_extractor()
        data = b"binary_image_data_here"
        result = extract(data)
        assert result == base64.b64encode(data).decode("utf-8")


class TestVLAGraspErrorHandling:
    """VLA 抓取错误处理测试"""

    @pytest.mark.asyncio
    async def test_mcp_client_not_initialized(self):
        """MCP 客户端未初始化时返回友好提示"""
        # 动态导入以避免服务器依赖
        from plugins_func.functions.vla_grasp import vla_grasp

        # Mock conn 没有 mcp_client
        conn = MagicMock()
        conn.config = {}
        del conn.mcp_client  # 确保 hasattr 返回 False

        # 注意：直接调用需要 conn 有 mcp_client 属性
        # 使用 hasattr 检查时如果属性不存在且没有抛出异常则进入降级分支
        with patch.object(type(conn), 'mcp_client', create=True, new=None):
            result = await vla_grasp(conn, "抓取红色方块")

        assert result.action.name == "REQLLM"
        assert "不在线" in result.result

    @pytest.mark.asyncio
    async def test_vla_disabled_in_config(self):
        """VLA 功能未启用时返回提示"""
        from plugins_func.functions.vla_grasp import vla_grasp

        conn = MagicMock()
        conn.config = {"VLA": {"enabled": False}}

        result = await vla_grasp(conn, "抓取红色方块")
        assert result.action.name == "REQLLM"
        assert "未启用" in result.result


class TestVLAGraspIntegration:
    """VLA 抓取集成测试（需要 VLA stub 服务运行）"""

    @pytest.mark.requires_server
    @pytest.mark.asyncio
    async def test_vla_stub_server_health(self):
        """验证 VLA stub 服务健康检查"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get("http://localhost:8080/health")
                assert resp.status_code == 200
                data = resp.json()
                assert data["status"] == "ok"
        except httpx.ConnectError:
            pytest.skip("VLA stub 服务未启动 (localhost:8080)")

    @pytest.mark.requires_server
    @pytest.mark.asyncio
    async def test_vla_stub_server_infer(self):
        """验证 VLA stub 服务推理接口返回合理数据"""
        import httpx
        # 生成一个假的小图片 base64
        b64 = base64.b64encode(b"\x89PNG\r\n\x1a\n" + b"\x00" * 200).decode()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "http://localhost:8080/vla/infer",
                    json={
                        "image": b64,
                        "instruction": "抓取红色方块",
                        "current_joints": [0, 0, 0, 0, 0, 0],
                    },
                )
                assert resp.status_code == 200
                data = resp.json()
                assert data["success"] is True
                assert len(data["action_joints"]) > 0
                assert 0 <= data["confidence"] <= 1
                # 每个动作步骤包含 6 个关节
                for step in data["action_joints"]:
                    assert len(step) == 6
                    for angle in step:
                        assert 0 <= angle <= 180
        except httpx.ConnectError:
            pytest.skip("VLA stub 服务未启动 (localhost:8080)")

    @pytest.mark.requires_server
    @pytest.mark.asyncio
    async def test_vla_stub_invalid_image(self):
        """VLA stub 服务对无效图片返回错误"""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    "http://localhost:8080/vla/infer",
                    json={
                        "image": "invalid_base64!!!",
                        "instruction": "抓取",
                    },
                )
                assert resp.status_code == 400
        except httpx.ConnectError:
            pytest.skip("VLA stub 服务未启动 (localhost:8080)")
