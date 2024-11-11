# from tools import ToolResult

# import asyncio

# from tools.computer import ComputerTool

# computer_tool = ComputerTool()

# async def simulate_keyboard_events():
#     result_key = await computer_tool(
#         action="key",
#         text="command+c"
#     )
#     print(result_key.output or result_key.error)

# asyncio.run(simulate_keyboard_events())


from time import sleep
import pyautogui

# Simulate Command + C (Copy)
sleep(2)
print("Pressing Command + C")
pyautogui.hotkey('command', 'c')
