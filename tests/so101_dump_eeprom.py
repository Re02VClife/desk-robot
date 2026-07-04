"""
SO101 舵机 EEPROM 诊断脚本
==========================
Dump 每个舵机的前 60 字节控制表，用于排查限位地址差异。

用法: python so101_dump_eeprom.py COM11 [舵机ID]
      不加 ID 则扫描全部 1-6
"""
import serial
import sys
import time
import struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
TARGET_ID = int(sys.argv[2]) if len(sys.argv) > 2 else None
BAUD = 1000000

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

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
    time.sleep(0.03)
    reply = ser.read(6 + length)
    if len(reply) < 6 + length:
        return None
    return list(reply[5:5 + length])

def scs_ping(ser, servo_id):
    pkt = scs_packet(servo_id, 0x01)
    ser.reset_input_buffer()
    ser.write(pkt)
    ser.flush()
    time.sleep(0.05)
    reply = ser.read(6)
    if len(reply) < 6 or reply[4] != 0:
        return None
    return reply[5]

def u16_be(data):
    """大端序 uint16"""
    return data[0] * 256 + data[1]

def u16_le(data):
    """小端序 uint16"""
    return data[0] + data[1] * 256

print(f"🔌 {PORT} @ {BAUD}bps...")
ser = serial.Serial(PORT, BAUD, timeout=0.2)

ids = [TARGET_ID] if TARGET_ID else range(1, 7)

for servo_id in ids:
    model = scs_ping(ser, servo_id)
    if model is None:
        print(f"\nID{servo_id} ❌ 离线")
        continue

    name = JOINT_NAMES[servo_id - 1]
    print(f"\n{'='*70}")
    print(f"ID{servo_id} {name} 型号={model}")
    print(f"{'='*70}")
    print(f"{'Addr':<6} {'HEX':<30} {'u16_BE':<10} {'u16_LE':<10} {'说明'}")
    print("-" * 70)

    for addr in range(0, 60, 2):
        data = scs_read(ser, servo_id, addr, 2)
        if data is None:
            continue
        hex_str = ' '.join(f'{b:02X}' for b in data)
        be = u16_be(data)
        le = u16_le(data)

        # 标注已知地址
        note = ""
        if addr == 6:
            note = f"← CW限位(BE={be}°={be/4096*360:.0f}° LE={le}°={le/4096*360:.0f}°)"
        elif addr == 8:
            note = f"← CCW限位(BE={be}°={be/4096*360:.0f}° LE={le}°={le/4096*360:.0f}°)"
        elif addr == 14:
            note = "← 最大扭矩"
        elif addr == 16:
            note = "← 最大电压"
        elif addr == 18:
            note = "← 最小电压"
        elif addr == 20:
            note = "← P比例"
        elif addr == 40:
            note = "← 扭矩使能"
        elif addr == 42:
            note = f"← 目标位置"
        elif addr == 56:
            note = f"← 当前位置(BE={be}={be/4096*360:.0f}° LE={le}={le/4096*360:.0f}°)"

        print(f"0x{addr:02X}   {hex_str:<30} {be:<10} {le:<10} {note}")
        time.sleep(0.01)

ser.close()
print(f"\n{'='*70}")
print("✅ Dump 完成")
print("对比 FD 软件中显示的限位值，确认是 BE(大端) 还是 LE(小端) 字节序")
