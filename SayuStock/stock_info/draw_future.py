import random
import asyncio
from typing import Any, Dict, List, Tuple, Union, Callable, Optional
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw, ImageFilter

from gsuid_core.utils.fonts.fonts import core_font as ss_font
from gsuid_core.utils.image.convert import convert_img

from .get_jp_data import get_jpy
from ..utils.image import get_footer
from ..utils.get_OKX import CRYPTO_MAP, get_all_crypto_price
from ..utils.constant import bond, whsc, i_code, commodity
from ..utils.stock.request import get_gg, get_mtdata

TEXT_PATH = Path(__file__).parent / "texture2d"
DataLike = Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]]
FUTURE_IMG_CACHE_SECONDS = 20
FUTURE_IMG_CACHE: Optional[Tuple[datetime, Any]] = None
FUTURE_IMG_LOCK: Optional[asyncio.Lock] = None

CARD_W = 196
CARD_H = 104
CARD_GAP_X = 12
CARD_GAP_Y = 12
CARD_START_X = 40
SECTION_X = 24
SECTION_W = 852
CHINA_UP_RED = (239, 68, 68)
CHINA_DOWN_GREEN = (34, 197, 94)
NEUTRAL_SLATE = (148, 163, 184)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, "", "-", "--"):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _fit_text(draw: ImageDraw.ImageDraw, text: Any, font, max_width: int) -> str:
    text = str(text or "-")
    if draw.textlength(text, font=font) <= max_width:
        return text

    ellipsis = "…"
    for length in range(len(text) - 1, 0, -1):
        candidate = f"{text[:length]}{ellipsis}"
        if draw.textlength(candidate, font=font) <= max_width:
            return candidate
    return ellipsis


def _format_price(value: Any) -> str:
    if value in (None, "", "-", "--"):
        return "-"
    number = _safe_float(value)
    if abs(number) >= 1000:
        text = f"{number:.1f}"
    elif abs(number) >= 100:
        text = f"{number:.2f}"
    elif abs(number) >= 10:
        text = f"{number:.3f}"
    else:
        text = f"{number:.4f}"
    return text.rstrip("0").rstrip(".")


def _format_compact_number(value: Any) -> str:
    number = _safe_float(value)
    if number <= 0:
        return "--"

    units = [
        (1_000_000_000_000, "T"),
        (1_000_000_000, "B"),
        (1_000_000, "M"),
        (1_000, "K"),
    ]
    for base, suffix in units:
        if number >= base:
            return f"{number / base:.2f}{suffix}".rstrip("0").rstrip(".")
    return f"{number:.0f}"


def _get_future_card_fields(item: Dict[str, Any], block_type: Optional[str]):
    if block_type == "single":
        name = item.get("f58") or item.get("f14") or "-"
        price = item.get("f43", item.get("f2", "-"))
        diff = _safe_float(item.get("f170", item.get("f3", 0)))
        amount = item.get("f48", item.get("f6", 0))
    else:
        name = item.get("f14") or item.get("f58") or "-"
        price = item.get("f2", item.get("f43", "-"))
        diff = _safe_float(item.get("f3", item.get("f170", 0)))
        amount = item.get("f6", item.get("f48", 0))

    return name, price, diff, amount, str(item.get("f12", "") or "")


def _market_color(diff: float) -> Tuple[int, int, int]:
    if diff > 0:
        return CHINA_UP_RED
    if diff < 0:
        return CHINA_DOWN_GREEN
    return NEUTRAL_SLATE


def _draw_background(img: Image.Image, draw: ImageDraw.ImageDraw, w: int, h: int) -> None:
    top = (2, 6, 23)
    bottom = (3, 7, 18)
    gradient = Image.new("RGB", (1, h))
    for y in range(h):
        ratio = y / max(h - 1, 1)
        color = tuple(int(top[i] * (1 - ratio) + bottom[i] * ratio) for i in range(3))
        gradient.putpixel((0, y), color)
    
    gradient = gradient.resize((w, h))
    img.paste(gradient, (0, 0))

    glow_scale = 4
    glow = Image.new("RGBA", (w // glow_scale, h // glow_scale), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    
    s = glow_scale
    glow_draw.ellipse([-160//s, -120//s, 340//s, 250//s], fill=(14, 165, 233, 34))
    glow_draw.ellipse([590//s, -180//s, 1080//s, 300//s], fill=(239, 68, 68, 24))
    glow_draw.ellipse([230//s, 540//s, 760//s, 1180//s], fill=(34, 197, 94, 16))
    
    glow = glow.filter(ImageFilter.GaussianBlur(58 // s))
    glow = glow.resize((w, h), resample=Image.Resampling.BILINEAR)
    img.alpha_composite(glow)

    for x in range(0, w, 60):
        draw.line([(x, 0), (x, h)], fill=(255, 255, 255, 5), width=1)
    for y in range(0, h, 60):
        draw.line([(0, y), (w, y)], fill=(255, 255, 255, 4), width=1)


def _draw_header(draw: ImageDraw.ImageDraw, w: int, now: datetime) -> None:
    draw.rounded_rectangle(
        [24, 22, w - 24, 120],
        radius=22,
        fill=(8, 13, 25, 238),
        outline=(148, 163, 184, 28),
        width=1,
    )
    draw.rectangle([24, 48, 28, 94], fill=(34, 211, 238, 220))
    draw.text((44, 48), "SAYUSTOCK TERMINAL", fill=(125, 211, 252), font=ss_font(14), anchor="lm")
    draw.text((44, 78), "All Weather Monitor", fill=(248, 250, 252), font=ss_font(34), anchor="lm")
    draw.text(
        (44, 105),
        "GLOBAL INDICES · COMMODITIES · YIELDS · FX · CRYPTO",
        fill=(100, 116, 139),
        font=ss_font(13),
        anchor="lm",
    )

    status_x = w - 44
    draw.rounded_rectangle([status_x - 190, 38, status_x, 72], radius=17, fill=(15, 23, 42, 255), outline=(34, 211, 238, 72))
    draw.ellipse([status_x - 178, 50, status_x - 168, 60], fill=(34, 197, 94))
    draw.text((status_x - 154, 55), f"LIVE · {now.strftime('%H:%M:%S')}", fill=(226, 232, 240), font=ss_font(16), anchor="lm")

    draw.rounded_rectangle([status_x - 236, 82, status_x, 108], radius=13, fill=(2, 6, 23, 210), outline=(148, 163, 184, 26))
    draw.ellipse([status_x - 220, 91, status_x - 210, 101], fill=CHINA_UP_RED)
    draw.text((status_x - 202, 96), "RED UP", fill=(203, 213, 225), font=ss_font(12), anchor="lm")
    draw.ellipse([status_x - 132, 91, status_x - 122, 101], fill=CHINA_DOWN_GREEN)
    draw.text((status_x - 114, 96), "GREEN DOWN", fill=(203, 213, 225), font=ss_font(12), anchor="lm")


def _draw_future_card(item: Dict[str, Any], block_type: Optional[str] = None) -> Image.Image:
    name, price, diff, amount, code = _get_future_card_fields(item, block_type)
    accent = _market_color(diff)
    is_up = diff > 0
    is_down = diff < 0

    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)

    intensity = min(abs(diff) / 5.0, 1.0)
    glow = (*accent, int(28 + 42 * intensity)) if diff != 0 else (148, 163, 184, 28)
    draw.rounded_rectangle([1, 1, CARD_W - 1, CARD_H - 1], radius=16, fill=glow)
    draw.rounded_rectangle(
        [3, 3, CARD_W - 3, CARD_H - 3],
        radius=15,
        fill=(9, 14, 25, 248),
        outline=(*accent, 58 if diff != 0 else 34),
        width=1,
    )
    draw.rounded_rectangle([12, 11, 48, 14], radius=2, fill=(*accent, 230))
    draw.ellipse([CARD_W - 21, 13, CARD_W - 13, 21], fill=(*accent, 180))

    f_price = ss_font(24)
    f_diff = ss_font(16)
    f_name = ss_font(18)
    f_meta = ss_font(12)

    price_text = _fit_text(draw, _format_price(price), f_price, 112)
    diff_text = f"{'+' if is_up else ''}{round(diff, 2)}%"
    if not is_up and not is_down:
        diff_text = "0.0%"

    draw.text((14, 34), price_text, fill=(*accent, 255), font=f_price, anchor="lm")
    diff_w = int(draw.textlength(diff_text, font=f_diff))
    pill_x0 = CARD_W - diff_w - 28
    draw.rounded_rectangle([pill_x0, 22, CARD_W - 12, 48], radius=13, fill=(*accent, 26), outline=(*accent, 82))
    draw.text((CARD_W - 20, 35), diff_text, fill=(*accent, 255), font=f_diff, anchor="rm")

    name_text = _fit_text(draw, str(name).split(" (")[0], f_name, CARD_W - 24)
    draw.text((14, 68), name_text, fill=(226, 232, 240), font=f_name, anchor="lm")

    amount_text = _format_compact_number(amount)
    meta_text = "LIVE" if amount_text == "--" else f"AMT {amount_text}"
    draw.text((14, 91), meta_text, fill=(100, 116, 139), font=f_meta, anchor="lm")
    if code and code != "None":
        draw.text((CARD_W - 13, 91), _fit_text(draw, code, f_meta, 70), fill=(71, 85, 105), font=f_meta, anchor="rm")

    return card


async def __get_data(result: Dict, display_name: str, stock: str):
    await asyncio.sleep(random.uniform(0.2, 1))
    data = await get_gg(stock, "single-stock")
    if isinstance(data, str) or not isinstance(data, dict):
        return data
    stock_data = data.get("data")
    if not isinstance(stock_data, dict):
        return data
    stock_data["f58"] = display_name
    result[display_name] = stock_data
    return result


async def _get_data(_d: Dict, other_call: Optional[Callable] = None):
    TASK = []
    result = {}
    if other_call:
        TASK.append(other_call(result))

    for i in _d:
        if _d[i]:
            TASK.append(__get_data(result, i, _d[i]))

    await asyncio.gather(*TASK, return_exceptions=True)
    return result


async def _get_list_data(_d: Dict):
    fs = ",".join(f"i:{code}" for code in _d.values() if code)
    if not fs:
        return {}

    resp = await get_mtdata(fs, pz=max(len(_d), 20))
    if not isinstance(resp, dict):
        return await _get_data(_d)

    data = resp.get("data")
    if not isinstance(data, dict):
        return await _get_data(_d)

    diff = data.get("diff")
    if not isinstance(diff, list):
        return await _get_data(_d)

    code_to_name = {
        str(code).split(".")[-1].upper(): name
        for name, code in _d.items()
        if code
    }
    result = {}
    for item in diff:
        if not isinstance(item, dict):
            continue

        display_name = code_to_name.get(str(item.get("f12", "")).upper())
        if display_name is None:
            display_name = item.get("f14")
        if display_name not in _d:
            continue

        item["f58"] = display_name
        item["f43"] = item.get("f2")
        item["f170"] = item.get("f3")
        item["f48"] = item.get("f6", "")
        result[display_name] = item

    return result or await _get_data(_d)


async def _get_bond_data():
    result = await _get_list_data(bond)
    await append_jpy(result)
    return result


async def append_jpy(result: Dict):
    data = await get_jpy()
    if data is None:
        return result
    result.update(data)
    return result


async def draw_future_img():
    global FUTURE_IMG_CACHE, FUTURE_IMG_LOCK

    now = datetime.now()
    if FUTURE_IMG_CACHE:
        cache_time, cache_result = FUTURE_IMG_CACHE
        if (now - cache_time).total_seconds() < FUTURE_IMG_CACHE_SECONDS:
            return cache_result

    if FUTURE_IMG_LOCK is None:
        FUTURE_IMG_LOCK = asyncio.Lock()

    async with FUTURE_IMG_LOCK:
        now = datetime.now()
        if FUTURE_IMG_CACHE:
            cache_time, cache_result = FUTURE_IMG_CACHE
            if (now - cache_time).total_seconds() < FUTURE_IMG_CACHE_SECONDS:
                return cache_result

        result = await _draw_future_img_uncached()
        if not isinstance(result, str):
            FUTURE_IMG_CACHE = (datetime.now(), result)
        return result


async def _draw_future_img_uncached():
    data1 = await get_mtdata("国际市场")
    if not isinstance(data1, dict):
        return str(data1)

    # 并发获取数据
    results = await asyncio.gather(
        _get_list_data(commodity),
        _get_bond_data(),
        _get_list_data(whsc),
        get_all_crypto_price(),
        return_exceptions=True,
    )

    def safe_data(result) -> DataLike:
        if isinstance(result, Exception):
            return None
        return result

    data2: DataLike = safe_data(results[0])
    data3: DataLike = safe_data(results[1])
    data4: DataLike = safe_data(results[2])
    data5: DataLike = safe_data(results[3])

    # --- V4 OLED Terminal Dashboard ---
    w, h = 900, 2800
    img = Image.new("RGBA", (w, h), (2, 6, 23, 255))
    draw = ImageDraw.Draw(img)

    now = datetime.now()
    _draw_background(img, draw, w, h)
    _draw_header(draw, w, now)

    data_gz: List[Dict] = data1["data"]["diff"]

    # --- 资产分组定义 ---
    commodity_groups = [
        ["伦敦金", "伦敦银", "伦敦铜"],
        ["COMEX黄金", "COMEX白银", "COMEX铜"],
        ["WTI原油", "布伦特原油", "天然气"],
        ["螺纹钢主连", "豆粕主连", "焦煤主连", "生猪主连"]
    ]
    
    bond_groups = [
        ["中国30年期国债", "中国10年期国债", "中国2年期国债"],
        ["美国30年期国债收益率", "美国10年期国债收益率", "美国2年期国债收益率"],
        ["日本30年期国债收益率", "日本10年期国债收益率", "日本2年期国债收益率"],
        ["德国10年期国债收益率", "英国10年期国债收益率"]
    ]

    curr_y = 154
    sections = [
        (data_gz, [list(i_code.keys())], "GLOBAL INDICES", (239, 68, 68), None),
        (data2, commodity_groups, "COMMODITIES", (168, 85, 247), "single"),
        (data3, bond_groups, "BONDS & YIELDS", (234, 179, 8), "single"),
        (data4, [list(whsc.keys())], "FOREX", (20, 184, 166), "single"),
        (data5, [list(CRYPTO_MAP.keys())], "CRYPTO", (249, 115, 22), "single"),
    ]

    async def paste_blocks_dynamic(data_list: DataLike, groups, y_start, title, accent_color, block_type=None):
        if not data_list:
            return 0

        items = data_list.values() if isinstance(data_list, dict) else data_list
        all_valid_groups = []
        total_count = 0
        up_count, down_count = 0, 0
        
        for group in groups:
            group_items = []
            for d in group:
                found = None
                if isinstance(data_list, dict) and d in data_list:
                    found = data_list[d]
                else:
                    for item in items:
                        name = item.get("f58") or item.get("f14") or ""
                        if str(name).split(" (")[0] == d:
                            found = item
                            break
                if found:
                    group_items.append(found)
                    total_count += 1
                    _, _, diff, _, _ = _get_future_card_fields(found, block_type)
                    if diff > 0: up_count += 1
                    elif diff < 0: down_count += 1
            if group_items:
                all_valid_groups.append(group_items)

        if not all_valid_groups:
            return 0

        # --- 核心布局计算：物理行隔离 ---
        current_row = 0
        oy = CARD_H + CARD_GAP_Y
        grid_top = y_start + 64

        for group_idx, group in enumerate(all_valid_groups):
            n = len(group)
            # 自适应列数：≤4 个资产用 n 列均匀分布，>4 个用 4 列换行
            if n <= 4:
                cols = n
                # 计算组内均匀分布：卡片在 SECTION_W 内居中
                total_w = cols * CARD_W + (cols - 1) * CARD_GAP_X
                margin = max(0, SECTION_W - total_w) // 2
                start_x = CARD_START_X + margin
                step_x = CARD_W + CARD_GAP_X
                rows_used = 1
            else:
                cols = 4
                start_x = CARD_START_X
                step_x = CARD_W + CARD_GAP_X
                rows_used = (n + cols - 1) // cols

            for idx, item in enumerate(group):
                block = _draw_future_card(item, block_type)
                if n <= 4:
                    x = start_x + idx * step_x
                    y = grid_top + oy * (current_row)
                else:
                    local_row = idx // cols
                    local_col = idx % cols
                    x = start_x + local_col * step_x
                    y = grid_top + oy * (current_row + local_row)
                
                img.paste(block, (x, y), block)
            
            # 组间加 1 行空白实现物理隔离
            current_row += rows_used + 1

        section_bottom = grid_top + current_row * oy + 10
        flat_count = total_count - up_count - down_count

        draw.rounded_rectangle([SECTION_X, y_start, SECTION_X + SECTION_W, section_bottom], radius=20, fill=(8, 13, 25, 232), outline=(148, 163, 184, 28), width=1)
        draw.rounded_rectangle([SECTION_X, y_start, SECTION_X + 7, section_bottom], radius=4, fill=(*accent_color, 180))
        draw.text((48, y_start + 24), f"{title}", fill=(241, 245, 249), font=ss_font(24), anchor="lm")
        draw.text((48, y_start + 48), f"{total_count} ASSETS · {up_count} UP · {down_count} DOWN · {flat_count} FLAT", fill=(100, 116, 139), font=ss_font(13), anchor="lm")
        draw.rounded_rectangle([w - 208, y_start + 18, w - 44, y_start + 46], radius=14, fill=(2, 6, 23, 190), outline=(*accent_color, 42))
        draw.text((w - 126, y_start + 32), f"{total_count} WATCHED", fill=(203, 213, 225), font=ss_font(13), anchor="mm")
        draw.rectangle([48, y_start + 58, w - 48, y_start + 59], fill=(255, 255, 255, 10))

        return section_bottom - y_start

    for d_list, groups, title, color, b_type in sections:
        height_used = await paste_blocks_dynamic(d_list, groups, curr_y, title, color, b_type)
        if height_used > 0:
            curr_y += height_used + 18

    footer = get_footer()
    img.paste(footer, (w//2 - footer.width//2, curr_y + 22), footer)

    final_h = min(curr_y + 112, h)
    img = img.crop((0, 0, w, final_h))
    img = Image.alpha_composite(Image.new("RGBA", img.size, (2, 6, 23, 255)), img)

    res = await convert_img(img)
    return res
