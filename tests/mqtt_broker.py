#!/usr/bin/env python
"""
简易 MQTT Broker — 供 ESP32 和 OpenClaw 本地通信
监听 1883 端口，中转消息
"""
import socketserver
import threading
import struct
import time

HOST = '0.0.0.0'
PORT = 1883

clients = []
clients_lock = threading.Lock()

def handle_mqtt(sock, addr):
    """极简 MQTT 3.1.1 broker — 仅处理 CONNECT/PUBLISH/SUBSCRIBE/PING"""
    buffer = b''
    client_id = f'{addr[0]}:{addr[1]}'
    try:
        while True:
            data = sock.recv(4096)
            if not data:
                break
            buffer += data

            while len(buffer) >= 2:
                # MQTT fixed header
                byte1 = buffer[0]
                msg_type = (byte1 & 0xF0) >> 4
                remaining = 0
                multiplier = 1
                pos = 1
                while pos < len(buffer):
                    b = buffer[pos]
                    remaining += (b & 0x7F) * multiplier
                    multiplier *= 128
                    pos += 1
                    if (b & 0x80) == 0:
                        break
                total = pos + remaining

                if len(buffer) < total:
                    break  # need more data

                packet = buffer[:total]
                buffer = buffer[total:]

                if msg_type == 1:  # CONNECT
                    sock.sendall(b'\x20\x02\x00\x00')  # CONNACK
                    with clients_lock:
                        clients.append(sock)
                    print(f'{client_id} CONNECTED (total {len(clients)})')
                elif msg_type == 12:  # PINGREQ
                    sock.sendall(b'\xD0\x00')  # PINGRESP
                elif msg_type == 3:  # PUBLISH
                    # relay to all other clients
                    topic_len = struct.unpack('!H', packet[pos:pos+2])[0]
                    topic = packet[pos+2:pos+2+topic_len].decode(errors='replace')
                    payload = packet[pos+2+topic_len:]
                    print(f'{client_id} PUBLISH -> {topic} ({len(payload)} bytes)')
                    with clients_lock:
                        for c in clients:
                            if c is not sock:
                                try:
                                    c.sendall(packet)
                                except:
                                    pass
                elif msg_type == 8:  # SUBSCRIBE
                    sock.sendall(b'\x90\x03\x00\x00\x00')  # SUBACK
    except Exception as e:
        print(f'{client_id} error: {e}')
    finally:
        with clients_lock:
            if sock in clients:
                clients.remove(sock)
        try:
            sock.close()
        except:
            pass
        print(f'{client_id} disconnected')


class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


if __name__ == '__main__':
    server = ThreadedTCPServer((HOST, PORT), lambda *a: None)
    server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f'MQTT Broker 启动: {HOST}:{PORT}')
    while True:
        sock, addr = server.socket.accept()
        threading.Thread(target=handle_mqtt, args=(sock, addr), daemon=True).start()
