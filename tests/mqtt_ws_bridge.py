#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
MQTT <-> WebSocket Bridge
ESP32 (MQTT) <-> Broker (1883) <-> Bridge <-> WebSocket (8003) <-> OpenClaw Server
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import asyncio, json, time, threading, struct, socket
import websockets

MQTT_PORT = 1883
WS_URL = "ws://127.0.0.1:8003/xiaozhi/v1/"
DEVICE_ID = "3c:dc:75:59:fd:ac"
CLIENT_ID = "ee9105ef-60ae-417a-93ab-cde81d87fee0"

mqtt_clients = {}
mqtt_to_ws_queue = asyncio.Queue()

def run_mqtt_broker():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', MQTT_PORT))
    server.listen(10)
    server.settimeout(1.0)
    print(f"[MQTT Broker] Started: 0.0.0.0:{MQTT_PORT}")

    def handle_client(sock, addr):
        cid = f"{addr[0]}:{addr[1]}"
        buf = b''
        try:
            while True:
                try:
                    data = sock.recv(4096)
                except:
                    break
                if not data: break
                buf += data
                while len(buf) >= 2:
                    byte1, rem_len, pos = buf[0], 0, 1
                    msg_type = (byte1 & 0xF0) >> 4
                    while pos < len(buf):
                        b = buf[pos]; rem_len += (b & 0x7F) * (128 ** (pos-1))
                        pos += 1
                        if (b & 0x80) == 0: break
                    total_len = pos + rem_len
                    if len(buf) < total_len: break
                    packet = buf[:total_len]
                    buf = buf[total_len:]
                    if msg_type == 1:
                        sock.sendall(b'\x20\x02\x00\x00')
                        mqtt_clients[cid] = sock
                        print(f"[MQTT] {cid} connected ({len(mqtt_clients)} online)")
                    elif msg_type == 12:
                        sock.sendall(b'\xD0\x00')
                    elif msg_type == 8:
                        sock.sendall(b'\x90\x03\x00\x00\x00')
                    elif msg_type == 3:
                        qos = (byte1 & 0x06) >> 1
                        topic_len = struct.unpack('!H', packet[pos:pos+2])[0]
                        topic = packet[pos+2:pos+2+topic_len].decode(errors='replace')
                        pyld_start = pos+2+topic_len + (2 if qos > 0 else 0)
                        payload = packet[pyld_start:]
                        print(f"[MQTT] PUBLISH topic={topic} size={len(payload)}")
                        mqtt_to_ws_queue.put_nowait((topic, payload))
                        for cid2, cs in list(mqtt_clients.items()):
                            if cs is not sock:
                                try: cs.sendall(packet)
                                except: pass
        except Exception as e:
            print(f"[MQTT] {cid} error: {e}")
        finally:
            mqtt_clients.pop(cid, None)
            try: sock.close()
            except: pass

    while True:
        try:
            sock, addr = server.accept()
            threading.Thread(target=handle_client, args=(sock, addr), daemon=True).start()
        except socket.timeout:
            continue
        except Exception as e:
            print(f"[MQTT Broker] Error: {e}")

async def main():
    print("=" * 60)
    print("MQTT <-> WebSocket Bridge")
    print("=" * 60)
    threading.Thread(target=run_mqtt_broker, daemon=True).start()
    await asyncio.sleep(1)

    print(f"\n[Bridge] Connecting WebSocket: {WS_URL}")
    headers = {"Device-Id": DEVICE_ID, "Client-Id": CLIENT_ID, "Protocol-Version": "3"}
    async with websockets.connect(WS_URL, extra_headers=headers) as ws:
        print(f"[Bridge] WebSocket connected!")
        print("[Bridge] Running... Type in browser to test")
        print("=" * 60)
        while True:
            try:
                topic, msg = await asyncio.wait_for(mqtt_to_ws_queue.get(), timeout=30)
                print(f"[MQTT->WS] topic={topic}, size={len(msg)}")
                if isinstance(msg, bytes):
                    await ws.send(msg)
                else:
                    await ws.send(str(msg))
            except asyncio.TimeoutError:
                pass
            except Exception as e:
                print(f"[Bridge] Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
