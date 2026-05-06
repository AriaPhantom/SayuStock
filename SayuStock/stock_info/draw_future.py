import random
import asyncio
from typing import Any, Dict, List, Tuple, Union, Callable, Optional
from pathlib import Path
from datetime import datetime

from PIL import Image, ImageDraw

from gsuid_core.utils.fonts.fonts import core_font as ss_font
from gsuid_core.utils.image.convert import convert_img

from .draw_info import draw_block
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


async def __get_data(result: Dict, stock: str):
    await asyncio.sleep(random.uniform(0.2, 1))
    data = await get_gg(stock, "single-stock")
    if isinstance(data, str):
        return data
    pure_name = data["data"]["f58"].split(" (")[0]
    data["data"]["f58"] = pure_name
    result[pure_name] = data["data"]
    return result


async def _get_data(_d: Dict, other_call: Optional[Callable] = None):
    TASK = []
    result = {}
    if other_call:
        TASK.append(other_call(result))

    for i in _d:
        if _d[i]:
            TASK.append(__get_data(result, _d[i]))

    await asyncio.gather(*TASK)
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
        _get_data(commodity),
        _get_data(bond, append_jpy),
        _get_data(whsc),
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

    # --- V3 Data-First Background ---
    w, h = 900, 2800
    img = Image.new("RGBA", (w, h), (7, 8, 12, 255))
    draw = ImageDraw.Draw(img)

    # 1. 紧凑型顶部状态 (移除时间线)
    draw.rectangle([0, 0, w, 80], fill=(20, 21, 26, 255))
    draw.text((40, 40), "// GLOBAL MARKET REAL-TIME MONITOR", (0, 255, 255, 200), font=ss_font(28), anchor="lm")
    draw.text(
        (w - 40, 40),
        f"STATUS: ACTIVE | {datetime.now().strftime('%H:%M:%S')}",
        (100, 100, 120),
        font=ss_font(18),
        anchor="rm",
    )

    ox = 210
    oy = 125
    data_gz: List[Dict] = data1["data"]["diff"]


    # 绘制各板块 (流式布局，避免空白)
    curr_y = 150
    sections = [
        (data_gz, i_code, "GLOBAL INDICES", (239, 68, 68), None),
        (data2, commodity, "COMMODITIES", (168, 85, 247), "single"),
        (data3, bond, "BONDS & YIELDS", (234, 179, 8), "single"),
        (data4, whsc, "FOREX", (20, 184, 166), "single"),
        (data5, CRYPTO_MAP, "CRYPTO", (249, 115, 22), "single"),
    ]

    async def paste_blocks_dynamic(data_list: DataLike, keys, y_start, title, accent_color, block_type=None):
        if not data_list:
            return 0

        # 预检查是否有实际内容
        items = data_list.values() if isinstance(data_list, dict) else data_list
        valid_items = []
        for d in keys:
            for item in items:
                name = item.get("f58", item.get("f14"))
                pure_name = name.split(" (")[0]
                if pure_name == d:
                    valid_items.append(item)
                    break

        if not valid_items:
            return 0

        # 绘制标题
        draw.rectangle([40, y_start - 30, 45, y_start - 10], fill=accent_color)
        draw.text((60, y_start - 20), f"{title}", (180, 180, 190), font=ss_font(22), anchor="lm")

        index = 0
        for item in valid_items:
            block = await draw_block(item, block_type) if block_type else await draw_block(item)
            img.paste(
                block,
                (40 + ox * (index % 4), y_start + 10 + oy * (index // 4)),
                block,
            )
            index += 1

        # 返回占用的高度
        rows = (index + 3) // 4
        return rows * oy + 60

    for d_list, keys, title, color, b_type in sections:
        height_used = await paste_blocks_dynamic(d_list, keys, curr_y, title, color, b_type)
        if height_used > 0:
            curr_y += height_used + 40 # 加上间距

    # 页脚 (动态位置)
    footer = get_footer()
    img.paste(footer, (w//2 - footer.width//2, curr_y + 20), footer)

    # 裁剪图片，去除底部多余空白
    final_h = min(curr_y + 120, h)
    img = img.crop((0, 0, w, final_h))

    res = await convert_img(img)
    return res
