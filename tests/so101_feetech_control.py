"""
SO101 机械臂直连控制 (Feetech SDK)
===================================
使用 Feetech 串口协议 @ 1,000,000 bps 直接控制 SO101 舵机。
跳过 ESP32 / 服务器 / LLM 全部链路。

依赖: pip install feetech-servo-sdk
接线: SO101 CH343 USB → PC, SO101 必须接 12V 电源
"""
from scservo_sdk import *
import sys
import time

# ====== 配置 ======
PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000  # Feetech 默认波特率
SPEED = 1000    # 舵机速度 (0-4095, 越大越快)
ACC = 50        # 加速度

# 舵机 ID 映射 (SO101: 6个STS系列舵机, ID 1-6)
JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# 安全位置范围 (STS3215: 0-4095 对应 0-360°, 中位=2048)
# 限制关节范围避免碰撞
SAFE_MIN = [512, 512, 256, 256, 512, 0]   # 关节最小位置 (~45°, ~45°, ~22°, ~22°, ~45°, 0°)
SAFE_MAX = [3584, 3072, 3072, 3072, 3072, 3072]  # 关节最大位置 (~315°, ~270°, ~270°, ~270°, ~270°, ~270°)

# Middle position (2048 = 180° for STS3215)
HOME = [2048, 2048, 2048, 2048, 2048, 2048]

# ====== 连接 ======
print(f"🔌 连接 {PORT} @ {BAUD} bps...")
port = PortHandler(PORT)
if not port.openPort():
    print("❌ 无法打开串口! 检查:")
    print("   1. SO101 是否接 12V 电源")
    print("   2. COM 口号是否正确")
    print("   3. 串口是否被其他程序占用")
    sys.exit(1)

if not port.setBaudRate(BAUD):
    print("❌ 无法设置波特率!")
    port.closePort()
    sys.exit(1)

print("✅ 串口就绪\n")

# STS系列使用协议1
packet = PacketHandler(1)

# ====== Ping 所有舵机 ======
print("🔍 扫描舵机...")
found = []
for servo_id in range(1, 7):
    model, result, error = packet.ping(port, servo_id)
    if result == COMM_SUCCESS:
        print(f"   ✅ ID={servo_id} ({JOINT_NAMES[servo_id-1]}) 在线, 型号={model}")
        found.append(servo_id)
    else:
        print(f"   ❌ ID={servo_id} ({JOINT_NAMES[servo_id-1]}) 未响应 (code={result})")

if not found:
    print("\n❌ 所有舵机无响应! 检查 SO101 是否上电。")
    port.closePort()
    sys.exit(1)

print(f"\n找到 {len(found)} 个舵机\n")

# Feetech STS系列控制表地址
ADDR_TORQUE_ENABLE = 40   # 0x28, 1 byte
ADDR_GOAL_POSITION = 42  # 0x2A, 2 bytes
ADDR_GOAL_SPEED = 46     # 0x2E, 2 bytes

# ====== 运动函数 ======
def move_all(positions, speed=SPEED, desc=""):
    """移动所有舵机到指定位置"""
    if desc:
        print(f"🎯 {desc}")
    for i, servo_id in enumerate(range(1, 7)):
        pos = int(positions[i])
        pos = max(SAFE_MIN[i], min(SAFE_MAX[i], pos))
        # 先写速度
        packet.write2ByteTxRx(port, servo_id, ADDR_GOAL_SPEED, speed)
        # 再写目标位置
        packet.write2ByteTxRx(port, servo_id, ADDR_GOAL_POSITION, pos)
    time.sleep(0.5)

print("=" * 50)
print("🏠 归位")
print("=" * 50)
move_all(HOME, 1500, "全部回到中位 (2048)")
time.sleep(1)

# ====== 逐个关节测试 ======
for joint in range(6):
    print(f"\n{'='*50}")
    print(f"测试 关节{joint+1}: {JOINT_NAMES[joint]}")
    print(f"{'='*50}")

    # 偏离中位 ±512 (约 ±45°)
    test_angles = list(HOME)
    delta = 512

    # 正向
    test_angles[joint] = HOME[joint] + delta
    move_all(test_angles, 1000, f"  正转 +45° → {test_angles[joint]}")
    time.sleep(1.5)

    # 回中
    test_angles[joint] = HOME[joint]
    move_all(test_angles, 1000, f"  回中 → {HOME[joint]}")
    time.sleep(1.5)

    # 反向
    test_angles[joint] = HOME[joint] - delta
    move_all(test_angles, 1000, f"  反转 -45° → {test_angles[joint]}")
    time.sleep(1.5)

    # 回中
    test_angles[joint] = HOME[joint]
    move_all(test_angles, 1000, f"  回中 → {HOME[joint]}")
    time.sleep(1.5)

# ====== 归位 ======
print(f"\n{'='*50}")
print("🏠 测试完成，归位")
print(f"{'='*50}")
move_all(HOME, 2000)
time.sleep(0.5)

# 释放扭矩
for servo_id in range(1, 7):
    packet.write1ByteTxOnly(port, servo_id, ADDR_TORQUE_ENABLE, 0)

print("✅ 全部完成!")
port.closePort()
