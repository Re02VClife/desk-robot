#!/usr/bin/env python
"""
小智 AI 串口助手 — Web 图形界面
启动后在浏览器打开 http://localhost:5555 即可使用
"""
import serial
import json
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os

PORT = "COM6"
BAUD = 115200
WEB_PORT = 5555

HTML = r"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>小智 AI 串口助手</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Microsoft YaHei',sans-serif;background:#1a1a2e;color:#eee;padding:20px}
h1{color:#e94560;margin-bottom:15px}
#log{background:#16213e;border-radius:8px;padding:15px;height:400px;overflow-y:auto;font-family:Consolas,monospace;font-size:13px;margin-bottom:15px;white-space:pre-wrap}
#input-row{display:flex;gap:10px}
#input{flex:1;padding:12px;border-radius:8px;border:none;font-size:16px;background:#0f3460;color:#fff}
button{padding:10px 20px;border-radius:8px;border:none;cursor:pointer;font-size:14px;color:#fff}
#btn-send{background:#e94560}
#btn-refresh{background:#0f3460}
.quick-btn{background:#533483;padding:8px 16px;font-size:13px}
.status{padding:8px;border-radius:8px;margin-bottom:10px}
.connected{background:#1b5e20}
.disconnected{background:#5e1b1b}
</style>
</head>
<body>
<h1>小智 AI 串口助手</h1>
<div id="status" class="disconnected">等待连接...</div>
<div id="log"></div>
<div id="input-row">
  <input id="input" placeholder="输入文字，回车发送..." autofocus>
  <button id="btn-send" onclick="send()">发送</button>
  <button id="btn-refresh" onclick="refresh()">刷新日志</button>
</div>
<div style="margin-top:10px;display:flex;gap:8px">
  <button class="quick-btn" onclick="quickSend('你好')">你好</button>
  <button class="quick-btn" onclick="quickSend('/help')">/help</button>
  <button class="quick-btn" onclick="quickSend('')">换行</button>
</div>
<script>
var logEl=document.getElementById('log'),statusEl=document.getElementById('status');
document.getElementById('input').onkeydown=function(e){if(e.key==='Enter')send()};
function send(){
  var t=document.getElementById('input').value;
  fetch('/send',{method:'POST',body:new URLSearchParams({text:t})}).then(r=>r.json()).then(d=>{
    if(!d.ok)alert('发送失败: '+d.error);
  });
  document.getElementById('input').value='';
}
function quickSend(t){document.getElementById('input').value=t;send()}
function refresh(){
  fetch('/log').then(r=>r.json()).then(d=>{
    logEl.textContent=d.log;
    statusEl.textContent=d.connected?'已连接 '+d.port+' @ '+d.baud+' bps':'未连接';
    statusEl.className='status '+(d.connected?'connected':'disconnected');
    logEl.scrollTop=logEl.scrollHeight;
  });
}
setInterval(refresh,500);
refresh();
</script>
</body>
</html>
"""

log_lines = []
log_lock = threading.Lock()
ser = None

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-Type','text/html')
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == '/log':
            self._json_response({
                'connected': ser is not None and ser.is_open,
                'port': PORT, 'baud': BAUD,
                'log': ''.join(log_lines[-200:])
            })

    def do_POST(self):
        if self.path == '/send':
            length = int(self.headers['Content-Length'])
            body = self.rfile.read(length).decode()
            from urllib.parse import parse_qs
            params = parse_qs(body)
            text = params.get('text',[''])[0]
            try:
                if ser and ser.is_open:
                    ser.write((text+'\r\n').encode('utf-8'))
                    add_log(f'📤 发送: {text}\n')
                    self._json_response({'ok':True})
                else:
                    self._json_response({'ok':False,'error':'串口未连接'})
            except Exception as e:
                self._json_response({'ok':False,'error':str(e)})

    def _json_response(self, data):
        self.send_response(200)
        self.send_header('Content-Type','application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data,ensure_ascii=False).encode())

def add_log(msg):
    ts = time.strftime('%H:%M:%S')
    with log_lock:
        log_lines.append(f'[{ts}] {msg}')

def read_loop():
    global ser
    while True:
        try:
            if ser and ser.is_open and ser.in_waiting:
                data = ser.read(ser.in_waiting).decode(errors='replace')
                with log_lock:
                    log_lines.append(data)
            time.sleep(0.1)
        except:
            break

if __name__ == '__main__':
    try:
        ser = serial.Serial(PORT, BAUD, timeout=0.1)
        ser.dtr = False; ser.rts = False
        add_log(f'✅ 已连接 {PORT} @ {BAUD} bps\n')
        threading.Thread(target=read_loop, daemon=True).start()
    except Exception as e:
        add_log(f'❌ 连接失败: {e}，检查 COM6 是否被占用\n')
        ser = None

    print(f'\n  小智串口助手: http://localhost:{WEB_PORT}\n')
    HTTPServer(('', WEB_PORT), Handler).serve_forever()
