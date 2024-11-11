import asyncio
import websockets
import mss
from PIL import Image
import io

# Set the WebSocket server port
PORT = 8080

# Function to capture, resize, and compress the screenshot
async def send_screenshot(websocket):
    with mss.mss() as sct:
        # Capture the screen
        screenshot = sct.shot(output="screenshot.jpg", mon=-1)

        # Open and process the image
        with Image.open(screenshot) as img:
            # Resize to width 640 and compress
            img = img.resize((640, int(640 * img.height / img.width)))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=80)
            compressed_img = buffer.getvalue()
        
        # Send the processed image over WebSocket
        await websocket.send(compressed_img)

# WebSocket handler
async def handler(websocket, path):
    print("Client connected")
    try:
        while True:
            await send_screenshot(websocket)
            await asyncio.sleep(0.5)  # 500 ms interval
    except websockets.exceptions.ConnectionClosed:
        print("Client disconnected")

# Start the WebSocket server
start_server = websockets.serve(handler, "localhost", PORT)

print(f"WebSocket server running on ws://localhost:{PORT}")

# Run the server
asyncio.get_event_loop().run_until_complete(start_server)
asyncio.get_event_loop().run_forever()
