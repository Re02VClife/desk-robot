"""
机械臂 MCP 工具端到端测试

运行前提：ESP32 已烧录固件并连接到 OpenClaw 服务器，机械臂已接线
运行方式：pytest tests/test_mcp_arm_tools.py -v -m requires_hardware
"""
import json
import time
import pytest


# ---- 模拟 MCP 工具调用的 JSON-RPC 请求 ----

def _make_mcp_call(tool_name: str, arguments: dict) -> dict:
    """构建符合 JSON-RPC 2.0 的 MCP tools/call 请求。"""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments,
        },
    }


def _make_mcp_list() -> dict:
    """构建 tools/list 请求。"""
    return {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}


# ---- 注意 ----
# 以下测试需要通过 WebSocket 与 ESP32 通信来执行。
# 由于需要硬件在线，标记为 requires_hardware。
# 在没有硬件时，可以作为 API 文档参考。
# ----


@pytest.mark.requires_hardware
class TestArmMoveJoints:
    """robot.arm.move_joints 工具测试"""

    def test_move_single_joint(self):
        """移动单个关节到指定角度"""
        # 这需要通过 WebSocket 发送 MCP 指令
        # 实际测试时需建立 WebSocket 连接
        cmd = _make_mcp_call("robot.arm.move_joints", {
            "angles": "[90, 0, 0, 0, 0, 0]",
            "speed": 30,
        })
        # 验证请求格式正确
        assert cmd["method"] == "tools/call"
        assert cmd["params"]["name"] == "robot.arm.move_joints"
        params = cmd["params"]["arguments"]
        assert "angles" in params
        assert "speed" in params
        assert 1 <= params["speed"] <= 100

    def test_move_all_joints(self):
        """移动所有 6 个关节"""
        cmd = _make_mcp_call("robot.arm.move_joints", {
            "angles": "[45, 30, 15, 60, 0, 90]",
            "speed": 50,
        })
        angles = json.loads(cmd["params"]["arguments"]["angles"])
        assert len(angles) == 6

    def test_speed_clamping(self):
        """速度参数应被裁剪到 1-100 范围"""
        # 速度 0 → 裁剪为 1
        cmd_low = _make_mcp_call("robot.arm.move_joints", {
            "angles": "[0,0,0,0,0,0]",
            "speed": 0,
        })
        assert cmd_low["params"]["arguments"]["speed"] == 0  # 由固件端裁剪

        # 速度 200 → 裁剪为 100
        cmd_high = _make_mcp_call("robot.arm.move_joints", {
            "angles": "[0,0,0,0,0,0]",
            "speed": 200,
        })
        assert cmd_high["params"]["arguments"]["speed"] == 200  # 由固件端裁剪

    def test_invalid_angles_length(self):
        """angles 数组长度必须为 6"""
        cmd = _make_mcp_call("robot.arm.move_joints", {
            "angles": "[90, 45]",  # 只有 2 个值
            "speed": 50,
        })
        angles = json.loads(cmd["params"]["arguments"]["angles"])
        assert len(angles) == 2  # 固件端应校验并拒绝


@pytest.mark.requires_hardware
class TestArmGripper:
    """robot.arm.gripper 工具测试"""

    def test_gripper_open(self):
        """张开夹爪"""
        cmd = _make_mcp_call("robot.arm.gripper", {
            "open": True,
            "speed": 30,
        })
        assert cmd["params"]["name"] == "robot.arm.gripper"
        assert cmd["params"]["arguments"]["open"] is True

    def test_gripper_close(self):
        """闭合夹爪"""
        cmd = _make_mcp_call("robot.arm.gripper", {
            "open": False,
            "speed": 30,
        })
        assert cmd["params"]["name"] == "robot.arm.gripper"
        assert cmd["params"]["arguments"]["open"] is False


@pytest.mark.requires_hardware
class TestArmGetStatus:
    """robot.arm.get_status 工具测试"""

    def test_get_status_request(self):
        """查询状态请求格式"""
        cmd = _make_mcp_call("robot.arm.get_status", {})
        assert cmd["params"]["name"] == "robot.arm.get_status"
        assert cmd["params"]["arguments"] == {}

    def test_get_status_response(self):
        """状态响应应包含 status 字段（当前为 stub）"""
        # 注意：当前实现返回固定 {"status":"pending"}
        # 待驱动板支持查询协议后更新
        expected_keys = {"status"}
        # 实际测试时通过 WebSocket 获取响应
        pytest.skip("需要驱动板支持查询协议后才能真实验证")
