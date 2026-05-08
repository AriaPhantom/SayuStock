import asyncio
import sys
import os

# 添加所有可能的路径
sys.path.insert(0, "/root/gsuid_core")
sys.path.insert(0, "/root/gsuid_core/gsuid_core")

# 尝试不同的导入方式
try:
    from gsuid_core.plugins.SayuStock.SayuStock.stock_info.draw_future import draw_future_img
    print("Import method 1 success")
except Exception as e:
    print(f"Import method 1 failed: {e}")
    try:
        from plugins.SayuStock.SayuStock.stock_info.draw_future import draw_future_img
        print("Import method 2 success")
    except Exception as e2:
        print(f"Import method 2 failed: {e2}")
        sys.exit(1)

async def main():
    print("Starting rendering test on VPS...")
    try:
        img_data = await draw_future_img()
        if isinstance(img_data, str):
            print(f"Error during rendering: {img_data}")
            return
            
        out_path = "/tmp/vps_layout_test.png"
        with open(out_path, "wb") as f:
            f.write(img_data)
        
        # 验证文件
        size = os.path.getsize(out_path)
        print(f"Success! Image saved to {out_path}, size: {size} bytes")
        
        # 检查图片尺寸
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(img_data))
        print(f"Image size: {img.size}, mode: {img.mode}")
        
    except Exception as e:
        import traceback
        print(f"Exception: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
