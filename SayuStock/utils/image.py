import asyncio
from typing import Union, Optional
from pathlib import Path
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont, ImageFilter
from playwright.async_api import async_playwright

from gsuid_core.logger import logger
import sys

async def launch_browser(p, **kwargs):
    try:
        return await p.chromium.launch(**kwargs)
    except Exception as e:
        logger.warning(f"[SayuStock] Chromium launch failed: {e}. Trying playwright install...")
        try:
            install_args = [
                sys.executable,
                "-m",
                "playwright",
                "install",
                "chromium",
            ]
            proc = await asyncio.create_subprocess_exec(*install_args)
            await proc.wait()
            return await p.chromium.launch(**kwargs)
        except Exception as err:
            logger.error(f"[SayuStock] Chromium install/relaunch failed: {err}")
            raise err


from gsuid_core.utils.image.convert import convert_img

from ..stock_config.stock_config import STOCK_CONFIG

TEXT_PATH = Path(__file__).parent / "texture2d"

view_port: int = STOCK_CONFIG.get_config("mapcloud_viewport").data
scale: int = STOCK_CONFIG.get_config("mapcloud_scale").data


def get_footer():
    return Image.open(TEXT_PATH / "footer.png")


def get_ICON():
    return Image.open(Path(__file__).parents[2] / "ICON.png")


async def render_image_by_pw(
    html_path: Path, w: int, h: int, _scale: int, return_bytes: bool = False
) -> Union[str, bytes]:
    if isinstance(html_path, str):
        return html_path

    async with async_playwright() as p:
        browser = await launch_browser(p, headless=True)
        if w == 0 or h == 0:
            w = view_port
            h = view_port
        if _scale == 0:
            _scale = scale

        context = await browser.new_context(
            viewport={
                "width": w,
                "height": h,
            },  # type: ignore
            device_scale_factor=_scale,
        )
        page = await context.new_page()
        await page.goto(html_path.absolute().as_uri())
        await page.wait_for_selector(".plot-container")
        png_bytes = await page.screenshot(type="png")
        await browser.close()
        if return_bytes:
            return png_bytes
        return await convert_img(png_bytes)


def draw_glass_card(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    radius: int,
    fill_color: tuple,
    border_color: tuple,
    border_width: int = 1,
):
    """绘制带圆角和边框的玻璃质感卡片背景"""
    # 绘制背景
    draw.rounded_rectangle(
        [x, y, x + w, y + h],
        radius=radius,
        fill=fill_color,
        outline=border_color,
        width=border_width,
    )


async def render_promax_image(
    base_img_bytes: bytes,
    title: str,
    subtitle: str,
    price: str,
    change_pct: str,
    is_up: bool,
    footer_info: str = "",
) -> bytes:
    """
    Pro Max 渲染器：将 Plotly 生成的基础图表与 PIL 绘制的高级 HUD 外壳合并。
    """
    base_img = Image.open(BytesIO(base_img_bytes)).convert("RGBA")
    width, height = base_img.size

    # 创建一个新的画布，稍微大一点以容纳 HUD 边距
    final_img = Image.new("RGBA", (width, height), (0, 0, 0, 255))
    final_img.paste(base_img, (0, 0))

    draw = ImageDraw.Draw(final_img)

    # 颜色配置 (OLED Pro Max) - 适配中国股市：红涨绿跌
    accent_color = (255, 59, 48, 255) if is_up else (34, 197, 94, 255)
    border_color = (255, 59, 48, 120) if is_up else (34, 197, 94, 120)
    glass_bg = (30, 30, 35, 255)  # 纯暗色背景，彻底解决透明通道引起的对比度问题

    # 1. 绘制顶端 HUD 卡片
    card_h = 180
    card_margin = 40

    # 绘制卡片
    draw_glass_card(
        draw,
        card_margin,
        card_margin,
        width - card_margin * 2,
        card_h,
        radius=25,
        fill_color=glass_bg,
        border_color=border_color,
        border_width=2,
    )

    # 加载字体 (尝试从 gsuid_core 载入 MiSans，本地 Windows 则兜底使用微软雅黑)
    try:
        from gsuid_core.utils.fonts.fonts import core_font
        font_main = core_font(60)
        font_sub = core_font(35)
        font_price = core_font(80)
    except ImportError:
        try:
            font_main = ImageFont.truetype("msyhbd.ttc", 60)
            font_sub = ImageFont.truetype("msyh.ttc", 35)
            font_price = ImageFont.truetype("arialbd.ttf", 80)
        except Exception:
            font_main = ImageFont.load_default()
            font_sub = ImageFont.load_default()
            font_price = ImageFont.load_default()

    # 绘制标题
    draw.text((card_margin + 40, card_margin + 35), title, font=font_main, fill=(255, 255, 255))
    draw.text((card_margin + 40, card_margin + 105), subtitle, font=font_sub, fill=(200, 200, 200))

    # 绘制价格 (靠右)
    price_text = price
    change_text = f"{'+' if is_up else ''}{change_pct}%"

    # 计算价格文本宽度以进行右对齐
    p_w = draw.textlength(price_text, font=font_price)
    c_w = draw.textlength(change_text, font=font_sub)

    draw.text((width - card_margin - 40 - p_w, card_margin + 25), price_text, font=font_price, fill=accent_color)
    draw.text((width - card_margin - 40 - c_w, card_margin + 115), change_text, font=font_sub, fill=accent_color)

    # 2. 绘制底部装饰
    footer_y = height - 60
    draw.text((card_margin, footer_y), footer_info, font=font_sub, fill=(100, 100, 100))

    # 输出
    img_byte_arr = BytesIO()
    final_img.save(img_byte_arr, format="PNG")
    return img_byte_arr.getvalue()
