import asyncio
async def test():
    try:
        import websockets
        url = "ws://127.0.0.1:8003/xiaozhi/v1/"
        print(f"测试 {url} ...")
        async with websockets.connect(url) as ws:
            print("Local OK")
        url = "ws://192.168.123.25:8003/xiaozhi/v1/"
        print(f"测试 {url} ...")
        async with websockets.connect(url) as ws:
            print("LAN OK - ESP32 should connect now")
    except Exception as e:
        print(f"FAILED: {e}")
asyncio.run(test())
