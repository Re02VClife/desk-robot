"""
USB 摄像头预览 — VS Code + 浏览器双模式
=========================================
用法:
  python tests/camera_test.py              → OpenCV 窗口预览（按 Q 退出）
  python tests/camera_test.py --web 8080   → 浏览器 MJPEG 流（VS Code Simple Browser 打开）
"""
import sys
import time
import http.server
import threading

try:
    import cv2
except ImportError:
    print("请先安装: pip install opencv-python")
    sys.exit(1)


def show_window():
    """OpenCV 窗口预览"""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("未检测到摄像头!")
        for i in range(4):
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                print(f"找到摄像头: 设备{i}")
                break
        else:
            print("所有设备均失败，请检查USB连接")
            return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头: {w}x{h}  按 Q 退出")

    cv2.namedWindow("USB Camera", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("USB Camera", 640, 480)

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        # 叠加FPS
        fps = cap.get(cv2.CAP_PROP_FPS)
        cv2.putText(frame, f"FPS: {fps:.0f}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.imshow("USB Camera", frame)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()


class MJPEGHandler(http.server.BaseHTTPRequestHandler):
    """简单的 MJPEG 流服务器"""
    cap = None

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            html = """<!DOCTYPE html><html><head><title>USB Camera</title>
<style>body{margin:0;background:#000;display:flex;justify-content:center;align-items:center;height:100vh}
img{max-width:100vw;max-height:100vh}</style></head>
<body><img src="/stream"><script>// 断线自动重连
const img=document.querySelector('img');img.onerror=()=>{setTimeout(()=>img.src='/stream?'+Date.now(),1000)}</script></body></html>"""
            self.wfile.write(html.encode())
        elif self.path == '/stream':
            self.send_response(200)
            self.send_header('Content-type', 'multipart/x-mixed-replace; boundary=frame')
            self.end_headers()
            try:
                while True:
                    ret, frame = self.cap.read()
                    if not ret:
                        break
                    _, jpeg = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
                    self.wfile.write(b'--frame\r\n')
                    self.wfile.write(b'Content-Type: image/jpeg\r\n\r\n')
                    self.wfile.write(jpeg.tobytes())
                    self.wfile.write(b'\r\n')
                    time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass


def serve_web(port=8080):
    """启动 MJPEG 流服务器"""
    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
    if not cap.isOpened():
        print("未检测到摄像头!")
        return

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"摄像头 {w}x{h}  →  http://localhost:{port}")
    print("在 VS Code 中: Ctrl+Shift+P → Simple Browser → 输入上面的URL")
    print("按 Ctrl+C 停止")

    MJPEGHandler.cap = cap
    server = http.server.HTTPServer(('0.0.0.0', port), MJPEGHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止")
    finally:
        cap.release()
        server.server_close()


if __name__ == '__main__':
    if '--web' in sys.argv:
        idx = sys.argv.index('--web')
        port = int(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else 8080
        serve_web(port)
    else:
        show_window()
