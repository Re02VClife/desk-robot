"""
SO101 安全测试脚本
==================
先读取所有舵机当前位置，然后逐个关节小幅移动（±20°），避免碰撞。
"""
from scservo_sdk import *
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000

# Feetech STS 控制表地址
ADDR_TORQUE_ENABLE = 40
ADDR_GOAL_POSITION = 42
ADDR_GOAL_SPEED = 46
ADDR_PRESENT_POSITION = 56  # 0x38

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# ====== 连接 ======
print(f"🔌 {PORT} @ {BAUD}bps...")
port = PortHandler(PORT)
port.openPort()
port.setBaudRate(BAUD)
packet = PacketHandler(1)
print("✅ 连接成功\n")

# ====== 读取当前位置 ======
def read_position(servo_id):
    """读取舵机当前位置"""
    try:
        pos, result, error = packet.read2ByteTxRx(port, servo_id, ADDR_PRESENT_POSITION)
        if result == COMM_SUCCESS:
            return pos
    except:
        pass
    return None

def write_position(servo_id, pos, speed=500):
    """写入目标位置"""
    pos = max(0, min(65535, int(pos)))
    # 确保扭矩开启
    packet.write1ByteTxOnly(port, servo_id, ADDR_TORQUE_ENABLE, 1)
    time.sleep(0.05)
    packet.write2ByteTxRx(port, servo_id, ADDR_GOAL_SPEED, speed)
    result, error = packet.write2ByteTxRx(port, servo_id, ADDR_GOAL_POSITION, pos)
    return result == COMM_SUCCESS

def enable_torque(servo_id):
    packet.write1ByteTxOnly(port, servo_id, ADDR_TORQUE_ENABLE, 1)

def disable_torque(servo_id):
    packet.write1ByteTxOnly(port, servo_id, ADDR_TORQUE_ENABLE, 0)

# ====== 扫描 + 读取当前位置 ======
print("🔍 扫描舵机并读取当前位置...")
print(f"{'ID':<4} {'关节':<8} {'型号':<8} {'当前位置':<10} {'角度估算':<10}")
print("-" * 52)

positions = {}
for servo_id in range(1, 7):
    # 先ping
    model, result, error = packet.ping(port, servo_id)
    if result == COMM_SUCCESS:
        time.sleep(0.1)
        # 读位置（无需先开扭矩，ping后直接读）
        pos = read_position(servo_id)
        if pos is not None:
            positions[servo_id] = pos
        else:
            positions[servo_id] = 2048
            pos = 2048
        angle_est = (positions[servo_id] / 65535) * 360
        print(f"{servo_id:<4} {JOINT_NAMES[servo_id-1]:<8} {model:<8} {positions[servo_id]:<10} {angle_est:<10.1f}°")
    else:
        print(f"{servo_id:<4} {JOINT_NAMES[servo_id-1]:<8} OFF-LINE")

if not positions:
    print("\n❌ 无舵机在线! 检查电源。")
    port.closePort()
    sys.exit(1)

print(f"\n找到 {len(positions)} 个舵机")
print("注意: STS3215 多圈模式, 1圈=4096步, 当前位置可能很大")

# ====== 逐个关节小幅测试 ======
print("\n⚠️  逐个关节小幅测试 (±300 步 ≈ 1/14圈)")
print("   随时按 Ctrl+C 紧急停止!\n")

DELTA = 300  # 很小幅度

try:
    for servo_id in sorted(positions.keys()):
        original = positions[servo_id]
        name = JOINT_NAMES[servo_id - 1]

        print(f"{'='*50}")
        print(f"关节{servo_id} {name}: 当前={original}")
        print(f"{'='*50}")

        # 正向
        target = original + DELTA
        print(f"  → 正转 {target} (+{DELTA})...", end=" ", flush=True)
        write_position(servo_id, target, 400)
        time.sleep(2)
        actual = read_position(servo_id)
        print(f"实际={actual}")

        # 回原
        print(f"  → 回原 {original}...", end=" ", flush=True)
        write_position(servo_id, original, 400)
        time.sleep(2)

        # 反向
        target = original - DELTA
        print(f"  → 反转 {target} (-{DELTA})...", end=" ", flush=True)
        write_position(servo_id, target, 400)
        time.sleep(2)
        actual = read_position(servo_id)
        print(f"实际={actual}")

        # 回原
        print(f"  → 回原 {original}...", end=" ", flush=True)
        write_position(servo_id, original, 400)
        time.sleep(2)

        print(f"  ✅ 关节{servo_id} 测试完成\n")

except KeyboardInterrupt:
    print("\n\n🛑 紧急停止！")

# ====== 释放扭矩 ======
print("释放扭矩...")
for servo_id in range(1, 7):
    disable_torque(servo_id)

print("✅ 安全退出")
port.closePort()
