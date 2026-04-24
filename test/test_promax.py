import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to sys.path to allow imports from SayuStock
sys.path.insert(0, str(Path(__file__).parent))

from SayuStock.stock_cloudmap.get_cloudmap import render_image

async def main():
    print("Starting Pro Max rendering test...")
    # Test with Kweichow Moutai (600519)
    # Using 'single-stock' which corresponds to the intraday chart
    img = await render_image("600519", "single-stock")
    
    if isinstance(img, bytes):
        output_path = Path("promax_test_output.png")
        with open(output_path, "wb") as f:
            f.write(img)
        print(f"Success! Image saved to {output_path.absolute()}")
    else:
        print(f"Failed to generate image: {img}")

if __name__ == "__main__":
    asyncio.run(main())
