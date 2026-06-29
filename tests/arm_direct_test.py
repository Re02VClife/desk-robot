"""
SO101 机械臂直连测试
====================
通过 CH343 USB 直接发指令到 SO101 驱动板，跳过 ESP32/服务器/LLM 全部链路。

用法: python arm_direct_test.py [--port COM11]
"""
import serial
import time
import sys
import io
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PORT = sys.argv[2] if len(sys.argv) > 2 else "COM11"
BAUD = 115200

print(f"🔌 连接 {PORT} @ {BAUD}bps...")
ser = serial.Serial(PORT, BAUD, timeout=1.0)
print("✅ 已连接\n")

def send_cmd(cmd_dict):
    """发送 JSON 指令到 SO101"""
    msg = json.dumps(cmd_dict) + "\n"
    print(f"📤 发送: {msg.strip()}")
    ser.write(msg.encode("utf-8"))
    ser.flush()
    time.sleep(0.3)
    # 读取回复（如果有）
    if ser.in_waiting:
        reply = ser.read(ser.in_waiting).decode("utf-8", errors="replace").strip()
        print(f"📥 回复: {reply}")
    else:
        print("📥 (无回复)")

def test_joint(joint_num, angles, speed=40):
    """测试单个关节"""
    desc = ["底座旋转", "大臂俯仰", "小臂俯仰", "腕部旋转", "腕部俯仰", "末端旋转"]
    print(f"\n{'='*50}")
    print(f"测试关节{joint_num+1}: {desc[joint_num]}")
    print(f"{'='*50}")

    base = [90, 90, 90, 90, 90, 90]
    angles_list = list(base)
    angles_list[joint_num] = angles
    send_cmd({"cmd": "move_joints", "angles": angles_list, "speed": speed})

# ====== 开始测试 ======
print("🦾 SO101 直连测试开始")
print("观察机械臂是否运动...\n")

# 归位
print("="*50)
print("归位")
print("="*50)
send_cmd({"cmd": "move_joints", "angles": [90, 90, 90, 90, 90, 90], "speed": 40})
time.sleep(1)

# 逐个关节测试
for joint, test_angle in enumerate([60, 60, 60, 60, 60, 60]):
    test_joint(joint, test_angle)
    time.sleep(1.5)
    # 回中
    test_joint(joint, 90)
    time.sleep(1)

# 夹爪测试
print(f"\n{'='*50}")
print("测试夹爪")
print(f"{'='*50}")

# 注意：夹爪命令格式可能不同
send_cmd({"cmd": "gripper", "open": True, "speed": 50})
time.sleep(1)
send_cmd({"cmd": "gripper", "open": False, "speed": 50})
time.sleep(1)

# 最终归位
print(f"\n{'='*50}")
print("归位")
print(f"{'='*50}")
send_cmd({"cmd": "move_joints", "angles": [90, 90, 90, 90, 90, 90], "speed": 40})

print("\n✅ 测试完成！机械臂动了吗？")
ser.close()
