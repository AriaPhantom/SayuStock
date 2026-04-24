from PIL import Image, ImageDraw, ImageFont
import os
from pathlib import Path

def draw_glass_card(draw, x, y, w, h, radius, fill_color, border_color, border_width=2):
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width,
    )

def finalize_image(input_path, output_path):
    # Load base image
    base_img = Image.open(input_path).convert("RGBA")
    width, height = base_img.size
    
    # Create final image
    final_img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    final_img.paste(base_img, (0, 0))
    
    draw = ImageDraw.Draw(final_img)
    
    # Config
    is_up = True
    accent_color = (0, 255, 0, 255) if is_up else (255, 59, 48, 255)
    glass_bg = (255, 255, 255, 25)
    glass_border = (255, 255, 255, 50)
    
    # 1. Top HUD
    card_h = 240
    card_margin = 60
    draw_glass_card(
        draw, 
        card_margin, card_margin, 
        width - card_margin*2, card_h, 
        radius=35, 
        fill_color=glass_bg, 
        border_color=glass_border
    )
    
    # Fonts
    try:
        font_main = ImageFont.truetype("msyhbd.ttc", 80)
        font_sub = ImageFont.truetype("msyh.ttc", 45)
        font_price = ImageFont.truetype("arialbd.ttf", 110)
    except:
        font_main = ImageFont.load_default()
        font_sub = ImageFont.load_default()
        font_price = ImageFont.load_default()
        
    # Text
    draw.text((card_margin + 60, card_margin + 50), "贵州茅台 (600519)", font=font_main, fill=(255, 255, 255))
    draw.text((card_margin + 60, card_margin + 150), "沪深A | 换手 1.25% | 成交额 52.4亿", font=font_sub, fill=(180, 180, 180))
    
    price_text = "1688.50"
    change_text = "+2.45%"
    p_w = draw.textlength(price_text, font=font_price)
    c_w = draw.textlength(change_text, font=font_sub)
    
    draw.text((width - card_margin - 80 - p_w, card_margin + 40), price_text, font=font_price, fill=accent_color)
    draw.text((width - card_margin - 80 - c_w, card_margin + 160), change_text, font=font_sub, fill=accent_color)
    
    # 2. Bottom Info
    draw.text((card_margin, height - 80), "SAYUSTOCK PRO MAX | DATA SOURCE: SINA FINANCE", font=font_sub, fill=(80, 80, 80))
    
    # Save
    final_img.save(output_path)
    print(f"Final image saved to {output_path}")

if __name__ == "__main__":
    input_img = r"C:\Users\AriaP\.gemini\antigravity\brain\2fdb21ae-2b70-42b9-946a-d94a0c1660d6\promax_demo_full_chart_1777048009463.png"
    output_img = r"F:\OneDrive\文档\GitHub\SayuStock\test\promax_final_demo.png"
    finalize_image(input_img, output_img)
