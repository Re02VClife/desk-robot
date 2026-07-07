"""读取 SO101 6关节当前位置和限位"""
import serial, sys, time, struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

def scs_checksum(data):
    return (~sum(data) & 0xFF)

def scs_packet(sid, inst, params=None):
    if params is None: params = []
    length = len(params) + 2
    pkt = [0xFF, 0xFF, sid, length, inst] + params
    pkt.append(scs_checksum(pkt[2:]))
    return bytes(pkt)

def scs_write(ser, sid, addr, data):
    ser.write(scs_packet(sid, 0x03, [addr] + list(data)))
    ser.flush()

def scs_read(ser, sid, addr, length):
    ser.reset_input_buffer()
    ser.write(scs_packet(sid, 0x02, [addr, length]))
    ser.flush()
    time.sleep(0.03)
    reply = ser.read(6 + length)
    if len(reply) < 6 + length: return None
    if reply[0] != 0xFF or reply[1] != 0xFF or reply[4] != 0: return None
    data = reply[5:5 + length]
    return struct.unpack('<H', data)[0] if length == 2 else data[0]

def scs_ping(ser, sid):
    ser.reset_input_buffer()
    ser.write(scs_packet(sid, 0x01))
    ser.flush()
    time.sleep(0.05)
    reply = ser.read(6)
    if len(reply) < 6 or reply[4] != 0: return None
    return reply[5]

def steps_to_deg(s):
    return s / 4096 * 360

print(f"PORT={PORT} BAUD={BAUD}")
ser = serial.Serial(PORT, BAUD, timeout=0.2)

print(f"\n{'ID':<4} {'关节':<8} {'在线':<6} {'当前位置':<10} {'角度':<10} {'CW限位':<10} {'CCW限位':<10} {'范围':<12}")
print("-" * 78)

for sid in range(1, 7):
    model = scs_ping(ser, sid)
    if model is None:
        print(f"{sid:<4} {JOINT_NAMES[sid-1]:<8} OFFLINE")
        continue

    # 开扭矩才能读位置
    scs_write(ser, sid, 40, b'\x01')
    time.sleep(0.03)

    pos = scs_read(ser, sid, 56, 2)    # 当前位置
    time.sleep(0.02)
    cw  = scs_read(ser, sid, 9, 2)     # CW限位
    time.sleep(0.02)
    ccw = scs_read(ser, sid, 11, 2)    # CCW限位

    name = JOINT_NAMES[sid-1]
    if pos is not None:
        deg = steps_to_deg(pos)
        cw_deg = steps_to_deg(cw) if cw else 0
        ccw_deg = steps_to_deg(ccw) if ccw else 0
        rng = ccw_deg - cw_deg if (cw and ccw) else 0
        print(f"{sid:<4} {name:<8} OK     {pos:<10} {deg:<10.1f} {cw or '?':<10} {ccw or '?':<10} {rng:<12.1f}")

ser.close()
