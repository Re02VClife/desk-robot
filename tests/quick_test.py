"""快速测试 - 用 idf.py monitor 风格发指令"""
import serial, time, sys

PORT = sys.argv[1] if len(sys.argv) > 1 else "COM12"
BAUD = 115200

# 先开串口（手动控制 DTR/RTS 不复位）
print(f"🔌 连接 {PORT}...")
ser = serial.Serial()
ser.port = PORT
ser.baudrate = BAUD
ser.timeout = 0.1
ser.dsrdtr = False
ser.rtscts = False
ser.open()

# 立即拉低 DTR/RTS（ESP32 在 DTR=低,RTS=高 时正常运行）
ser.dtr = False
ser.rts = False
time.sleep(0.5)

# 读走所有已有数据
buf = b""
for _ in range(40):
    if ser.in_waiting:
        buf += ser.read(ser.in_waiting)
    time.sleep(0.05)

print(f"📥 清掉 {len(buf)} 字节旧数据")

# 逐字符发送指令（模拟人打字，给 ESP32 的 getchar 时间消化）
cmd = '!{"cmd":"gripper","open":true,"speed":50}\n'
print(f"📤 逐字发送: {cmd.strip()}")
for ch in cmd:
    ser.write(ch.encode())
    ser.flush()
    time.sleep(0.02)  # 每字符 20ms

# 等待响应
print("⏳ 等待...")
buf = b""
for _ in range(100):
    if ser.in_waiting:
        chunk = ser.read(ser.in_waiting)
        buf += chunk
    time.sleep(0.05)

if buf:
    print(f"📥 收到 {len(buf)} 字节:")
    print(buf.decode('utf-8', 'ignore'))
else:
    print("❌ 无响应")

ser.close()
