"""极简串口调试：打开 COM6，发送文字，持续打印收到的所有数据"""
import serial
import time
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SERIAL_PORT = "COM6"
BAUD = 115200

# 1. 连接
print(f"🔌 连接 {SERIAL_PORT} @ {BAUD}bps...")
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
print(f"✅ 已连接")

# ESP32-S3 USB-serial-JTAG 需要正确设置 DTR/RTS
ser.dtr = False  # 不触发复位
ser.rts = False
print(f"   DTR={ser.dtr}, RTS={ser.rts}")
print(f"   缓冲区: {ser.in_waiting} 字节等待\n")

# 试试手动触发
ser.dtr = True
time.sleep(0.1)
ser.dtr = False
print(f"   触发 DTR 后缓冲区: {ser.in_waiting} 字节\n")

# 2. 先读取已有的缓冲数据
if ser.in_waiting:
    existing = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
    print(f"📥 缓冲数据: {existing[:500]}")

# 3. 后台持续打印收到的数据
last_print = time.time()

def read_all():
    """读取所有可用数据并打印"""
    if ser.in_waiting:
        data = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
        if data.strip():
            print(data, end="", flush=True)
        return True
    return False

# 先静默读 5 秒看有没有数据
print("⏳ 等待 5 秒收集初始数据...")
deadline = time.time() + 5
while time.time() < deadline:
    read_all()
    time.sleep(0.05)

print("\n📤 发送: 你好")
ser.write("你好\r\n".encode("utf-8"))
ser.flush()

# 再读 10 秒
print("⏳ 等待 10 秒读取回复...")
deadline = time.time() + 10
while time.time() < deadline:
    if read_all():
        pass
    time.sleep(0.05)

# 再发一次
print("\n📤 发送: hello")
ser.write("hello\r\n".encode("utf-8"))
ser.flush()

deadline = time.time() + 10
while time.time() < deadline:
    if read_all():
        pass
    time.sleep(0.05)

print("\n\n=== 测试结束 ===")
ser.close()
