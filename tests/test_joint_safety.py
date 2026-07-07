"""
F4.3 安全限位测试：验证关节角度裁剪算法

纯算法测试，不依赖硬件。测试角度裁剪到 [0, 180] 范围的逻辑。
"""

import json
import pytest


def clamp_joints(angles: list[float]) -> tuple[list[float], list[str]]:
    """模拟 C++ 固件中的关节角度安全裁剪逻辑。

    Args:
        angles: 原始关节角度列表（度）

    Returns:
        (裁剪后角度列表, 警告消息列表)
    """
    warnings = []
    clamped = angles.copy()
    for i, val in enumerate(clamped):
        if val < 0.0:
            warnings.append(f"关节{i+1}角度 {val}° < 0，裁剪为 0°")
            clamped[i] = 0.0
        elif val > 180.0:
            warnings.append(f"关节{i+1}角度 {val}° > 180°，裁剪为 180°")
            clamped[i] = 180.0
    return clamped, warnings


class TestJointSafetyClamp:
    """安全限位 - 边界值测试"""

    def test_normal_angles_unchanged(self):
        """正常范围内的角度不应被修改"""
        angles = [90.0, 45.0, 0.0, 30.0, 60.0, 120.0]
        result, warnings = clamp_joints(angles)
        assert result == angles
        assert len(warnings) == 0

    def test_negative_angle_clamped_to_zero(self):
        """负角度应被裁剪为 0"""
        angles = [90.0, -10.0, 45.0, 30.0, 60.0, 120.0]
        result, warnings = clamp_joints(angles)
        assert result[1] == 0.0
        assert len(warnings) == 1
        assert "关节2" in warnings[0]

    def test_over_180_clamped_to_180(self):
        """超过 180 的角度应被裁剪为 180"""
        angles = [90.0, 200.0, 45.0, 30.0, 60.0, 120.0]
        result, warnings = clamp_joints(angles)
        assert result[1] == 180.0
        assert len(warnings) == 1
        assert "关节2" in warnings[0]

    def test_boundary_zero_unchanged(self):
        """刚好为 0 的角度不应被修改"""
        angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        result, warnings = clamp_joints(angles)
        assert result == angles
        assert len(warnings) == 0

    def test_boundary_180_unchanged(self):
        """刚好为 180 的角度不应被修改"""
        angles = [180.0, 180.0, 180.0, 180.0, 180.0, 180.0]
        result, warnings = clamp_joints(angles)
        assert result == angles
        assert len(warnings) == 0

    def test_multiple_out_of_range(self):
        """多个角度越界时，全部正确裁剪"""
        angles = [-50.0, 200.0, 90.0, -10.0, 250.0, 100.0]
        expected = [0.0, 180.0, 90.0, 0.0, 180.0, 100.0]
        result, warnings = clamp_joints(angles)
        assert result == expected
        assert len(warnings) == 4  # 关节1,2,4,5 共4个越界

    def test_float_precision(self):
        """浮点精度不影响边界判断"""
        angles = [0.0001, 179.9999, 90.0, 45.0, 0.0, 180.0]
        result, warnings = clamp_joints(angles)
        assert result == angles  # 不应被修改
        assert len(warnings) == 0

    def test_extreme_values(self):
        """极端值正确裁剪"""
        angles = [-999.0, 999.0, -0.1, 180.1, 0.0, 180.0]
        expected = [0.0, 180.0, 0.0, 180.0, 0.0, 180.0]
        result, warnings = clamp_joints(angles)
        assert result == expected
        assert len(warnings) == 4


class TestJointSafetySerialization:
    """安全限位 - 序列化往返测试"""

    def test_roundtrip_angles_json(self):
        """角度数组 JSON 序列化往返后裁剪逻辑一致"""
        original = [90.0, 200.0, -10.0, 45.0, 0.0, 180.0]
        # 模拟 C++ 端：JSON 字符串 → 解析 → 裁剪 → 重新序列化
        angles_str = json.dumps(original)
        parsed = json.loads(angles_str)
        clamped, _ = clamp_joints(parsed)
        result_str = json.dumps(clamped)
        # 验证重新序列化后是一个合法 JSON 数组
        result_parsed = json.loads(result_str)
        assert len(result_parsed) == 6
        assert all(isinstance(v, (int, float)) for v in result_parsed)
        assert min(result_parsed) >= 0.0
        assert max(result_parsed) <= 180.0

    def test_invalid_angles_length_too_short(self):
        """角度数量不足6个时，只裁剪已有角度"""
        angles = [90.0, -10.0, 200.0]  # 只有3个
        result, warnings = clamp_joints(angles)
        assert result == [90.0, 0.0, 180.0]
        assert len(warnings) == 2

    def test_empty_angles(self):
        """空角度列表，不做任何操作"""
        angles = []
        result, warnings = clamp_joints(angles)
        assert result == []
        assert len(warnings) == 0
