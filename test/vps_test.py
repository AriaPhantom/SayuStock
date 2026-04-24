import asyncio
import os
import sys
from pathlib import Path

# Add project paths to sys.path
sys.path.insert(0, "/root/gsuid_core")
sys.path.insert(0, "/root/gsuid_core/gsuid_core")
sys.path.insert(0, "/root/gsuid_core/gsuid_core/plugins/SayuStock")

os.chdir("/root/gsuid_core")

from SayuStock.stock_info.draw_future import draw_future_img

async def main():
    print("Running All-Weather Pro Max V3 Test on VPS (Multi-Path Fix)...")
    try:
        img = await draw_future_img()
        if isinstance(img, bytes):
            with open("/root/all_weather_VPS_TEST.png", "wb") as f:
                f.write(img)
            print("SUCCESS: Image generated at /root/all_weather_VPS_TEST.png")
        else:
            print(f"FAILED: {img}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
