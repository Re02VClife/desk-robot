"""SO101 深度扫描 — 全部波特率+全部ID+两种协议"""
from scservo_sdk import *
import sys, time

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"
# 所有可能的 Feetech 波特率 (BPS)
BAUDS = [1000000, 500000, 250000, 115200, 57600, 38400, 19200, 9600]
# 对应波特率代码
BAUD_CODES = {1000000: 1, 500000: 2, 250000: 3, 115200: 4, 57600: 5, 38400: 6, 19200: 7, 9600: 0}

print("🔍 SO101 深度扫描\n")

port = PortHandler(PORT)
port.openPort()

found_any = False

for protocol in [1, 0]:  # 1=STS, 0=SMS
    for baud in BAUDS:
        port.setBaudRate(baud)
        pkt = PacketHandler(protocol)
        for sid in range(0, 254):  # 扫描全部ID
            try:
                m, r, e = pkt.ping(port, sid)
                if r == COMM_SUCCESS:
                    print(f"✅ 协议{protocol} {baud}bps ID={sid} 型号={m}")
                    found_any = True
            except:
                pass
        time.sleep(0.1)

if not found_any:
    print("\n❌ 全部扫描无结果")
    print("\n可能原因:")
    print("1. 舵机配置丢失 - 需要硬件复位（断电≥2分钟后重试）")
    print("2. 舵机物理损坏 (第一次撞限位可能烧了驱动)")
    print("3. USB转串口芯片故障")
    print("\n建议: 在 Ubuntu 上试一下 lerobot，确认舵机是否还活着")

port.closePort()
