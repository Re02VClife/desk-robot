"""
小智 AI 串口助手 — 图形化测试工具
- 实时显示 ESP32 串口输出
- 输入框发送文字
- 自动保存日志
"""
import tkinter as tk
from tkinter import scrolledtext, ttk
import serial
import threading
import time
import queue
import os
from datetime import datetime

class XiaozhiSerialAssistant:
    def __init__(self, root):
        self.root = root
        self.root.title("小智 AI 串口助手")
        self.root.geometry("900x650")

        # ---- 顶部：连接设置 ----
        frame_top = ttk.Frame(root)
        frame_top.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(frame_top, text="端口:").pack(side=tk.LEFT)
        self.cb_port = ttk.Combobox(frame_top, width=8, values=["COM3","COM4","COM5","COM6","COM7","COM8","COM9"])
        self.cb_port.set("COM6")
        self.cb_port.pack(side=tk.LEFT, padx=5)

        ttk.Label(frame_top, text="波特率:").pack(side=tk.LEFT)
        self.cb_baud = ttk.Combobox(frame_top, width=10, values=["9600","115200","460800","921600"])
        self.cb_baud.set("115200")
        self.cb_baud.pack(side=tk.LEFT, padx=5)

        self.btn_conn = ttk.Button(frame_top, text="🔗 连接", command=self.toggle_connect)
        self.btn_conn.pack(side=tk.LEFT, padx=5)

        self.status_lbl = ttk.Label(frame_top, text="⚪ 未连接", foreground="red")
        self.status_lbl.pack(side=tk.LEFT, padx=10)

        self.btn_save = ttk.Button(frame_top, text="💾 保存日志", command=self.save_log)
        self.btn_save.pack(side=tk.RIGHT, padx=5)

        # ---- 中部：日志输出 ----
        self.log_area = scrolledtext.ScrolledText(root, wrap=tk.WORD, font=("Consolas", 10))
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # ---- 底部：输入区 ----
        frame_bot = ttk.Frame(root)
        frame_bot.pack(fill=tk.X, padx=10, pady=5)

        self.entry = ttk.Entry(frame_bot, font=("Microsoft YaHei", 12))
        self.entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self.entry.bind("<Return>", self.send_text)
        self.entry.focus_set()

        self.btn_send = ttk.Button(frame_bot, text="📤 发送", command=self.send_text)
        self.btn_send.pack(side=tk.RIGHT)

        # 快捷按钮
        ttk.Button(frame_bot, text="你好", width=6, command=lambda: self.quick_send("你好")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(frame_bot, text="/help", width=6, command=lambda: self.quick_send("/help")).pack(side=tk.RIGHT, padx=2)
        ttk.Button(frame_bot, text="换行", width=6, command=lambda: self.serial_write("\n")).pack(side=tk.RIGHT, padx=2)

        # ---- 状态 ----
        self.serial = None
        self.running = False
        self.msg_queue = queue.Queue()
        self.logs = []

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.poll_queue()

    def toggle_connect(self):
        if self.serial and self.serial.is_open:
            self.disconnect()
        else:
            self.connect()

    def connect(self):
        try:
            port = self.cb_port.get()
            baud = int(self.cb_baud.get())
            self.serial = serial.Serial(port, baud, timeout=0.1)
            self.serial.dtr = False
            self.serial.rts = False
            self.running = True
            self.btn_conn.config(text="🔌 断开")
            self.status_lbl.config(text="🟢 已连接", foreground="green")
            self.log(f"✅ 已连接 {port} @ {baud} bps", "green")
            # 启动读线程
            self.read_thread = threading.Thread(target=self.read_loop, daemon=True)
            self.read_thread.start()
        except Exception as e:
            self.log(f"❌ 连接失败: {e}", "red")

    def disconnect(self):
        self.running = False
        if self.serial:
            try:
                self.serial.close()
            except:
                pass
            self.serial = None
        self.btn_conn.config(text="🔗 连接")
        self.status_lbl.config(text="⚪ 未连接", foreground="red")
        self.log("🔌 已断开", "orange")

    def read_loop(self):
        while self.running and self.serial and self.serial.is_open:
            try:
                if self.serial.in_waiting:
                    data = self.serial.read(self.serial.in_waiting).decode(errors="replace")
                    self.msg_queue.put(("data", data))
                time.sleep(0.05)
            except Exception as e:
                self.msg_queue.put(("error", str(e)))
                break

    def poll_queue(self):
        try:
            while True:
                msg_type, msg = self.msg_queue.get_nowait()
                if msg_type == "data":
                    self.append_text(msg)
                elif msg_type == "error":
                    self.log(f"❌ {msg}", "red")
        except queue.Empty:
            pass
        self.root.after(50, self.poll_queue)

    def append_text(self, text):
        self.log_area.insert(tk.END, text)
        self.log_area.see(tk.END)
        self.logs.append(text)

    def log(self, msg, color="black"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{ts}] {msg}\n")
        self.log_area.see(tk.END)
        self.logs.append(f"[{ts}] {msg}\n")

    def serial_write(self, text):
        if self.serial and self.serial.is_open:
            try:
                if isinstance(text, str):
                    text = (text + "\n").encode("utf-8")
                self.serial.write(text)
                self.log(f"📤 已发送: {text.decode('utf-8', errors='replace').strip()}", "blue")
            except Exception as e:
                self.log(f"❌ 发送失败: {e}", "red")

    def send_text(self, event=None):
        text = self.entry.get()
        if text.strip():
            self.serial_write(text)
            self.entry.delete(0, tk.END)

    def quick_send(self, text):
        self.entry.delete(0, tk.END)
        self.entry.insert(0, text)
        self.send_text()

    def save_log(self):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(os.path.expanduser("~"), "Desktop", f"xiaozhi_log_{ts}.txt")
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(self.logs)
        self.log(f"💾 日志已保存: {filepath}", "green")

    def on_close(self):
        self.disconnect()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = XiaozhiSerialAssistant(root)
    root.mainloop()
