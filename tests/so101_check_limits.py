"""
SO101 限位检查脚本
==================
读取 6 个关节舵机的 EEPROM 限位值（CW/CCW），转换为角度显示。

用法: python so101_check_limits.py COM11
"""
import serial
import sys
import time
import struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000

# EEPROM 地址（字节地址，匹配 FD 软件）
# 舵机型号 252，地址表与标准 STS3215 不同
ADDR_CW_LIMIT   = 9    # 最小角度限制 (2字节, 小端)
ADDR_CCW_LIMIT  = 11   # 最大角度限制 (2字节, 小端)

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# ====== SCS 协议 ======
def scs_checksum(data):
    return (~sum(data) & 0xFF)

def scs_packet(servo_id, instruction, params=None):
    if params is None:
        params = []
    length = len(params) + 2
    pkt = [0xFF, 0xFF, servo_id, length, instruction] + params
    pkt.append(scs_checksum(pkt[2:]))
    return bytes(pkt)

def scs_read(ser, servo_id, addr, length):
    pkt = scs_packet(servo_id, 0x02, [addr, length])
    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()
    time.sleep(0.05)
    reply = ser.read(6 + length)
    if len(reply) < 6 + length:
        return None
    if reply[0] != 0xFF or reply[1] != 0xFF or reply[4] != 0:
        return None
    data = reply[5:5 + length]
    return struct.unpack('<H', data)[0] if length == 2 else data[0]

def scs_ping(ser, servo_id):
    pkt = scs_packet(servo_id, 0x01)
    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()
    time.sleep(0.05)
    reply = ser.read(6)
    if len(reply) < 6 or reply[0] != 0xFF or reply[1] != 0xFF or reply[4] != 0:
        return None
    return reply[5]

def steps_to_deg(steps):
    return steps / 4096 * 360

# ====== 主逻辑 ======
print(f"🔌 {PORT} @ {BAUD}bps...")
ser = serial.Serial(PORT, BAUD, timeout=0.2)
print("✅ 连接成功\n")

print("🔍 读取 6 个关节限位...\n")
print(f"{'ID':<4} {'关节':<8} {'在线':<6} {'CW限位':<10} {'CCW限位':<10} {'CW角度':<10} {'CCW角度':<10} {'有效范围':<12}")
print("-" * 80)

for servo_id in range(1, 7):
    model = scs_ping(ser, servo_id)
    if model is None:
        print(f"{servo_id:<4} {JOINT_NAMES[servo_id-1]:<8} ❌ 离线")
        continue

    time.sleep(0.05)
    cw = scs_read(ser, servo_id, ADDR_CW_LIMIT, 2)
    time.sleep(0.05)
    ccw = scs_read(ser, servo_id, ADDR_CCW_LIMIT, 2)

    name = JOINT_NAMES[servo_id - 1]
    if cw is not None and ccw is not None:
        cw_deg = steps_to_deg(cw)
        ccw_deg = steps_to_deg(ccw)
        range_deg = ccw_deg - cw_deg
        print(f"{servo_id:<4} {name:<8} ✅     {cw:<10} {ccw:<10} {cw_deg:<10.1f}° {ccw_deg:<10.1f}° {range_deg:<12.1f}°")
    else:
        print(f"{servo_id:<4} {name:<8} ✅     读取失败")

ser.close()
print("\n✅ 检查完成")
