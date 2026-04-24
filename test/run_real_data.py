import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Setup paths
root = Path(__file__).parent.parent

# Injecting modules BEFORE imports
def mock_module(name):
    m = MagicMock()
    sys.modules[name] = m
    return m

# Create the deep structure
mock_module('gsuid_core')
mock_module('gsuid_core.sv')
mock_module('gsuid_core.logger')
mock_module('gsuid_core.aps')
mock_module('gsuid_core.models')
mock_module('gsuid_core.bot')
mock_module('gsuid_core.utils')
mock_module('gsuid_core.utils.image')
mock_module('gsuid_core.utils.image.convert')
mock_module('gsuid_core.utils.fonts')
mock_module('gsuid_core.utils.fonts.fonts')
mock_module('gsuid_core.utils.plugins_config')
mock_module('gsuid_core.utils.plugins_config.gs_config')

# Setup functions
async def mock_convert_img(img):
    import io
    if hasattr(img, 'save'):
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    return img

sys.modules['gsuid_core.utils.image.convert'].convert_img = mock_convert_img

def mock_core_font(size):
    from PIL import ImageFont
    try: return ImageFont.truetype("msyh.ttc", size)
    except: return ImageFont.load_default()

sys.modules['gsuid_core.utils.fonts.fonts'].core_font = mock_core_font

# Add root to path
sys.path.insert(0, str(root))

from SayuStock.stock_info.draw_future import draw_future_img

async def main():
    print("Executing REAL DATA V3 Dashboard...")
    try:
        img = await draw_future_img()
        if isinstance(img, bytes):
            output_path = root / "test" / "all_weather_V3_REAL.png"
            with open(output_path, "wb") as f:
                f.write(img)
            print(f"SUCCESS! Result saved to {output_path.absolute()}")
        else: print(f"FAILED: {img}")
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
