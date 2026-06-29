"""
SO101 简易交互控制
==================
扫描 → 读当前位置 → 输入角度移动单个关节
"""
from scservo_sdk import *
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000
ADDR_TORQUE = 40
ADDR_GOAL = 42
ADDR_SPEED = 46
ADDR_POS = 56

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

# 连接
port = PortHandler(PORT)
port.openPort()
port.setBaudRate(BAUD)
packet = PacketHandler(1)
print(f"✅ {PORT} 就绪\n")

# 扫描
print("🔍 扫描舵机...")
positions = {}
for sid in range(1, 7):
    model, result, error = packet.ping(port, sid)
    if result == COMM_SUCCESS:
        # 读位置
        try:
            pos, r2, e2 = packet.read2ByteTxRx(port, sid, ADDR_POS)
            if r2 == COMM_SUCCESS:
                positions[sid] = pos
                print(f"  ID{sid} {JOINT_NAMES[sid-1]}: 型号={model} 位置={pos}")
            else:
                print(f"  ID{sid} {JOINT_NAMES[sid-1]}: 型号={model} 位置读取失败")
        except:
            print(f"  ID{sid} {JOINT_NAMES[sid-1]}: 型号={model} 位置异常")
    else:
        print(f"  ID{sid} {JOINT_NAMES[sid-1]}: 离线")

if not positions:
    print("\n无舵机! SO101上电了没?")
    port.closePort()
    sys.exit(1)

print(f"\n在线: {len(positions)}/6")

# 交互
print("\n" + "=" * 50)
print("指令: jN +/-角度  (如 j2 +10 = 关节2正转10°)")
print("      home       (回中位)")
print("      q          (退出)")
print("      Ctrl+C     (紧急停止)")
print("=" * 50)

# 当前中位（记录初始位置作为 "home"）
home = dict(positions)

def move_joint(sid, target_pos):
    """移动单个关节到目标位置"""
    target_pos = max(0, min(65535, int(target_pos)))
    packet.write1ByteTxOnly(port, sid, ADDR_TORQUE, 1)
    time.sleep(0.02)
    packet.write2ByteTxRx(port, sid, ADDR_SPEED, 500)
    result, error = packet.write2ByteTxRx(port, sid, ADDR_GOAL, target_pos)
    return result == COMM_SUCCESS

try:
    while True:
        cmd = input("\n> ").strip().lower()
        if not cmd:
            continue
        if cmd in ('q', 'quit', 'exit'):
            break
        if cmd == 'home':
            for sid, pos in home.items():
                print(f"  归位 ID{sid} → {pos}...")
                move_joint(sid, pos)
                time.sleep(0.3)
            continue

        # jN +/-角度
        if cmd.startswith('j'):
            try:
                parts = cmd[1:].split()
                sid = int(parts[0])
                delta_deg = float(parts[1])
                # 1° ≈ 4096/360 ≈ 11.38 步
                delta = int(delta_deg * 4096 / 360)

                if sid in positions:
                    old = positions[sid]
                    new_pos = old + delta
                    print(f"  ID{sid} {JOINT_NAMES[sid-1]}: {old} + {delta} → {new_pos}")
                    if move_joint(sid, new_pos):
                        time.sleep(1)
                        try:
                            new_read, r, e = packet.read2ByteTxRx(port, sid, ADDR_POS)
                            if r == COMM_SUCCESS:
                                positions[sid] = new_read
                                print(f"  实际位置: {new_read}")
                        except:
                            pass
                    else:
                        print("  写入失败")
                else:
                    print(f"  ID{sid} 不在线")
            except:
                print("  格式: j2 +10 或 j3 -5")

except KeyboardInterrupt:
    print("\n🛑 停止")

# 释放
print("释放扭矩...")
for sid in range(1, 7):
    try:
        packet.write1ByteTxOnly(port, sid, ADDR_TORQUE, 0)
    except:
        pass
port.closePort()
print("退出")
