import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from SayuStock.stock_info.draw_future import draw_future_img

async def main():
    print("Generating All-Weather Pro Max Dashboard...")
    try:
        img = await draw_future_img()
        if isinstance(img, bytes):
            output_path = Path("test/all_weather_promax.png")
            with open(output_path, "wb") as f:
                f.write(img)
            print(f"Success! Dashboard saved to {output_path.absolute()}")
        else:
            print(f"Failed to generate dashboard: {img}")
    except Exception as e:
        print(f"Error during generation: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
