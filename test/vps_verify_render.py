import asyncio
import os
import sys

# Add the plugin directory to path
sys.path.append('/root/gsuid_core')
sys.path.append('/root/gsuid_core/gsuid_core')
sys.path.append('/root/gsuid_core/gsuid_core/plugins/SayuStock')

from SayuStock.stock_info.draw_future import draw_future_img

async def main():
    print("Starting manual HUD draw test on VPS...")
    try:
        # We need to mock some gsuid_core parts or ensure environment is set
        # But draw_future_img mostly depends on PIL and its own utils
        img_data = await draw_future_img()
        if isinstance(img_data, bytes):
            with open('/root/vps_hud_test.png', 'wb') as f:
                f.write(img_data)
            print("Successfully rendered and saved to /root/vps_hud_test.png")
        else:
            print(f"Failed to render: {img_data}")
    except Exception as e:
        import traceback
        print(f"Error during render: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
