import random
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Union, Callable, Optional
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from gsuid_core.utils.fonts.fonts import core_font as ss_font
from gsuid_core.utils.image.convert import convert_img

from .draw_info import draw_block
from .get_jp_data import get_jpy
from ..utils.image import get_footer, draw_glass_card
from ..utils.get_OKX import CRYPTO_MAP, get_all_crypto_price
from ..utils.constant import bond, whsc, i_code, commodity
from ..utils.stock.request import get_gg, get_mtdata

TEXT_PATH = Path(__file__).parent / "texture2d"
DataLike = Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]]


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
    data1 = await get_mtdata("国际市场")
    if isinstance(data1, str):
        return data1

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
    draw.text((w-40, 40), f"STATUS: ACTIVE | {datetime.now().strftime('%H:%M:%S')}", (100, 100, 120), font=ss_font(18), anchor="rm")
    
    ox = 210
    oy = 125
    data_gz: List[Dict] = data1["data"]["diff"]

    async def paste_blocks(data_list: DataLike, keys, y_base, title, accent_color, block_type=None):
        if data_list is None:
            return
        
        # 极简精密标题
        draw.rectangle([40, y_base - 30, 45, y_base - 10], fill=accent_color)
        draw.text((60, y_base - 20), f"{title}", (180, 180, 190), font=ss_font(22), anchor="lm")

        index = 0
        items = data_list.values() if isinstance(data_list, dict) else data_list
        for d in keys:
            for item in items:
                name = item.get("f58", item.get("f14"))
                # 兼容性处理：如果 item 是个股数据，f58 可能包含板块信息，如 "上证指数 (指数)"
                pure_name = name.split(" (")[0]
                if pure_name != d:
                    continue
                block = await draw_block(item, block_type) if block_type else await draw_block(item)
                img.paste(
                    block,
                    (40 + ox * (index % 4), y_base + 10 + oy * (index // 4)),
                    block,
                )
                index += 1

    # 绘制各板块 (移除时间线后的新布局坐标)
    await paste_blocks(data_gz, i_code, 150, "GLOBAL INDICES", (239, 68, 68))
    await paste_blocks(data2, commodity, 750, "COMMODITIES", (168, 85, 247), "single")
    await paste_blocks(data3, bond, 1150, "BONDS & YIELDS", (234, 179, 8), "single")
    await paste_blocks(data4, whsc, 1600, "FOREX", (20, 184, 166), "single")
    await paste_blocks(data5, CRYPTO_MAP, 2050, "CRYPTO", (249, 115, 22), "single")

    # 页脚
    footer = get_footer()
    img.paste(footer, (w//2 - footer.width//2, h - 80), footer)

    res = await convert_img(img)
    return res
