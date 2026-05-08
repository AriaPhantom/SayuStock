import random
import asyncio
from typing import Any, Dict, List, Tuple, Union, Optional
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

DataLike = Optional[Union[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]]
FUTURE_IMG_CACHE_SECONDS = 20
FUTURE_IMG_CACHE: Optional[Tuple[datetime, Any]] = None
FUTURE_IMG_LOCK: Optional[asyncio.Lock] = None

CARD_W, CARD_H = 196, 104
GAP_X, GAP_Y = 12, 12
SECTION_W = 852
SECTION_X = 24
CARD_START_X = 40
UP_COLOR = (239, 68, 68)
DOWN_COLOR = (34, 197, 94)
MID_COLOR = (148, 163, 184)

def _safe_float(v, d=0.0):
    try: return float(v) if v not in (None, "", "-", "--") else d
    except: return d

def _format_price(v):
    n = _safe_float(v)
    if n == 0: return "-"
    if abs(n) >= 1000: return f"{n:.1f}"
    if abs(n) >= 100: return f"{n:.2f}"
    return f"{n:.3f}".rstrip("0").rstrip(".")

def _format_amt(v):
    n = _safe_float(v)
    if n <= 0: return "0"
    for b, s in [(1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if n >= b: return f"{n/b:.2f}{s}".rstrip("0").rstrip(".")
    return f"{n:.0f}"

def _draw_card(item: Dict) -> Image.Image:
    name = item.get("f58") or item.get("f14") or "-"
    price = item.get("f2") or item.get("f43") or "-"
    diff = _safe_float(item.get("f3") or item.get("f170") or 0)
    amt = item.get("f6") or item.get("f48") or 0
    code = str(item.get("f12", "") or "")

    color = UP_COLOR if diff > 0 else (DOWN_COLOR if diff < 0 else MID_COLOR)
    card = Image.new("RGBA", (CARD_W, CARD_H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    
    alpha = int(28 + 42 * min(abs(diff)/5.0, 1.0)) if diff != 0 else 28
    draw.rounded_rectangle([0, 0, CARD_W, CARD_H], radius=16, fill=(*color, alpha))
    draw.rounded_rectangle([2, 2, CARD_W-2, CARD_H-2], radius=14, fill=(9, 14, 25, 250), outline=(*color, 60), width=1)
    
    draw.text((14, 32), _format_price(price), fill=color, font=ss_font(24), anchor="lm")
    diff_str = f"{'+' if diff > 0 else ''}{diff:.2f}%"
    draw.rounded_rectangle([CARD_W-85, 20, CARD_W-12, 46], radius=12, fill=(*color, 30), outline=(*color, 80))
    draw.text((CARD_W-18, 33), diff_str, fill=color, font=ss_font(16), anchor="rm")
    
    draw.text((14, 66), str(name).split(" (")[0][:10], fill=(230, 235, 245), font=ss_font(18), anchor="lm")
    amt_str = _format_amt(amt)
    draw.text((14, 90), f"AMT {amt_str}" if amt_str != "0" else "LIVE", fill=(100, 120, 140), font=ss_font(12), anchor="lm")
    if code: draw.text((CARD_W-14, 90), code, fill=(70, 85, 100), font=ss_font(11), anchor="rm")
    return card

async def _get_list_data(symbols_dict: Dict):
    codes = ",".join(f"i:{c}" for c in symbols_dict.values() if c)
    if not codes: return {}
    resp = await get_mtdata(codes, pz=50)
    if not isinstance(resp, dict) or "data" not in resp: return {}
    diff_list = resp["data"].get("diff", [])
    
    mapping = {str(c).split(".")[-1].upper(): n for n, c in symbols_dict.items()}
    result = {}
    for item in diff_list:
        code_suffix = str(item.get("f12", "")).upper()
        name = mapping.get(code_suffix) or item.get("f14")
        if name:
            item["f58"] = name
            result[name] = item
    return result

async def draw_future_img():
    global FUTURE_IMG_CACHE, FUTURE_IMG_LOCK
    if FUTURE_IMG_LOCK is None: FUTURE_IMG_LOCK = asyncio.Lock()
    async with FUTURE_IMG_LOCK:
        now = datetime.now()
        if FUTURE_IMG_CACHE and (now - FUTURE_IMG_CACHE[0]).total_seconds() < 20:
            return FUTURE_IMG_CACHE[1]
        
        d1_raw = await get_mtdata("国际市场")
        d1 = d1_raw.get("data", {}).get("diff", []) if isinstance(d1_raw, dict) else []
        
        tasks = [
            _get_list_data(commodity),
            _get_list_data(bond),
            _get_list_data(whsc),
            get_all_crypto_price()
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        def safe_dict(r): return r if isinstance(r, dict) else {}
        d2, d3, d4, d5 = [safe_dict(r) for r in results]
        
        w, h = 900, 2600
        img = Image.new("RGBA", (w, h), (2, 6, 23, 255))
        draw = ImageDraw.Draw(img)
        
        # 背景
        grad = Image.new("RGB", (1, h))
        for y in range(h):
            r = y/h
            grad.putpixel((0,y), (int(2*(1-r)+3*r), int(6*(1-r)+7*r), int(23*(1-r)+18*r)))
        img.paste(grad.resize((w, h)), (0, 0))
        
        # Header
        draw.rounded_rectangle([24, 22, 876, 120], 22, fill=(8, 13, 25, 240), outline=(150, 160, 180, 30))
        draw.text((44, 78), "All Weather Monitor", fill=(250, 255, 255), font=ss_font(34), anchor="lm")
        draw.text((w-50, 60), f"LIVE {now.strftime('%H:%M:%S')}", fill=(34, 211, 238), font=ss_font(16), anchor="rm")

        sections = [
            ("GLOBAL INDICES", d1, [list(i_code.keys())], (240, 70, 70)),
            ("COMMODITIES", d2, [["伦敦金","伦敦银","伦敦铜"],["COMEX黄金","COMEX白银","COMEX铜"],["WTI原油","布伦特原油","天然气"],["螺纹钢主连","豆粕主连","焦煤主连","生猪主连"]], (170, 90, 250)),
            ("BONDS & YIELDS", d3, [["中国30年期国债","中国10年期国债","中国2年期国债"],["美国30年期国债收益率","美国10年期国债收益率","美国2年期国债收益率"],["日本30年期国债收益率","日本10年期国债收益率","日本2年期国债收益率"],["德国10年期国债收益率","英国10年期国债收益率"]], (235, 180, 10)),
            ("FOREX", d4, [list(whsc.keys())], (20, 190, 170)),
            ("CRYPTO", d5, [list(CRYPTO_MAP.keys())], (250, 120, 25)),
        ]

        curr_y = 150
        for title, source, groups, color in sections:
            valid_groups = []
            sec_up, sec_down, sec_total = 0, 0, 0
            
            items_list = source if isinstance(source, list) else source.values()
            for g in groups:
                g_items = []
                for name_to_find in g:
                    found = None
                    if isinstance(source, dict) and name_to_find in source:
                        found = source[name_to_find]
                    else:
                        for item in items_list:
                            if (item.get("f58") or item.get("f14") or "").split(" (")[0] == name_to_find:
                                found = item
                                break
                    if found:
                        g_items.append(found)
                        sec_total += 1
                        df = _safe_float(found.get("f3") or found.get("f170"))
                        if df > 0: sec_up += 1
                        elif df < 0: sec_down += 1
                if g_items: valid_groups.append(g_items)
            
            if not valid_groups: continue
            
            rows = sum((len(g)+3)//4 for g in valid_groups)
            sec_h = 70 + rows * (CARD_H + GAP_Y)
            draw.rounded_rectangle([24, curr_y, 876, curr_y + sec_h], 20, fill=(8, 13, 25, 230), outline=(150, 160, 180, 25))
            draw.rectangle([24, curr_y, 31, curr_y + sec_h], fill=(*color, 200))
            draw.text((48, curr_y + 30), title, fill=(245, 250, 255), font=ss_font(24), anchor="lm")
            draw.text((48, curr_y + 52), f"{sec_total} ASSETS | {sec_up} UP | {sec_down} DOWN", fill=(100, 120, 140), font=ss_font(12), anchor="lm")
            
            card_y = curr_y + 65
            for g in valid_groups:
                for i, item in enumerate(g):
                    c_img = _draw_card(item)
                    img.paste(c_img, (CARD_START_X + (i%4)*(CARD_W+GAP_X), card_y + (i//4)*(CARD_H+GAP_Y)), c_img)
                card_y += ((len(g)+3)//4) * (CARD_H + GAP_Y)
            
            curr_y += sec_h + 20

        footer = get_footer()
        img.paste(footer, (450 - footer.width//2, curr_y + 10), footer)
        res = await convert_img(img.crop((0, 0, 900, min(curr_y + 100, 2600))))
        FUTURE_IMG_CACHE = (datetime.now(), res)
        return res
