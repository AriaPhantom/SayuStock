import asyncio

import httpx
from bs4 import BeautifulSoup

from gsuid_core.logger import logger


async def get_live_pch_by_symbol(soup, symbol):
    table = soup.select_one("table.table.table-hover.sortable-theme-minimal")

    if not table:
        return None

    target_tr = table.select_one(f'tr[data-symbol="{symbol}"]')

    if not target_tr:
        return None

    pch_td = target_tr.select_one("td#pch")
    p_td = target_tr.select_one("td#p")

    if not pch_td:
        all_tds = target_tr.find_all("td")
        if len(all_tds) >= 4:
            pch_td = all_tds[3]
        else:
            return None

    if not p_td:
        all_tds = target_tr.find_all("td")
        if len(all_tds) >= 3:
            p_td = all_tds[2]
        else:
            return None

    return float(pch_td.get_text(strip=True)[:-1]), float(p_td.get_text(strip=True))


def calculate_change_rate(a: float, b: float):
    previous_value = b - a
    if previous_value == 0:
        return 0

    diff = a / previous_value
    return diff * 100


async def get_jpy():
    url = "https://zh.tradingeconomics.com/japan/government-bond-yield"
    symbols = {
        "日本30年期国债收益率": "GJGB30Y:IND",
        "日本10年期国债收益率": "GJGB10:IND",
        "日本2年期国债收益率": "GJGB2Y:IND",
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit"
        "/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, follow_redirects=True, timeout=15.0)
        response.raise_for_status()
        html_content = response.text

    soup = BeautifulSoup(html_content, "html.parser")

    result = {}
    for name, symbol in symbols.items():
        data = await get_live_pch_by_symbol(soup, symbol)
        if data is None:
            continue

        diff = calculate_change_rate(data[0], data[1])
        logger.debug(f"{symbol}: {data[0]} ({diff:.2%})")
        result[name] = {
            "f58": name,
            "f14": name,
            "f43": data[1],
            "f170": diff,
            "f48": "",
        }

    if not result:
        return None

    return result


if __name__ == "__main__":
    print(asyncio.run(get_jpy()))
