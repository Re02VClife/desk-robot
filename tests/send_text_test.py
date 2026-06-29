"""
ESP32 文字对话测试 v5 — 重点捕获 WebSocket 连接日志
"""
import serial, time

PORT, BAUD = "COM6", 115200

ser = serial.Serial(PORT, BAUD, timeout=0.1)
ser.dtr = ser.rts = False

# 等 boot 完成（idle）
print("⏳ 等 idle...")
start = time.time()
while time.time() - start < 35:
    if ser.in_waiting:
        data = ser.read(ser.in_waiting).decode(errors="replace")
        if "idle" in data:
            time.sleep(2)
            ser.reset_input_buffer()
            print("✅ idle，发送 你好")
            break
    time.sleep(0.2)

# 发文字
ser.write("你好\n".encode())
time.sleep(0.3)

# 长等待，捕获 WebSocket + 后续日志
print("⏳ 捕获日志（60秒），找关键词: websocket, tcp, connect, error...\n")
keywords = ["websocket", "WebSocket", "tcp", "TCP", "connect", "error", "Error", "8000", "hello", "Hello"]
start = time.time()
while time.time() - start < 60:
    if ser.in_waiting:
        data = ser.read(ser.in_waiting).decode(errors="replace")
        for kw in keywords:
            if kw.lower() in data.lower():
                print(f"\n🔍 找到关键词 '{kw}' 附近日志:")
        print(data, end="", flush=True)
    time.sleep(0.2)

ser.close()
print("\n✅ 完成 — 检查上面是否有 WebSocket 连接相关日志")
