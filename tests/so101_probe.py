"""
SO101 自动探测脚本
==================
自动尝试不同波特率/协议，找到 SO101 的正确通信方式。
"""
import serial
import time
import sys
import io
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM11"

# SO101 可能使用的波特率（从高到低，常见伺服驱动波特率）
BAUD_RATES = [1000000, 921600, 460800, 230400, 115200, 57600, 38400, 9600]

# 测试的指令格式
TEST_COMMANDS = [
    # 格式1: JSON (ESP32格式)
    b'{"cmd":"move_joints","angles":[90,60,90,90,90,90],"speed":30}\n',
    # 格式2: 紧凑JSON
    b'{"cmd":"move_joints","angles":[90,60,90,90,90,90],"speed":30}\r\n',
    # 格式3: 简单角度数组
    b'[90,60,90,90,90,90]\n',
    # 格式4: Lerobot格式
    b'{"action":"move","joints":[90,60,90,90,90,90]}\n',
]

sep = "=" * 50
print(f"🔍 SO101 自动探测 - {PORT}")
print(f"   将尝试 {len(BAUD_RATES)} 种波特率 x {len(TEST_COMMANDS)} 种指令格式")
print("   " + sep + "\n")

for baud in BAUD_RATES:
    print(f"🔄 尝试波特率: {baud} bps...")
    try:
        ser = serial.Serial(PORT, baud, timeout=1.0)
        ser.dtr = True
        time.sleep(0.1)
        ser.dtr = False
        time.sleep(0.3)

        # 先读是否有欢迎信息
        if ser.in_waiting:
            data = ser.read(ser.in_waiting)
            try:
                text = data.decode("utf-8", errors="replace")
                if len(text.strip()) > 2:
                    print(f"   📥 启动数据({len(data)}B): {text[:200]}")
            except:
                print(f"   📥 启动数据({len(data)}B): {data[:50].hex()}")

        # 尝试每种指令格式
        for i, cmd in enumerate(TEST_COMMANDS):
            ser.reset_input_buffer()
            ser.write(cmd)
            ser.flush()
            time.sleep(0.5)

            if ser.in_waiting:
                reply = ser.read(ser.in_waiting)
                if reply:
                    try:
                        text = reply.decode("utf-8", errors="replace").strip()
                        print(f"   ✅ {baud}bps 格式{i+1}: 有回复! → {text[:100]}")
                    except:
                        print(f"   ✅ {baud}bps 格式{i+1}: 有回复! → {reply[:20].hex()}")
                    ser.close()
                    sys.exit(0)

        # 无回复
        if i == len(TEST_COMMANDS) - 1:
            print(f"   ❌ 无回复", end="")
        ser.close()

    except Exception as e:
        print(f"   ⚠️ 错误: {e}")

print("\n" + sep)
print("探测完成 - 所有波特率/格式均无回复")
print()
print("可能原因:")
print("1. SO101 CH343 USB口是固件烧录口，不是控制口")
print("2. SO101 需要特定初始化序列")
print("3. 需要先给 SO101 上电（接电源）")
print("4. 接线是 IO9/IO10 - SO101 的 RX/TX 排针，不走 USB")
print()
print("ESP32 已加串口透传，重新编译烧录后可直接通过 ESP32 转发指令")
