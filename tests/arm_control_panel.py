"""
机械臂关节直控面板 (V2)
========================
通过串口发送 !J: / !G: 调试指令到 ESP32，绕过 LLM/MCP 意图链路。

ESP32 文字控制台 → WebSocket → 服务器 intentHandler._handle_debug_command
  → MCP tools/call → ESP32 → UART1 → SO101 驱动板

用法：
  python arm_control_panel.py [--port COM6] [--web 5556]

然后浏览器打开 http://localhost:5556
"""
import json
import sys
import io
import time
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
logger = logging.getLogger("ArmPanel")

# ========== 串口通信 ==========

try:
    import serial
except ImportError:
    print("需要 pyserial: pip install pyserial")
    sys.exit(1)

SERIAL_PORT = "COM6"
BAUD_RATE = 115200

ser = None
ser_lock = threading.Lock()

# 串口监听缓冲区
serial_log_lines = []  # 最近 200 行
serial_log_lock = threading.Lock()
_reader_thread = None
_reader_running = False


def _serial_reader():
    """后台线程：持续读取串口数据"""
    global ser, serial_log_lines, _reader_running
    buf = b""
    logger.info("串口监听线程已启动")
    while _reader_running:
        try:
            if ser and ser.is_open:
                waiting = ser.in_waiting
                if waiting > 0:
                    chunk = ser.read(waiting)
                    buf += chunk
                    # 每次收到数据打印到终端
                    text_preview = chunk.decode("utf-8", errors="replace")[:100]
                    logger.info(f"📟 串口收到 {waiting}B")
                    # 按行分割
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        text = line.decode("utf-8", errors="replace").strip()
                        if text:
                            with serial_log_lock:
                                serial_log_lines.append(text)
                                if len(serial_log_lines) > 200:
                                    serial_log_lines = serial_log_lines[-200:]
                else:
                    time.sleep(0.05)
            else:
                time.sleep(0.5)
        except Exception as e:
            logger.error(f"串口读取异常: {e}")
            time.sleep(0.1)


def serial_connect(port=SERIAL_PORT):
    global ser, _reader_thread, _reader_running
    try:
        ser = serial.Serial(port, BAUD_RATE, timeout=0.1)
        # ESP32-S3 USB-serial-JTAG 必须触发 DTR 才能收到串口数据
        ser.dtr = True
        time.sleep(0.1)
        ser.dtr = False
        logger.info(f"串口 {port} 已连接")
        # 启动后台监听线程
        _reader_running = True
        _reader_thread = threading.Thread(target=_serial_reader, daemon=True)
        _reader_thread.start()
        return True
    except Exception as e:
        logger.error(f"串口连接失败 ({port}): {e}")
        return False


def serial_send(text: str) -> str:
    """发送文本到 ESP32（追加换行符），读取回复"""
    global ser
    with ser_lock:
        if not ser or not ser.is_open:
            return "ERROR:串口未连接"
        try:
            full = text + "\r\n"
            ser.write(full.encode("utf-8"))
            ser.flush()
            logger.info(f"📤 串口发送: {text}")
            # 读取回复（等待最多 2 秒）
            time.sleep(0.2)
            lines = []
            deadline = time.time() + 2.0
            while time.time() < deadline:
                if ser.in_waiting:
                    chunk = ser.read(ser.in_waiting).decode("utf-8", errors="replace")
                    lines.append(chunk)
                else:
                    time.sleep(0.05)
            reply = "".join(lines).strip()
            # 同步到日志缓冲区
            if reply:
                with serial_log_lock:
                    for line in reply.split("\n"):
                        line = line.strip()
                        if line:
                            serial_log_lines.append(line)
                            if len(serial_log_lines) > 200:
                                serial_log_lines = serial_log_lines[-200:]
                logger.info(f"📥 串口回复: {reply[:200]}")
            return reply if reply else "OK (无回复)"
        except Exception as e:
            logger.error(f"串口发送失败: {e}")
            return f"ERROR:{e}"


def serial_close():
    global ser, _reader_running
    _reader_running = False
    if ser and ser.is_open:
        ser.close()
        logger.info("串口已关闭")


def send_joints(angles: list, speed: int = 40):
    """发送关节角度指令: !J:[a1,a2,a3,a4,a5,a6],speed=N"""
    safe = [max(0, min(180, int(a))) for a in angles[:6]]
    while len(safe) < 6:
        safe.append(90)
    cmd = f"!J:{json.dumps(safe)},speed={speed}"
    return serial_send(cmd)


def send_gripper(open_grip: bool, speed: int = 50):
    """发送夹爪指令: !G:open 或 !G:close"""
    action = "open" if open_grip else "close"
    cmd = f"!G:{action},{speed}"
    return serial_send(cmd)


def send_chat(text: str):
    """发送普通文字（无前缀，触发 WebSocket 连接）"""
    return serial_send(text)


# ========== Web UI ==========

HTML_PAGE = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>机械臂关节直控面板</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: 'Segoe UI', system-ui, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
  .container { max-width: 700px; margin: 0 auto; padding: 20px; }
  h1 { text-align: center; color: #e94560; margin-bottom: 4px; font-size: 1.4em; }
  .subtitle { text-align: center; color: #888; margin-bottom: 16px; font-size: 0.8em; }
  .status { text-align: center; padding: 8px; border-radius: 6px; margin-bottom: 14px; font-weight: bold; font-size: 0.9em; }
  .status.on { background: #0f3460; color: #4ecca3; }
  .status.off { background: #533535; color: #e94560; }

  .joint { background: #16213e; border-radius: 10px; padding: 12px 16px; margin-bottom: 8px; }
  .joint-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
  .joint-name { font-weight: bold; font-size: 0.95em; }
  .joint-desc { color: #888; font-size: 0.73em; }
  .joint-value { font-size: 1.3em; font-weight: bold; color: #4ecca3; min-width: 55px; text-align: right; }

  input[type=range] { width: 100%; height: 20px; -webkit-appearance: none; background: #0f3460; border-radius: 10px; outline: none; }
  input[type=range]::-webkit-slider-thumb { -webkit-appearance: none; width: 26px; height: 26px; background: #e94560; border-radius: 50%; cursor: pointer; border: 2px solid #fff; }

  .speed-row { display: flex; align-items: center; gap: 10px; margin: 12px 0; background: #16213e; padding: 10px 14px; border-radius: 8px; }
  .speed-row label { font-weight: bold; white-space: nowrap; }
  .speed-row input { flex: 1; }
  .speed-row span { min-width: 40px; text-align: right; font-weight: bold; color: #4ecca3; }

  .controls { display: flex; gap: 8px; flex-wrap: wrap; }
  button { flex: 1; min-width: 90px; padding: 11px 14px; border: none; border-radius: 8px; font-size: 0.9em; font-weight: bold; cursor: pointer; transition: all 0.15s; }
  button:hover { transform: translateY(-1px); }
  button:active { transform: scale(0.97); }
  .btn-open { background: #4ecca3; color: #1a1a2e; }
  .btn-close { background: #e94560; color: #fff; }
  .btn-home { background: #0f3460; color: #fff; }
  .btn-preset { background: #5335a0; color: #fff; font-size: 0.8em; }

  .chat-row { display: flex; gap: 8px; margin-top: 12px; }
  .chat-row input { flex: 1; padding: 10px 14px; border: 1px solid #0f3460; border-radius: 8px; background: #16213e; color: #eee; font-size: 0.9em; outline: none; }
  .chat-row input:focus { border-color: #4ecca3; }

  .log-box { background: #0d1117; border-radius: 8px; margin-top: 14px; padding: 10px; max-height: 150px; overflow-y: auto; font-family: 'Cascadia Code', monospace; font-size: 0.75em; line-height: 1.4; }
  .log-ok { color: #4ecca3; }
  .log-err { color: #e94560; }
  .log-info { color: #58a6ff; }
</style>
</head>
<body>
<div class="container">
  <h1>🦾 机械臂关节直控</h1>
  <div class="subtitle">串口 → ESP32 → MCP → UART1 → SO101</div>
  <div id="status" class="status off">⏳ 检测连接...</div>
  <div id="joints"></div>

  <div class="speed-row">
    <label>⚡ 速度:</label>
    <input type="range" id="speed" min="10" max="100" value="40" step="5">
    <span id="speedVal">40</span>
  </div>

  <div class="controls">
    <button class="btn-open" onclick="gripper(true)">🖐 张开</button>
    <button class="btn-close" onclick="gripper(false)">✊ 闭合</button>
    <button class="btn-home" onclick="goHome()">🏠 归位</button>
    <button class="btn-preset" onclick="goPreset('rest')">🪑 休息</button>
    <button class="btn-preset" onclick="goPreset('forward')">➡ 前伸</button>
  </div>

  <div class="chat-row">
    <input type="text" id="chatInput" placeholder="输入文字触发 WebSocket 连接（如"你好"）" onkeydown="if(event.key==='Enter')sendChat()">
    <button onclick="sendChat()" style="flex:0;min-width:60px;padding:10px 16px;background:#4ecca3;color:#1a1a2e;">发送</button>
  </div>

  <div class="log-box" id="log"><div class="log-info">🟡 等待操作...</div></div>

  <details style="margin-top:14px;">
    <summary style="color:#888;cursor:pointer;font-size:0.85em;">📟 ESP32 串口输出 (实时)</summary>
    <div class="log-box" id="serialLog" style="max-height:250px;margin-top:8px;"><div class="log-info">等待数据...</div></div>
  </details>
</div>

<script>
const JOINTS = [
  ["关节1 底座旋转", "0最左 · 90正中 · 180最右"],
  ["关节2 大臂俯仰", "0最低 · 90水平 · 180最高 ⬆抬起"],
  ["关节3 小臂俯仰", "0收起 · 90水平 · 180展开"],
  ["关节4 腕部旋转", "手腕左右转"],
  ["关节5 腕部俯仰", "30下弯 · 90水平 · 150上翘"],
  ["关节6 末端旋转", "夹爪旋转"],
];

let angles = [90, 90, 90, 90, 90, 90];
let speed = 40;
let connected = false;
let debounceTimer = null;

function render() {
  document.getElementById('joints').innerHTML = JOINTS.map((j, i) => `
    <div class="joint">
      <div class="joint-header">
        <div>
          <div class="joint-name">${j[0]}</div>
          <div class="joint-desc">${j[1]}</div>
        </div>
        <div class="joint-value" id="v${i}">${angles[i]}°</div>
      </div>
      <input type="range" min="0" max="180" value="${angles[i]}" step="1"
             oninput="setJoint(${i}, +this.value)">
    </div>
  `).join('');
}

function setJoint(idx, val) {
  angles[idx] = val;
  document.getElementById('v'+idx).textContent = val + '°';
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(sendJoints, 80);
}

async function sendJoints() {
  try {
    const r = await fetch('/api/joints', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({angles, speed})
    });
    const d = await r.json();
    addLog(d.ok ? 'ok' : 'err', `关节→${JSON.stringify(d.angles||angles)} ${d.reply||''}`);
    document.getElementById('status').className = 'status on';
    document.getElementById('status').textContent = '✅ 已连接 · 拖动滑块控制关节';
  } catch(e) {
    addLog('err', '发送失败: ' + e.message);
  }
}

async function gripper(open) {
  try {
    const r = await fetch('/api/gripper', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({open, speed})
    });
    const d = await r.json();
    addLog(d.ok ? 'ok' : 'err', (open ? '🖐张开' : '✊闭合') + ' ' + (d.reply||''));
  } catch(e) {
    addLog('err', '夹爪失败: ' + e.message);
  }
}

function goHome() {
  angles = [90, 90, 90, 90, 90, 90];
  render();
  sendJoints();
}

function goPreset(name) {
  const presets = {
    rest: [90, 30, 30, 90, 90, 90],
    forward: [90, 90, 150, 90, 90, 90],
  };
  angles = presets[name] || angles;
  render();
  sendJoints();
}

function addLog(cls, msg) {
  const log = document.getElementById('log');
  const t = new Date().toLocaleTimeString();
  log.innerHTML += `<div class="log-${cls}">[${t}] ${msg}</div>`;
  log.scrollTop = log.scrollHeight;
  while (log.children.length > 40) log.removeChild(log.firstChild);
}

document.getElementById('speed').oninput = function() {
  speed = +this.value;
  document.getElementById('speedVal').textContent = speed;
};

async function sendChat() {
  const input = document.getElementById('chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  addLog('info', '💬 ' + text);
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text})
    });
    const d = await r.json();
    addLog(d.ok ? 'ok' : 'err', d.reply || d.error || '');
  } catch(e) {
    addLog('err', '发送失败: ' + e.message);
  }
}

async function checkStatus() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    const st = document.getElementById('status');
    if (d.connected) {
      st.className = 'status on';
      st.textContent = '✅ 已连接 · ' + d.port + ' @ ' + d.baud + 'bps';
    } else {
      st.className = 'status off';
      st.textContent = '❌ ' + (d.error || '串口未连接');
    }
  } catch(e) {
    document.getElementById('status').className = 'status off';
    document.getElementById('status').textContent = '❌ 后端未启动';
  }
}

let lastSerialCount = 0;
async function pollSerialLog() {
  try {
    const r = await fetch('/api/serial-log');
    const d = await r.json();
    if (d.lines && d.lines.length > lastSerialCount) {
      const newLines = d.lines.slice(lastSerialCount);
      const logEl = document.getElementById('serialLog');
      for (const line of newLines) {
        const cls = line.includes('ERROR') || line.includes('E (') ? 'log-err' :
                     line.includes('WARN') || line.includes('W (') ? 'log-info' : 'log-ok';
        logEl.innerHTML += `<div class="${cls}">${escapeHtml(line)}</div>`;
      }
      lastSerialCount = d.lines.length;
      logEl.scrollTop = logEl.scrollHeight;
      while (logEl.children.length > 100) logEl.removeChild(logEl.firstChild);
    }
  } catch(e) {}
}
function escapeHtml(s) { return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }

render();
setInterval(checkStatus, 2000);
checkStatus();
setInterval(pollSerialLog, 1000);
pollSerialLog();
</script>
</body>
</html>"""


# ========== HTTP API ==========

class ArmHTTPHandler(BaseHTTPRequestHandler):
    """简单的 HTTP API 处理器"""

    def log_message(self, format, *args):
        logger.debug(f"HTTP: {args[0]}")

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        return json.loads(raw.decode("utf-8"))

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = HTML_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            self._send_json({
                "connected": ser is not None and ser.is_open,
                "port": SERIAL_PORT,
                "baud": BAUD_RATE,
            })
        elif self.path == "/api/serial-log":
            with serial_log_lock:
                lines = list(serial_log_lines)
            self._send_json({"lines": lines})
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        if self.path == "/api/joints":
            try:
                body = self._read_body()
                angles = body.get("angles", [90]*6)
                speed = body.get("speed", 40)
                reply = send_joints(angles, speed)
                self._send_json({"ok": not reply.startswith("ERROR"), "angles": angles, "reply": reply})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/gripper":
            try:
                body = self._read_body()
                open_grip = body.get("open", True)
                speed = body.get("speed", 50)
                reply = send_gripper(open_grip, speed)
                self._send_json({"ok": not reply.startswith("ERROR"), "action": "open" if open_grip else "close", "reply": reply})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)

        elif self.path == "/api/chat":
            try:
                body = self._read_body()
                text = body.get("text", "")
                if not text:
                    self._send_json({"ok": False, "error": "text is empty"}, 400)
                    return
                reply = send_chat(text)
                self._send_json({"ok": not reply.startswith("ERROR"), "reply": reply})
            except Exception as e:
                self._send_json({"ok": False, "error": str(e)}, 500)

        else:
            self._send_json({"error": "Not found"}, 404)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()


def run_http_server(port):
    server = HTTPServer(("0.0.0.0", port), ArmHTTPHandler)
    logger.info(f"🦾 机械臂控制面板: http://localhost:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="机械臂关节直控面板")
    parser.add_argument("--port", type=str, default=SERIAL_PORT, help=f"串口 (默认 {SERIAL_PORT})")
    parser.add_argument("--web", type=int, default=5556, help="Web 面板端口 (默认 5556)")
    parser.add_argument("--baud", type=int, default=BAUD_RATE, help=f"波特率 (默认 {BAUD_RATE})")
    args = parser.parse_args()

    SERIAL_PORT = args.port
    BAUD_RATE = args.baud

    # 连接串口
    if not serial_connect(SERIAL_PORT):
        print(f"❌ 无法连接串口 {SERIAL_PORT}，请检查：")
        print("   1. ESP32 是否已连接 USB")
        print("   2. VSCode Monitor 是否已关闭（串口只能被一个程序占用）")
        print("   3. 端口号是否正确（设备管理器查看）")
        sys.exit(1)

    try:
        run_http_server(args.web)
    finally:
        serial_close()
