"""
Simple WebSocket test client for Healthcare API.
Run this to test the WebSocket connection locally.

Usage:
    python test_websocket.py
"""
import asyncio
import json
import websockets


async def test_chat():
    """Test the WebSocket chat endpoint."""
    uri = "ws://localhost:8000/ws/chat"

    print(f"Connecting to {uri}...")

    try:
        async with websockets.connect(uri) as ws:
            print("Connected!")

            # Send a test message
            message = {
                "type": "message",
                "question": "Hello, what can you help me with?",
                "user_id": "test-user",
                "session_id": "test-session-001"
            }

            print(f"\nSending: {message['question']}")
            await ws.send(json.dumps(message))

            # Receive responses
            print("\nReceiving responses:")
            print("-" * 50)

            while True:
                try:
                    response = await asyncio.wait_for(ws.recv(), timeout=30)
                    data = json.loads(response)

                    msg_type = data.get("type", "")

                    if msg_type == "status":
                        print(f"[STATUS] {data.get('message', '')}")

                    elif msg_type == "stream":
                        token = data.get("token", "")
                        if token:
                            print(token, end="", flush=True)
                        if data.get("done"):
                            print("\n[STREAM COMPLETE]")

                    elif msg_type == "complete":
                        print(f"\n[COMPLETE] Turn {data.get('turn_number')}")
                        print(f"Session: {data.get('session_id')}")
                        break

                    elif msg_type == "error":
                        print(f"[ERROR] {data.get('error')}")
                        break

                    elif msg_type == "data":
                        print(f"[DATA] {data.get('data_type')}: {json.dumps(data.get('data', {}))[:100]}...")

                    elif msg_type == "clarification":
                        print(f"[CLARIFICATION] {data.get('clarification_type')}: {data.get('message')}")

                except asyncio.TimeoutError:
                    print("[TIMEOUT] No response in 30 seconds")
                    break

    except ConnectionRefusedError:
        print("ERROR: Could not connect. Is the server running?")
        print("Start the server with: ./run_local.sh")

    except Exception as e:
        print(f"ERROR: {e}")


if __name__ == "__main__":
    asyncio.run(test_chat())
