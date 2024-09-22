import asyncio
import websockets
import gradio as gr
import threading
import queue
import time

# 使用线程安全队列
websocket_messages = queue.Queue()

async def listen_to_websocket(query):
    uri = "ws://127.0.0.1:8765"
    print(f"Connecting to WebSocket server at {uri}")
    try:
        async with websockets.connect(uri) as websocket:
            print(f"Connected to WebSocket server, sending query: {query}")
            await websocket.send(query)
            
            async def send_heartbeat():
                while True:
                    await asyncio.sleep(1)  # 每10秒发送一次心跳
                    await websocket.send("heartbeat")
                    print("Sent heartbeat")

            # 启动心跳任务
            asyncio.create_task(send_heartbeat())

            while True:
                print("Waiting for message from WebSocket server...")
                try:
                    message = await websocket.recv()
                    if message != "heartbeat":
                        websocket_messages.put(message)
                    print(f"Received message from WebSocket server: {message}")
                    await asyncio.sleep(0.1)  # Small sleep to simulate processing
                except websockets.ConnectionClosed:
                    print("WebSocket connection closed")
                    break
                except Exception as e:
                    print(f"Exception in websocket connection: {e}")
                    break  # Exit the loop if an exception occurs
    except Exception as e:
        print(f"Exception when trying to connect to WebSocket server: {e}")

async def start_listener(query):
    await listen_to_websocket(query)

def websocket_listener(query):
    asyncio.run(start_listener(query))

def chat(message, history=""):
    print(f"Received user message: {message}")
    # 启动一个新线程来监听 WebSocket
    thread = threading.Thread(target=websocket_listener, args=(message,))
    thread.start()
    
    full_response = ""
    while True:
        if not thread.is_alive():
            print("WebSocket listener thread has stopped unexpectedly.")
            break
        try:
            # 尝试从队列中获取消息，设置一个超时时间以避免阻塞
            response_message = websocket_messages.get(timeout=1)
            print(f"Yielding response message: {response_message}")
            full_response += response_message
            yield full_response
        except queue.Empty:
            print("No new messages, waiting...")
            time.sleep(1)  # Small sleep to avoid busy waiting
        except Exception as e:
            print(f"Exception while processing messages: {e}")
            break

# 启动Gradio应用
with gr.Blocks() as demo:
    gr.Markdown("# Itinerary planning chatbot")
    with gr.Column():
        query_input = gr.Textbox(lines=2, label="Query", placeholder="Please enter your itinerary requirements here")
        send_btn = gr.Button(value="Send")
        output_area = gr.TextArea(label="Response", lines=10)
        examples=gr.Examples(["计划一个3天的从洛杉矶到旧金山的旅行。",
                  "请提供一个从纽约到洛杉矶的旅行计划。",
                  "你能给我规划在加利福尼亚州的旅行吗？预算10000以内"],query_input)
    send_btn.click(chat, inputs=[query_input], outputs=[output_area])
demo.launch()
