"""WebSocket MCP 控臂测试 — 直连 ESP32 调用 robot.arm.gripper"""
import asyncio, json, sys

WS_URL = "ws://192.168.123.25:8003/xiaozhi/v1/"
DEVICE_ID = "ee9105ef-60ae-417a-93ab-cde81d87fee0"

async def main():
    import websockets

    print(f"🔌 连接 {WS_URL} ...")
    async with websockets.connect(WS_URL, extra_headers={
        "device-id": DEVICE_ID,
        "client-id": DEVICE_ID,
        "protocol-version": "1",
    }) as ws:
        # 发 hello
        hello = {
            "type": "hello",
            "version": 1,
            "features": {"mcp": True},
            "transport": "websocket",
            "audio_params": {"format": "opus", "sample_rate": 16000, "channels": 1, "frame_duration": 60}
        }
        await ws.send(json.dumps(hello))

        # 等 MCP 初始化完成
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
            t = msg.get("type", "")
            print(f"  ← {t}: {json.dumps(msg, ensure_ascii=False)[:200]}")
            if t == "mcp":
                payload = msg.get("payload", {})
                if payload.get("id") == 2:  # tools/list 响应
                    print("\n✅ MCP 初始化完成，工具列表已接收\n")
                    break

        # 调一次 get_status
        session_id = "test_arm_001"
        print("📤 发送 robot.arm.get_status ...")
        await ws.send(json.dumps({
            "session_id": session_id,
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/call",
                "params": {
                    "name": "robot.arm.get_status",
                    "arguments": {}
                }
            }
        }))

        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(resp)
            print(f"  ← get_status 返回: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
        except asyncio.TimeoutError:
            print("  ⚠️ 超时")

        # 调一次 gripper open
        print("\n📤 发送 robot.arm.gripper (open=true) ...")
        await ws.send(json.dumps({
            "session_id": session_id,
            "type": "mcp",
            "payload": {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "tools/call",
                "params": {
                    "name": "robot.arm.gripper",
                    "arguments": {"open": True, "speed": 30}
                }
            }
        }))

        try:
            resp = await asyncio.wait_for(ws.recv(), timeout=5)
            data = json.loads(resp)
            print(f"  ← gripper 返回: {json.dumps(data, ensure_ascii=False, indent=2)[:300]}")
        except asyncio.TimeoutError:
            print("  ⚠️ 超时")

    print("\n✅ 完成")

asyncio.run(main())
