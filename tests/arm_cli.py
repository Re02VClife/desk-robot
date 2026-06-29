"""
机械臂命令行直控工具
====================
最简方式：串口连 ESP32，直接敲指令

用法: python arm_cli.py [--port COM6]
指令:
  文字内容     → 发送到小智 (如: 你好)
  !J:[a1,...,a6],speed=N  → 控制关节
  !G:open 或 !G:close     → 控制夹爪
  !HOME       → 归位
  q/quit/退出  → 退出
"""
import serial
import time
import sys
import io
import threading
import json

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SERIAL_PORT = "COM6"
BAUD = 115200

# ====== 连接串口 ======
print(f"🔌 连接 {SERIAL_PORT}...")
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
ser.dtr = True
time.sleep(0.1)
ser.dtr = False
time.sleep(0.2)
print("✅ 已连接，等待 ESP32 启动...\n")

# ====== 后台读取线程 ======
def reader_thread():
    buf = b""
    while ser and ser.is_open:
        try:
            if ser.in_waiting:
                data = ser.read(ser.in_waiting)
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        print(text, flush=True)
        except:
            break

reader = threading.Thread(target=reader_thread, daemon=True)
reader.start()

# ====== 等待 ESP32 进入 idle ======
print("⏳ 等待 WiFi 连接 + OTA + idle...", flush=True)
try:
    # 等待最多 20 秒
    for i in range(20):
        time.sleep(1)
        print(".", end="", flush=True)
    print("\n", flush=True)
except KeyboardInterrupt:
    pass

print("\n🦾 机械臂命令行就绪！")
print("  输入指令后回车：")
print("   - 普通文字 → 发小智对话")
print("   - !J:[90,45,90,90,90,90],speed=40 → 关节角度")
print("   - !G:open 或 !G:close → 夹爪")
print("   - !HOME → 归位")
print("   - /quit → 退出\n")

def send_cmd(cmd):
    ser.write((cmd + "\r\n").encode("utf-8"))
    ser.flush()
    print(f"📤 已发送: {cmd}", flush=True)

# ====== 主循环 ======
try:
    while True:
        user_input = input("> ").strip()
        if not user_input:
            continue
        if user_input in ("/quit", "q", "退出"):
            print("👋 退出")
            break
        if user_input.upper() == "!HOME":
            send_cmd("!J:[90,90,90,90,90,90],speed=60")
            continue
        send_cmd(user_input)
except KeyboardInterrupt:
    print("\n👋 退出")
finally:
    ser.close()
    print("串口已关闭")
