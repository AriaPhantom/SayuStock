from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import os
from pathlib import Path

def number_to_chinese(num):
    if num >= 100000000:
        return f"{num/100000000:.2f}亿"
    elif num >= 10000:
        return f"{num/10000:.2f}万"
    return str(num)

def draw_mock_block(name, price, diff, code="600519", amount=5240000000):
    w, h = 210, 115
    img = Image.new("RGBA", (w, h))
    draw = ImageDraw.Draw(img)
    
    is_up = diff >= 0
    intensity = min(abs(diff) / 5.0, 1.0)
    if is_up:
        base_color = (34, 197, 94)
        glow_color = (34, 197, 94, int(40 * intensity))
    else:
        base_color = (239, 68, 68)
        glow_color = (239, 68, 68, int(40 * intensity))
        
    accent_color = (*base_color, 255)
    glass_bg = (15, 16, 22, 240)
    
    draw.rounded_rectangle([2, 2, w-2, h-2], radius=4, fill=glow_color)
    draw.rounded_rectangle([5, 5, w-5, h-5], radius=4, fill=glass_bg, outline=(255,255,255,20), width=1)
    draw.rectangle([5, 5, w-5, 8], fill=accent_color)
    
    try:
        f_name = ImageFont.truetype("msyh.ttc", 20)
        f_price = ImageFont.truetype("arialbd.ttf", 24)
        f_diff = ImageFont.truetype("arial.ttf", 18)
        f_meta = ImageFont.truetype("arial.ttf", 14)
    except:
        f_name = f_price = f_diff = f_meta = ImageFont.load_default()
        
    draw.text((w//2, 32), str(price), accent_color, font=f_price, anchor="mm")
    draw.text((w//2, 58), f"{'+' if is_up else ''}{diff}%", accent_color, font=f_diff, anchor="mm")
    draw.text((w//2, 78), f"额 {number_to_chinese(amount)}", (120, 120, 130), font=f_meta, anchor="mm")
    draw.text((w//2, 98), name, (200, 200, 200), font=f_name, anchor="mm")
    draw.text((w-10, h-15), code, (80, 80, 80), font=f_meta, anchor="rm")
    
    return img

def generate_demo():
    w, h = 900, 1200
    img = Image.new("RGBA", (w, h), (7, 8, 12, 255))
    draw = ImageDraw.Draw(img)
    
    # Compact Header
    draw.rectangle([0, 0, w, 80], fill=(20, 21, 26, 255))
    try:
        f_head = ImageFont.truetype("msyhbd.ttc", 24)
        f_status = ImageFont.truetype("arial.ttf", 16)
    except:
        f_head = f_status = ImageFont.load_default()
        
    draw.text((40, 40), "// GLOBAL MARKET REAL-TIME MONITOR", (0, 255, 255, 200), font=f_head, anchor="lm")
    draw.text((w-40, 40), f"STATUS: ACTIVE | {datetime.now().strftime('%H:%M:%S')}", (100, 100, 120), font=f_status, anchor="rm")
    
    sections = [
        ("GLOBAL INDICES", (239, 68, 68), [
            ("Nasdaq", 16500.5, 1.25, "IXIC", 8240000000), 
            ("S&P 500", 5200.2, 0.82, "SPX", 12500000000), 
            ("Nikkei 225", 39012.5, -0.45, "N225", 4500000000), 
            ("DAX", 18023.1, 0.31, "GDAXI", 3200000000)
        ]),
        ("COMMODITIES", (168, 85, 247), [
            ("Gold", 2350.5, 1.45, "XAU", 1540000000), 
            ("Silver", 28.52, 2.12, "XAG", 450000000), 
            ("Crude Oil", 85.24, -1.15, "CL", 2800000000), 
            ("Copper", 4.52, 0.68, "HG", 320000000)
        ]),
    ]
    
    y_base = 150
    for title, color, items in sections:
        draw.rectangle([40, y_base - 30, 45, y_base - 10], fill=color)
        draw.text((60, y_base - 20), title, (180, 180, 190), font=f_head, anchor="lm")
        
        for i, (name, price, diff, code, amount) in enumerate(items):
            block = draw_mock_block(name, price, diff, code, amount)
            img.paste(block, (40 + 210 * (i % 4), y_base + 10 + 125 * (i // 4)), block)
        
        y_base += 300
        
    output_path = Path("test/all_weather_demo_V3.png")
    img.save(output_path)
    print(f"Final Demo saved to {output_path}")

if __name__ == "__main__":
    generate_demo()
