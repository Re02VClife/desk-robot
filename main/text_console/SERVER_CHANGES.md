# OpenClaw 服务器端文字消息支持 — 修改方案

本文档描述如何在 [OpenClaw 后端](https://github.com/xinnan-tech/xiaozhi-esp32-server) 添加文字消息处理支持。

## 背景

ESP32 端已添加串口文字控制台功能，用户可通过 UART 输入文字并发送到服务器。消息格式：

```json
{
  "session_id": "xxx",
  "type": "text",
  "text": "用户输入的文字内容"
}
```

服务器需要接收此类型的消息，将文字直接路由到 LLM（跳过 STT/语音识别），然后返回 TTS 响应。

## 修改步骤

### 1. 消息路由 — 添加 `text` 类型处理

在 WebSocket / MQTT 消息处理函数中，添加对 `type: "text"` 的识别。

**示例代码（Python FastAPI WebSocket 处理器）：**

```python
# 在 websocket_handler 或 mqtt_handler 的消息分发处添加

elif message_type == "text":
    # 文字输入消息 — 跳过 ASR，直接进入 LLM
    text_content = data.get("text", "")
    if not text_content:
        await send_error(ws, "Empty text content")
        return
    
    logger.info(f"收到文字输入: {text_content}")
    
    # 发送 TTS 开始信号（让 ESP32 进入 Speaking 状态）
    await send_json(ws, {
        "type": "tts",
        "state": "start",
        "session_id": session_id
    })
    
    # 将文字当作已识别的用户语音，发送 STT 结果给 LLM
    await send_json(ws, {
        "type": "stt",
        "text": text_content,
        "session_id": session_id
    })
    
    # 调用 LLM 处理
    llm_response = await process_llm(
        user_text=text_content,
        session_id=session_id,
        # ... 其他上下文
    )
    
    # 发送 LLM 情感（如果有）
    if llm_response.emotion:
        await send_json(ws, {
            "type": "llm",
            "emotion": llm_response.emotion,
            "session_id": session_id
        })
    
    # 发送 TTS 文本（逐句/整体）
    for sentence in split_sentences(llm_response.text):
        await send_json(ws, {
            "type": "tts",
            "state": "sentence_start",
            "text": sentence,
            "session_id": session_id
        })
        # TTS 音频通过二进制帧发送
        audio_data = await text_to_speech(sentence)
        await ws.send_bytes(audio_data)
    
    # 发送 TTS 结束信号
    await send_json(ws, {
        "type": "tts",
        "state": "stop",
        "session_id": session_id
    })
```

### 2. 跳过 VAD/ASR 流水线

文字消息的处理路径与语音不同：
- **语音路径**: 音频帧 → VAD → ASR(STT) → LLM → TTS → 音频帧
- **文字路径**: 文字消息 → LLM → TTS → 音频帧

关键差异：
1. **不需要 STT**: 文字已经是文本，直接作为用户输入传给 LLM
2. **不需要 VAD**: 没有音频流需要断句
3. **保持 TTS 输出**: 回复仍走 TTS 流程（生成语音 + 同步发送文字）

### 3. 会话上下文保持

文字消息应保持与语音消息相同的会话上下文：

```python
# 文字消息应使用相同的对话历史
conversation_history = get_session_history(session_id)
conversation_history.append({"role": "user", "content": text_content})

llm_response = await llm.chat(
    messages=conversation_history,
    tools=get_mcp_tools(session_id),  # MCP 工具照常可用
    # ...
)

conversation_history.append({"role": "assistant", "content": llm_response.text})
```

### 4. 并发处理注意事项

- 如果 ESP32 在文字消息处理期间又发送了新的文字消息，应 `abort` 当前 LLM 请求并开始新的
- 如果 ESP32 在播放 TTS 期间发送文字消息，应先停止当前 TTS 音频流

## 快速测试

1. 编译烧录 ESP32 固件
2. 打开串口监视器
3. 看到 `文字控制台已启动` 提示
4. 输入 `你好，今天天气怎么样？` 按回车
5. 观察：
   - 屏幕显示用户消息（"user" 角色）
   - 服务器返回 TTS 音频（喇叭播放）
   - 屏幕显示助手消息（"assistant" 角色）

## MQTT 模式下的特殊处理

如果使用 MQTT 协议，文字消息和 TTS 消息都通过 MQTT publish 发送到 `publish_topic`。服务器端需要在 MQTT 消息回调中做相同的 type 分发处理。

MQTT 模式下的 UDP 音频通道不受影响，TTS 音频仍通过 UDP 加密传输，只有 JSON 控制消息走 MQTT。
