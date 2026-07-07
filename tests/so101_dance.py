"""
SO101 机械臂跳舞脚本 🕺
=======================
USB 直连舵机总线，零依赖 pyserial。
启动时读取当前位置作为 HOME，所有动作基于 HOME 做相对偏移。
安全：自动读取各关节限位并裁剪，Ctrl+C 紧急停止。

用法: python so101_dance.py COM11 [舞蹈编号]
      不加编号则列出可选舞蹈
"""
import serial
import sys
import time
import struct

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
DANCE_ID = int(sys.argv[2]) if len(sys.argv) > 2 else None
BAUD = 1000000

# 舵机 EEPROM 地址（型号 252，字节地址，小端序）
ADDR_TORQUE  = 40
ADDR_GOAL    = 42
ADDR_SPEED   = 46
ADDR_PRESENT = 56
ADDR_CW      = 9    # 最小角度限制
ADDR_CCW     = 11   # 最大角度限制

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# ====== SCS 协议 ======
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

# ====== 读取限位 ======
def read_limits(ser):
    """返回 {1: [cw, ccw], 2: [cw, ccw], ...}"""
    limits = {}
    for sid in range(1, 7):
        cw = scs_read(ser, sid, ADDR_CW, 2)
        time.sleep(0.02)
        ccw = scs_read(ser, sid, ADDR_CCW, 2)
        if cw is not None and ccw is not None:
            limits[sid] = [cw, ccw]
        else:
            limits[sid] = [0, 4095]  # 兜底
    return limits

def clamp(val, lo, hi, margin=30):
    """裁剪到安全范围，留 30 步余量避免撞限位"""
    return max(lo + margin, min(hi - margin, val))

# ====== 舞蹈动作定义 ======
# 所有姿态都是相对 HOME 的偏移量 [Δbase, Δshoulder, Δelbow, Δwrist_rot, Δwrist_pitch, Δgripper]
# 正值=正向运动, 负值=反向运动

POSE_OFFSETS = {
    "举手":      [   0, +700, +300,    0,    0, +300],
    "前伸":      [   0, +200, +600,    0, -500, +400],
    "左摆":      [+400, +150, +200, +400, -200, -300],
    "右摆":      [-400, -250, +200, -450, +100, +200],
    "低姿态":    [   0, -600, -600,    0, +400,    0],
    "高昂":      [   0, +600, +500,    0, -200, +400],
    "招手左":    [   0, +200, +100, -450, +400, -100],
    "招手右":    [   0, +200, +100, +400, -200, +200],
    "侧身":      [+150, +400, -200, +400, +600,    0],
    "敬礼":      [   0, +200, +600, +400, -300, +400],
    "左转":      [+400,    0,    0, +400,    0,    0],
    "右转":      [-400,    0,    0, -400,    0,    0],
    "夹爪开":    [   0,    0,    0,    0,    0, -500],
    "夹爪合":    [   0,    0,    0,    0,    0, +200],
}

# ====== 舞蹈序列（用偏移名引用，不写死数值） ======
DANCES = {
    1: {
        "name": "💃 机械热舞",
        "bpm": 110,
        "steps": [
            ("举手",       ["举手"],              4),
            ("左右摇摆",   ["左摆", "右摆", "左摆", "右摆"], 2),
            ("前伸",       ["前伸"],              4),
            ("夹爪开合",   ["夹爪开", "夹爪合"],  2),
            ("低姿态",     ["低姿态"],            4),
            ("高昂",       ["高昂"],              4),
            ("敬礼",       ["敬礼"],              4),
        ]
    },
    2: {
        "name": "🤖 机器人舞",
        "bpm": 90,
        "steps": [
            ("左看",       ["左转"],              4),
            ("右看",       ["右转"],              4),
            ("前伸",       ["前伸"],              4),
            ("抬手",       ["举手"],              4),
            ("侧身",       ["侧身"],              4),
            ("左看",       ["左转"],              4),
            ("招手",       ["招手左", "招手右", "招手左", "招手右"], 2),
        ]
    },
    3: {
        "name": "👋 招手舞",
        "bpm": 120,
        "steps": [
            ("举手",       ["举手"],              4),
            ("招左手",     ["招手左"],            2),
            ("招右手",     ["招手右"],            2),
            ("招左手",     ["招手左"],            2),
            ("招右手",     ["招手右"],            2),
            ("快速挥手",   ["招手左", "招手右", "招手左", "招手右", "招手左", "招手右"], 1),
            ("敬礼",       ["敬礼"],              4),
        ]
    },
    4: {
        "name": "💪 力量展示",
        "bpm": 100,
        "steps": [
            ("蓄力",       ["低姿态"],            4),
            ("爆发",       ["高昂"],              2),
            ("蓄力",       ["低姿态"],            2),
            ("爆发",       ["高昂"],              2),
            ("侧展",       ["侧身"],              4),
            ("前伸",       ["前伸"],              4),
            ("敬礼",       ["敬礼"],              4),
        ]
    },
    5: {
        "name": "🕺 左右摇摆",
        "bpm": 130,
        "steps": [
            ("左摆",       ["左摆"],              2),
            ("右摆",       ["右摆"],              2),
            ("左摆",       ["左摆"],              2),
            ("右摆",       ["右摆"],              2),
            ("左摆",       ["左摆"],              2),
            ("右摆",       ["右摆"],              2),
            ("高举",       ["举手"],              4),
            ("归位",       [],                    2),   # 空=回HOME
        ]
    },
}

# ====== 平滑移动 ======
def lerp(a, b, t):
    return int(a + (b - a) * t)

def smoothstep(t):
    return t * t * (3 - 2 * t)

def move_to(ser, home, target, limits, duration, steps=25):
    """
    平滑移动到目标姿态
    home:     HOME 位置（6元素步数值）
    target:   目标位置（6元素步数值）
    limits:   各关节限位 {sid: [cw, ccw]}
    duration: 总时长（秒）
    """
    # 裁剪目标在限位内
    safe_target = []
    for i, sid in enumerate(range(1, 7)):
        lo, hi = limits[sid]
        safe_target.append(clamp(target[i], lo, hi))

    # 读当前位置作起点
    current = []
    for sid in range(1, 7):
        pos = scs_read(ser, sid, ADDR_PRESENT, 2)
        current.append(pos if pos is not None else safe_target[sid - 1])

    interval = duration / steps
    for step in range(steps + 1):
        t = smoothstep(step / steps)
        for i, sid in enumerate(range(1, 7)):
            mid = lerp(current[i], safe_target[i], t)
            scs_write(ser, sid, ADDR_GOAL, struct.pack('<H', mid))
        time.sleep(interval)

    # 最终精确写入
    for i, sid in enumerate(range(1, 7)):
        scs_write(ser, sid, ADDR_GOAL, struct.pack('<H', safe_target[i]))

def apply_offset(home, offsets, limits):
    """HOME + 偏移 → 目标位置，裁剪到限位"""
    target = []
    for i, sid in enumerate(range(1, 7)):
        lo, hi = limits[sid]
        val = home[i] + offsets[i]
        target.append(clamp(val, lo, hi))
    return target

# ====== 主逻辑 ======
if DANCE_ID is None:
    print("🕺 SO101 机械臂跳舞\n")
    print("可选舞蹈:")
    for k, v in DANCES.items():
        print(f"  {k}. {v['name']}")
    print(f"\n用法: python so101_dance.py {PORT} [编号]")
    print("\n提示: 先把机械臂摆到你想要的 HOME 位置（初始姿态），然后运行脚本")
    sys.exit(0)

if DANCE_ID not in DANCES:
    print(f"❌ 舞蹈编号 {DANCE_ID} 不存在")
    sys.exit(1)

dance = DANCES[DANCE_ID]
beat_sec = 60.0 / dance["bpm"]

print(f"🔌 {PORT} @ {BAUD}bps...")
ser = serial.Serial(PORT, BAUD, timeout=0.2)

# 扫描舵机
online = {}
for sid in range(1, 7):
    model = scs_ping(ser, sid)
    if model is not None:
        online[sid] = model
        scs_write(ser, sid, ADDR_TORQUE, b'\x01')
        time.sleep(0.03)

if len(online) < 6:
    print(f"⚠️ 仅 {len(online)}/6 舵机在线: {list(online.keys())}")
else:
    print(f"✅ 6 舵机在线")

# 读限位
limits = read_limits(ser)

# 读当前位置 → 这就是 HOME
print("📏 读取当前位置作为 HOME...")
HOME = []
for sid in range(1, 7):
    pos = scs_read(ser, sid, ADDR_PRESENT, 2)
    if pos is not None:
        HOME.append(pos)
    else:
        # 居中兜底
        lo, hi = limits[sid]
        HOME.append((lo + hi) // 2)
    time.sleep(0.02)

print(f"🏠 HOME = [{', '.join(str(h) for h in HOME)}]")
print(f"   ≈ [{', '.join(f'{h/4096*360:.1f}°' for h in HOME)}]")
print(f"{'='*50}")
print(f"  {dance['name']}  BPM={dance['bpm']}")
print(f"  所有动作相对于 HOME 做偏移，限位内安全")
print(f"{'='*50}")
print("随时 Ctrl+C 紧急停止!\n")

# 设置统一速度
for sid in range(1, 7):
    scs_write(ser, sid, ADDR_SPEED, struct.pack('<H', 200))
time.sleep(0.1)

try:
    for step_name, pose_names, beats in dance["steps"]:
        duration = beats * beat_sec

        if not pose_names:
            # 空列表 = 回 HOME
            print(f"  🏠 {step_name}  [{beats}拍, {duration:.1f}s]")
            move_to(ser, HOME, HOME, limits, duration)
        elif len(pose_names) == 1:
            target = apply_offset(HOME, POSE_OFFSETS[pose_names[0]], limits)
            print(f"  {step_name} → {pose_names[0]}  [{beats}拍, {duration:.1f}s]")
            move_to(ser, HOME, target, limits, duration)
        else:
            print(f"  {step_name}  [{beats}拍, {duration:.1f}s]")
            per_pose_dur = duration / len(pose_names)
            for name in pose_names:
                target = apply_offset(HOME, POSE_OFFSETS[name], limits)
                move_to(ser, HOME, target, limits, per_pose_dur)

    # 归位
    print(f"\n🏠 谢幕归位...")
    move_to(ser, HOME, HOME, limits, 3.0)

except KeyboardInterrupt:
    print("\n\n🛑 紧急停止!")

finally:
    print("释放扭矩...")
    for sid in range(1, 7):
        try:
            scs_write(ser, sid, ADDR_TORQUE, b'\x00')
        except:
            pass
    ser.close()
    print("✅ 安全退出")
