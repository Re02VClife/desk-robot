"""
机械臂自动化测试脚本
====================
自动：连接串口 → 等 ESP32 就绪 → 触发 WebSocket → 发送关节指令序列

用法：python arm_test.py
接线要求：IO9(TX)→SO101 RX, IO10(RX)→SO101 TX, GND↔GND
观察：机械臂是否按指令序列运动
"""
import serial
import time
import sys
import io
import threading

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

SERIAL_PORT = "COM6"
BAUD = 115200

# ====== 连接串口 ======
print(f"🔌 连接 {SERIAL_PORT}...")
ser = serial.Serial(SERIAL_PORT, BAUD, timeout=0.1)
# 先什么都不做，等 3 秒看有没有自发数据
time.sleep(3)
buffered = ser.in_waiting
print(f"📊 连接后3秒缓冲区: {buffered} 字节")

if buffered == 0:
    # 手动触发 DTR 复位
    print("触发 DTR 复位...")
    ser.dtr = True
    time.sleep(0.2)
    ser.dtr = False
    time.sleep(3)
    buffered = ser.in_waiting
    print(f"📊 DTR复位后缓冲区: {buffered} 字节")

if buffered > 0:
    preview = ser.read(min(buffered, 300)).decode("utf-8", errors="replace")
    print(f"   预览: {preview[:200]}")
print("✅ 已连接\n")

# ====== 后台读取 ======
idle_detected = False

def reader():
    global idle_detected
    buf = b""
    err_count = 0
    while ser and ser.is_open:
        try:
            waiting = ser.in_waiting
            if waiting > 0:
                data = ser.read(waiting)
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    text = line.decode("utf-8", errors="replace").strip()
                    if text:
                        print(text, flush=True)
                        if "activating -> idle" in text:
                            idle_detected = True
            else:
                time.sleep(0.02)
        except Exception as e:
            err_count += 1
            if err_count <= 3:
                print(f"[串口错误#{err_count}: {e}]", flush=True)
            time.sleep(0.5)

threading.Thread(target=reader, daemon=True).start()

# ====== 等待 idle ======
print("⏳ 等待 ESP32 就绪 (activating -> idle)...", flush=True)
for i in range(30):
    if idle_detected:
        print(" ✅ 检测到 idle!\n", flush=True)
        break
    time.sleep(1)
    # 每 5 秒报告状态
    if i > 0 and i % 5 == 0:
        print(f"  [{i}s] 缓冲区:{ser.in_waiting}B idle={idle_detected}", flush=True)
else:
    print(" 超时，继续等待15秒...\n")
    time.sleep(15)

# 额外等待稳定
time.sleep(3)

# ====== 发送命令序列 ======
def cmd(text):
    print(f"\n📤 >>> {text}", flush=True)
    ser.write((text + "\r\n").encode("utf-8"))
    ser.flush()
    time.sleep(0.3)

# 步骤1：触发 WebSocket 连接
print("\n" + "="*50)
print("步骤1: 触发 WebSocket 连接")
print("="*50)
cmd("hello")

# 等待连接建立
print("⏳ 等待连接建立 (10秒)...\n", flush=True)
time.sleep(10)

# 步骤2：归位
print("\n" + "="*50)
print("步骤2: 归位 → [90,90,90,90,90,90]")
print("="*50)
cmd("!J:[90,90,90,90,90,90],speed=60")
time.sleep(2)

# 步骤3：关节1 左转
print("\n" + "="*50)
print("步骤3: 关节1(底座)左转 → 45°")
print("="*50)
cmd("!J:[45,90,90,90,90,90],speed=40")
time.sleep(2)

# 步骤4：关节1 右转
print("\n" + "="*50)
print("步骤4: 关节1(底座)右转 → 135°")
print("="*50)
cmd("!J:[135,90,90,90,90,90],speed=40")
time.sleep(2)

# 步骤5：关节1 回中
print("\n" + "="*50)
print("步骤5: 关节1 回中 → 90°")
print("="*50)
cmd("!J:[90,90,90,90,90,90],speed=40")
time.sleep(2)

# 步骤6：关节2 抬起
print("\n" + "="*50)
print("步骤6: 关节2(大臂)抬起 → 120°")
print("="*50)
cmd("!J:[90,120,90,90,90,90],speed=40")
time.sleep(2)

# 步骤7：关节2 放下
print("\n" + "="*50)
print("步骤7: 关节2(大臂)放下 → 45°")
print("="*50)
cmd("!J:[90,45,90,90,90,90],speed=40")
time.sleep(2)

# 步骤8：归位
print("\n" + "="*50)
print("步骤8: 归位")
print("="*50)
cmd("!J:[90,90,90,90,90,90],speed=60")
time.sleep(2)

# 步骤9：夹爪测试
print("\n" + "="*50)
print("步骤9: 夹爪张开")
print("="*50)
cmd("!G:open,50")
time.sleep(1.5)
print("\n" + "="*50)
print("步骤10: 夹爪闭合")
print("="*50)
cmd("!G:close,50")
time.sleep(1.5)

print("\n" + "="*50)
print("✅ 测试序列完成！")
print("   如果机械臂没动，请检查：")
print("   1. IO9(TX)→SO101 RX, IO10(RX)→SO101 TX, GND↔GND")
print("   2. SO101 驱动板是否上电")
print("   3. 服务器是否在运行")
print("="*50)

ser.close()
