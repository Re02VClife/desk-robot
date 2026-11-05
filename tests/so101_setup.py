"""
SO101 舵机配置工具 (Windows)
============================
逐个配置 Feetech STS3215 舵机的 ID 和波特率。
接好 SO101 电源+USB，按提示每次只接一个舵机。

类比: lerobot-setup-motors --robot.type=so100_follower
"""
from scservo_sdk import *
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD_DEFAULT = 1000000

# Feetech 控制表地址 (EEPROM 区域)
ADDR_ID = 5            # ID (1 byte, EEPROM)
ADDR_BAUD = 6          # Baud Rate (1 byte, EEPROM, 1=1Mbps)
ADDR_EEPROM_LOCK = 55  # EEPROM lock (0=unlock)

JOINT_NAMES = ["底座(旋转)", "大臂(俯仰)", "小臂(俯仰)", "腕部(旋转)", "腕部(俯仰)", "夹爪"]

def find_any_servo(port, pkt):
    """扫描所有可能ID找到当前连接的舵机"""
    for sid in range(0, 253):
        try:
            m, r, e = pkt.ping(port, sid)
            if r == COMM_SUCCESS:
                return sid, m
        except:
            pass
    return None, None

def unlock_eeprom(port, pkt, sid):
    """解锁 EEPROM 以便写入"""
    pkt.write1ByteTxOnly(port, sid, ADDR_EEPROM_LOCK, 0)
    time.sleep(0.05)

def set_id(port, pkt, old_id, new_id):
    """设置舵机 ID"""
    unlock_eeprom(port, pkt, old_id)
    r, e = pkt.write1ByteTxRx(port, old_id, ADDR_ID, new_id)
    if r == COMM_SUCCESS:
        print(f"   ✅ ID已设为 {new_id}")
        return True
    else:
        print(f"   ❌ ID设置失败 (code={r})")
        return False

def set_baud(port, pkt, sid, baud_code=1):
    """设置波特率 (1=1Mbps)"""
    unlock_eeprom(port, pkt, sid)
    r, e = pkt.write1ByteTxRx(port, sid, ADDR_BAUD, baud_code)
    if r == COMM_SUCCESS:
        print(f"   ✅ 波特率已设为 1Mbps")
        return True
    else:
        print(f"   ❌ 波特率设置失败 (code={r})")
        return False

# ====== 主流程 ======
print("🛠️  SO101 舵机配置工具")
print(f"   串口: {PORT}")
print()
print("⚠️  重要: SO101 总线上每次只接一个舵机！")
print("   断开其他舵机，只保留当前要配置的一个。\n")

port = PortHandler(PORT)
if not port.openPort():
    print("❌ 无法打开串口")
    sys.exit(1)

for baud_try in [BAUD_DEFAULT, 115200, 500000]:
    if port.setBaudRate(baud_try):
        print(f"📡 波特率: {baud_try} bps")
        break

pkt = PacketHandler(1)

for target_id in range(1, 7):
    name = JOINT_NAMES[target_id - 1]
    print(f"\n{'='*50}")
    print(f"舵机 #{target_id}: {name}")
    print(f"{'='*50}")
    print(f"📋 请只连接舵机#{target_id}（断开其他所有舵机）")
    input(f"   接好后按回车...")

    # 扫描当前舵机
    old_id, model = find_any_servo(port, pkt)
    if old_id is None:
        print("   ❌ 未找到舵机! 检查接线后重试")
        continue

    print(f"   📍 当前ID={old_id}, 型号={model}")

    if old_id != target_id:
        print(f"   🔧 设置ID: {old_id} → {target_id}")
        set_id(port, pkt, old_id, target_id)
        old_id = target_id

    # 确保波特率是1M
    print(f"   🔧 确保波特率=1Mbps")
    set_baud(port, pkt, old_id, 1)

    # 验证
    time.sleep(0.3)
    m, r, e = pkt.ping(port, target_id)
    if r == COMM_SUCCESS:
        print(f"   ✅✅ 配置完成: ID={target_id}, 型号={m}")
    else:
        print(f"   ⚠️ 验证失败，可能需要重新上电")

print(f"\n{'='*50}")
print("✅ 全部6个舵机配置完成!")
print()
print("下一步:")
print("1. 断开USB，接回所有舵机（串联）")
print("2. 重新上电")
print("3. 运行: python so101_diag.py COM11 验证")
print(f"{'='*50}")

port.closePort()
