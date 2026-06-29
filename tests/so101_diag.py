"""
SO101 诊断脚本
=============
最简诊断：连接 → 逐个舵机尝试 ping + 读位置，不写任何数据。
"""
from scservo_sdk import *
import sys
import time

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
BAUD = 1000000
ADDR_PRESENT_POSITION = 56

JOINT_NAMES = ["底座", "大臂", "小臂", "腕转", "腕俯", "夹爪"]

print(f"🔌 {PORT} @ {BAUD}bps...")
port = PortHandler(PORT)
port.openPort()
port.setBaudRate(BAUD)
packet = PacketHandler(1)
print("✅ 串口就绪\n")

print("🔍 逐个诊断舵机...")
ok_count = 0
for servo_id in range(1, 7):
    print(f"\n--- 舵机 {servo_id} ({JOINT_NAMES[servo_id-1]}) ---")

    # 尝试 ping (可能报错)
    try:
        model, result, error = packet.ping(port, servo_id)
        if result == COMM_SUCCESS:
            print(f"  ✅ Ping成功, 型号={model}")
        else:
            print(f"  ❌ Ping失败, code={result}")
            continue
    except Exception as e:
        print(f"  ❌ Ping异常: {e}")
        continue

    # 尝试读位置
    try:
        pos, result, error = packet.read2ByteTxRx(port, servo_id, ADDR_PRESENT_POSITION)
        if result == COMM_SUCCESS:
            angle = pos / 4095 * 360
            print(f"  📍 当前位置={pos} (约{angle:.1f}°)")
        else:
            print(f"  ⚠️ 读位置失败, code={result}")
    except Exception as e:
        print(f"  ⚠️ 读位置异常: {e}")

    ok_count += 1

print(f"\n{'='*40}")
print(f"诊断结果: {ok_count}/6 舵机正常")
print("如果 0 个在线 → SO101 断电再上电 (拔插12V)")
print("如果部分在线 → 检查舵机接线 (是否串联)")
port.closePort()
