"""
SO101 安全测试脚本（零依赖版）
==============================
纯 pyserial 实现 Feetech SCServo 协议，无需 scservo_sdk。
先读取所有舵机当前位置，然后逐个关节小幅移动（±3.5°），避免碰撞。

用法: python so101_safe_test.py COM11
"""
import serial
import sys
import time
import struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000

# Feetech STS 控制表地址
ADDR_TORQUE_ENABLE   = 40   # 扭矩使能
ADDR_GOAL_POSITION   = 42   # 目标位置 (2字节)
ADDR_GOAL_SPEED      = 46   # 目标速度 (2字节)
ADDR_PRESENT_POSITION = 56  # 当前位置 (2字节)

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# ====== Feetech SCS 协议实现 ======

def scs_checksum(data):
    """计算 SCS 协议校验和: ~(sum of bytes) & 0xFF"""
    return (~sum(data) & 0xFF)

def scs_packet(servo_id, instruction, params=None):
    """构建 SCS 协议包: [0xFF,0xFF, ID, Length, Instruction, ...params, Checksum]"""
    if params is None:
        params = []
    length = len(params) + 2  # instruction + params + checksum
    pkt = [0xFF, 0xFF, servo_id, length, instruction] + params
    pkt.append(scs_checksum(pkt[2:]))  # checksum of ID through params
    return bytes(pkt)

def scs_read(ser, servo_id, addr, length):
    """读舵机控制表"""
    pkt = scs_packet(servo_id, 0x02, [addr, length])
    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()
    time.sleep(0.05)
    # 等待回复: [0xFF,0xFF, ID, Length, Error, ...data, Checksum]
    reply = ser.read(6 + length)
    if len(reply) < 6 + length:
        return None
    if reply[0] != 0xFF or reply[1] != 0xFF:
        return None
    error = reply[4]
    if error != 0:
        return None
    data = reply[5:5 + length]
    if length == 2:
        return struct.unpack('<H', data)[0]
    return data[0]

def scs_write(ser, servo_id, addr, data):
    """写舵机控制表，data 为 bytes"""
    params = [addr] + list(data)
    pkt = scs_packet(servo_id, 0x03, params)
    ser.write(pkt)
    ser.flush()
    time.sleep(0.03)

def scs_ping(ser, servo_id):
    """Ping 舵机，返回型号。STS3215 返回 6"""
    pkt = scs_packet(servo_id, 0x01)
    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()
    time.sleep(0.05)
    reply = ser.read(6)
    if len(reply) < 6:
        return None
    if reply[0] != 0xFF or reply[1] != 0xFF:
        return None
    error = reply[4]
    if error != 0:
        return None
    return reply[5]  # model number

# ====== 连接 ======
print(f"🔌 {PORT} @ {BAUD}bps...")
ser = serial.Serial(PORT, BAUD, timeout=0.2)
print("✅ 连接成功\n")

# ====== 扫描 + 读取当前位置 ======
print("🔍 扫描舵机并读取当前位置...")
print(f"{'ID':<4} {'关节':<8} {'型号':<8} {'当前位置':<10} {'角度估算':<10}")
print("-" * 52)

positions = {}
for servo_id in range(1, 7):
    model = scs_ping(ser, servo_id)
    if model is not None:
        time.sleep(0.1)
        # 先开扭矩才能读位置
        scs_write(ser, servo_id, ADDR_TORQUE_ENABLE, b'\x01')
        time.sleep(0.05)
        pos = scs_read(ser, servo_id, ADDR_PRESENT_POSITION, 2)
        if pos is not None:
            positions[servo_id] = pos
        else:
            positions[servo_id] = 2048
            pos = 2048
        angle_est = (pos / 4096) * 360  # 单圈模式: 0-4095
        print(f"{servo_id:<4} {JOINT_NAMES[servo_id-1]:<8} {model:<8} {pos:<10} {angle_est:<10.1f}°")
    else:
        print(f"{servo_id:<4} {JOINT_NAMES[servo_id-1]:<8} OFF-LINE")

if not positions:
    print("\n❌ 无舵机在线! 检查电源。")
    ser.close()
    sys.exit(1)

print(f"\n找到 {len(positions)} 个舵机")
print("注意: 1圈=4096步, 显示角度基于单圈模式估算")

# ====== 逐个关节小幅测试 ======
print("\n⚠️  逐个关节小幅测试 (±40 步 ≈ 3.5°)")
print("   随时按 Ctrl+C 紧急停止!\n")

DELTA = 40   # 很小幅度 (~3.5° = 40/4096*360)
SPEED = 150  # 低速

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
        scs_write(ser, servo_id, ADDR_GOAL_SPEED, struct.pack('<H', SPEED))
        scs_write(ser, servo_id, ADDR_GOAL_POSITION, struct.pack('<H', target))
        time.sleep(1.5)
        actual = scs_read(ser, servo_id, ADDR_PRESENT_POSITION, 2)
        print(f"实际={actual}")

        # 回原
        print(f"  → 回原 {original}...", end=" ", flush=True)
        scs_write(ser, servo_id, ADDR_GOAL_POSITION, struct.pack('<H', original))
        time.sleep(1.5)

        # 反向
        target = original - DELTA
        print(f"  → 反转 {target} (-{DELTA})...", end=" ", flush=True)
        scs_write(ser, servo_id, ADDR_GOAL_POSITION, struct.pack('<H', target))
        time.sleep(1.5)
        actual = scs_read(ser, servo_id, ADDR_PRESENT_POSITION, 2)
        print(f"实际={actual}")

        # 回原
        print(f"  → 回原 {original}...", end=" ", flush=True)
        scs_write(ser, servo_id, ADDR_GOAL_POSITION, struct.pack('<H', original))
        time.sleep(1.5)

        print(f"  ✅ 关节{servo_id} 测试完成\n")

except KeyboardInterrupt:
    print("\n\n🛑 紧急停止！")

# ====== 释放扭矩 ======
print("释放扭矩...")
for servo_id in range(1, 7):
    try:
        scs_write(ser, servo_id, ADDR_TORQUE_ENABLE, b'\x00')
    except:
        pass

print("✅ 安全退出")
ser.close()
