"""新浪 fx_s* 加密现货直投源。

BTC/XRP 不是东财 secid，``resolve``（东财 searchapi）必然失败；
OKX 在机房 IP 直连 ConnectTimeout（VPS 侧 7 个月一直如此）。
新浪 ``fx_s*`` 有现货价格，但 ``SinaMarketData.quote`` 同样要先过
东财解析层，所以这里绕开直投。

只收录实测有数据的：BTC / XRP。ETH/SOL 新浪 fx_s 无现货行。
"""

from __future__ import annotations

from ...enums import AssetClass
from ...errors import MarketError, empty_error
from ...models import Quote, SymbolRef
from .client import PROVIDER, fetch_hq_lines
from .parse import parse_hq_line_fx
from .provider import SinaMarketData

# ticker → 新浪 fx_s 现货符号（2026-10-19 逐个实测）
_SPOT: dict[str, str] = {
    "BTC": "fx_sbtcusd",
    "XRP": "fx_sxrpusd",
}


class SinaCryptoMarketData(SinaMarketData):
    """加密现货：BTC/XRP 直投新浪 fx_s*，绕过东财解析层。"""

    provider_name = PROVIDER

    async def quote(self, query: str) -> Quote | MarketError:
        ticker = query.strip().upper()
        sina_sym = _SPOT.get(ticker)
        if sina_sym is None:
            # 未收录的加密标的 → 常规路径（resolve 层），多半 not_found
            return await super().quote(query)
        lines = await fetch_hq_lines([sina_sym])
        if isinstance(lines, MarketError):
            return lines
        line = lines.get(sina_sym)
        if line is None or not line.strip():
            # 符号映射成功、只是这行空（瞬时缺行）≠ 标的不存在；
            # 报 empty 让调用方顺延，_not_found_ 会短路整条源链。
            return empty_error(f"新浪加密现货无数据行: {sina_sym}", provider=PROVIDER)
        symbol = SymbolRef(
            code=ticker,
            name=ticker,
            asset_class=AssetClass.CRYPTO,
            exchange="CRYPTO",
            provider_symbol=sina_sym,
            sec_type="加密现货",
        )
        return parse_hq_line_fx(line, symbol=symbol)
