import math
import asyncio
from typing import Dict, List, Union, Optional
from pathlib import Path
from datetime import datetime, timedelta
from collections import defaultdict

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from gsuid_core.logger import logger

from .utils import fill_kline
from .get_compare import to_compare_fig
from ..utils.image import render_image_by_pw, render_promax_image
from ..utils.utils import get_vix_name, int_to_percentage, number_to_chinese
from ..utils.constant import ErroText, bk_dict, market_dict
from ..utils.time_range import get_trading_minutes
from ..utils.stock.utils import get_file
from ..utils.stock.request import (
    get_gg,
    get_vix,
    get_menu,
    get_hotmap,
    get_mtdata,
)
from ..stock_config.stock_config import STOCK_CONFIG


async def to_single_fig_kline(raw_data: Dict, sp: Optional[str] = None):
    df = fill_kline(raw_data)
    if df is None:
        return ErroText["notData"]

    df["日期"] = pd.to_datetime(df["日期"], errors="coerce")
    df = df.dropna(subset=["日期"]).reset_index(drop=True)

    # 为频率判断用一个单独的已排序 Series（不改变后续绘图所用 df 顺序，除非你想按时间绘图）
    sorted_dates = df["日期"].sort_values(ignore_index=True)

    # 计算相邻差值并取中位数（更鲁棒，能抵抗周末/节假日带来的长间隔）
    deltas = sorted_dates.diff().dropna()
    if deltas.empty:
        # 退回到日线
        median_delta = pd.Timedelta(days=1)
    else:
        median_delta = deltas.dt.total_seconds().median()  # float seconds

    # 把 median_delta 统一为 Timedelta 便于后续判断与日志
    if isinstance(median_delta, (int, float)):
        median_delta = pd.Timedelta(seconds=float(median_delta))
    elif not isinstance(median_delta, pd.Timedelta):
        median_delta = pd.to_timedelta(median_delta)

    # debug 打印（运行一次看输出）
    logger.info(f"[SayuStock] median delta: {median_delta}")

    # 基于中位差值做分类（阈值使用 0.9 做容忍）
    seconds = median_delta.total_seconds()
    if seconds >= 0.9 * 86400:  # 大于或接近 1 天 -> 日线
        inferred_freq = "D"
        freq_label = "1D"
    elif seconds >= 0.9 * 3600:  # 大于或接近 1 小时 -> 小时线
        # 以小时为单位取整（比如 1H, 2H）
        hours = max(1, int(round(seconds / 3600)))
        inferred_freq = f"{hours}H"
        freq_label = inferred_freq
    else:
        # 分钟级：向最接近的整数分钟取整，并使用 pandas 的 'T' 表示分钟频率
        minutes = max(1, int(round(seconds / 60)))
        # 如果常见分钟档（1,5,15,30,60）则优先映射到这些
        for m in (1, 5, 15, 30, 60):
            if abs(minutes - m) <= (m * 0.25):  # 容忍 25% 误差映射到常见档位
                minutes = m
                break
        inferred_freq = f"{minutes}T"
        freq_label = f"{minutes}min"

    if "T" in inferred_freq:  # 分钟K
        tickformat = "%m-%d %H:%M"
    elif inferred_freq in ["H"]:
        tickformat = "%m-%d %H:%M"
    elif inferred_freq in ["M"]:
        tickformat = "%Y.%m"
    else:
        tickformat = "%Y.%m.%d"

    logger.info(f"[SayuStock] 判定周期 inferred_freq={inferred_freq}, freq_label={freq_label}")

    x_min, x_max = df["日期"].min(), df["日期"].max()

    # 添加 trace 前强制类型检查
    assert pd.api.types.is_datetime64_any_dtype(df["日期"]), "日期列必须是 datetime64 类型"

    # 计算成交量柱子的颜色
    # 如果当日收盘价高于开盘价，为红色（上涨），否则为绿色（下跌）
    volume_colors = ["red" if close >= open_price else "green" for close, open_price in zip(df["收盘"], df["开盘"])]

    fig = go.Figure(
        data=[
            go.Candlestick(
                x=df["日期"],
                open=df["开盘"],
                high=df["最高"],
                low=df["最低"],
                close=df["收盘"],
                increasing_line_color="red",
                decreasing_line_color="green",
                name="K线",
                yaxis="y1",
            ),
            go.Scatter(
                x=df["日期"],
                y=df["换手率"],
                mode="lines",
                line=dict(color="purple", width=4),
                yaxis="y2",
                name="换手率",
            ),
            go.Scatter(
                x=df["日期"],
                y=df["5日均线"],
                mode="lines",
                line=dict(color="orange", width=3),
                name="5日均线",
                yaxis="y1",
            ),
            go.Scatter(
                x=df["日期"],
                y=df["10日均线"],
                mode="lines",
                line=dict(color="blue", width=3),
                name="10日均线",
                yaxis="y1",
            ),
            # 添加量能图（成交量）
            go.Bar(
                x=df["日期"],
                y=df["成交量"],
                marker_color=volume_colors,
                name="成交量",
                yaxis="y3",
            ),
        ]
    )

    fig.update_xaxes(
        tickformat=tickformat,
        type="date",
        rangeslider_visible=False,
    )

    df["is_max"] = df["换手率"] == df["换手率"].rolling(window=3, center=True).max()
    max_turnovers = df[df["is_max"] & (df["换手率"] > 0)]

    # 添加所有最高点标记
    for _, row in max_turnovers.iterrows():
        fig.add_trace(
            go.Scatter(
                x=[row["日期"]],
                y=[row["换手率"]],
                mode="markers+text",
                text=[f"{row['换手率'] * 100:.2f}%"],
                textposition="top center",
                marker=dict(size=10, color="red"),
                showlegend=False,
                yaxis="y2",
            )
        )

    fig.update_layout(
        title=dict(
            text=f"{raw_data['data']['name']} {freq_label}",
            font=dict(size=80),
            y=0.98,
            x=0.5,
            xanchor="center",
            yanchor="top",
        ),
        xaxis=dict(
            title_font=dict(size=40),  # X轴标题字体大小
            tickfont=dict(size=40),  # X轴刻度标签字体大小
        ),
        xaxis2=dict(
            anchor="y2",
            matches="x",  # X轴同步
            showticklabels=False,  # 换手率和成交量的X轴标签可以隐藏，只保留主图的
        ),
        xaxis3=dict(
            anchor="y3",
            matches="x",  # X轴同步
            showticklabels=True,  # 量能图的X轴标签保留
        ),
        yaxis=dict(
            title="价格",
            domain=[0.5, 1],  # 主图占上方 50%
            title_font=dict(size=40),
            tickfont=dict(size=40),
        ),
        yaxis2=dict(
            title="换手率",
            domain=[0.25, 0.45],  # 换手率图放在K线图下方，量能图上方
            title_font=dict(size=40),
            tickfont=dict(size=40),
            tickformat=".0%",
        ),
        yaxis3=dict(  # 新增y3轴用于成交量
            title="成交量",
            domain=[0, 0.2],  # 量能图占最下方 20%
            title_font=dict(size=40),
            tickfont=dict(size=40),
            side="right",  # 可以选择放在右侧
        ),
        legend=dict(
            title=dict(
                font=dict(
                    size=40,
                )
            )
        ),  # 设置图例标题的大小
        font=dict(size=40),  # 设置整个图表的字体大小
        margin=dict(t=100, b=100, l=100, r=100),  # 调整边距以容纳更多的子图和标签
    )

    dates = df["日期"]

    dates = df["日期"]
    diffs = dates.diff()
    threshold = median_delta * 1.5  # 根据推断的周期自动放宽
    breaks = []
    for i in range(1, len(dates)):
        if diffs.iloc[i] > threshold:
            start = dates.iloc[i - 1]
            end = dates.iloc[i]
            # 注意这里用 bounds，而不是 values！
            breaks.append(dict(bounds=[start, end]))

    logger.info(f"[SayuStock] 自动检测到 {len(breaks)} 个时间缺口")

    fig.update_xaxes(
        type="date",
        tickformat=tickformat,
        range=[x_min, x_max],
        rangeslider_visible=False,
        rangebreaks=breaks,
    )
    return fig


# 获取个股图形
async def to_single_fig(raw_data: Dict):
    logger.info("[SayuStock] 开始获取图形 (Pro Max Mode)...")
    raw = raw_data["data"]
    price_history = raw_data["trends"]
    stock_name = raw["f58"]
    new_price = raw["f43"]
    open_price = raw["f60"]

    code_id = raw_data.get("file_name")
    full_data = []
    existing_times = {item["datetime"] for item in price_history}
    ARRAY = get_trading_minutes(code_id)
    
    for time in ARRAY:
        if time in existing_times:
            item = next(it for it in price_history if it["datetime"] == time)
            full_data.append(item)
        else:
            full_data.append({"datetime": time, "price": None, "money": 0})
    
    df = pd.DataFrame(full_data)

    # 颜色配置 (Cyberpunk HUD)
    up_color = "#00FF00"  # Matrix Green
    down_color = "#FF3B30"  # Neon Red
    line_color = "#00FFFF"  # Cyan
    bg_color = "#000000"  # OLED Black
    grid_color = "rgba(255, 255, 255, 0.05)"

    # 计算自适应范围
    max_price = df["price"].max()
    min_price = df["price"].min()
    
    # 填充缺失值以便计算范围
    valid_prices = df["price"].dropna()
    if valid_prices.empty:
        return ErroText["notOpen"]
        
    max_p = valid_prices.max()
    min_p = valid_prices.min()
    
    diff = max(abs(max_p - open_price), abs(min_p - open_price))
    y_max = open_price + diff * 1.2
    y_min = open_price - diff * 1.2

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.02,
        row_heights=[0.75, 0.25],
    )

    # 1. 价格面积图 (带渐变效果)
    fig.add_trace(
        go.Scatter(
            x=df["datetime"],
            y=df["price"],
            mode="lines",
            name="Price",
            line=dict(width=4, color=line_color),
            fill='tozeroy',
            fillcolor='rgba(0, 255, 255, 0.1)', # 淡淡的青色填充
            showlegend=False,
        ),
        row=1, col=1,
    )

    # 2. 开盘价水平线
    fig.add_hline(
        y=open_price,
        line=dict(color="rgba(255, 215, 0, 0.5)", width=2, dash="dash"),
        row=1, col=1
    )

    # 3. 量能柱状图
    bar_colors = []
    prices = df["price"].tolist()
    for i in range(len(prices)):
        if i == 0 or prices[i] is None or prices[i-1] is None:
            bar_colors.append(up_color if (prices[i] or 0) >= open_price else down_color)
        else:
            bar_colors.append(up_color if prices[i] >= prices[i-1] else down_color)

    fig.add_trace(
        go.Bar(
            x=df["datetime"],
            y=df["money"],
            marker_color=bar_colors,
            opacity=0.8,
            showlegend=False,
        ),
        row=2, col=1,
    )

    # 布局优化
    fig.update_layout(
        margin=dict(t=250, l=80, r=80, b=80), # 为顶部的 PIL HUD 留出空间
        paper_bgcolor=bg_color,
        plot_bgcolor=bg_color,
        font=dict(color="white", size=24),
    )

    fig.update_yaxes(
        range=[y_min, y_max],
        showgrid=True,
        gridcolor=grid_color,
        tickfont=dict(size=22),
        row=1, col=1
    )

    fig.update_yaxes(
        showgrid=False,
        showticklabels=False,
        row=2, col=1
    )

    fig.update_xaxes(
        showgrid=True,
        gridcolor=grid_color,
        dtick=60,
        tickfont=dict(size=22),
        row=1, col=1
    )
    
    fig.update_xaxes(
        dtick=30,
        tickfont=dict(size=22),
        row=2, col=1
    )

    return fig


async def to_multi_fig(raw_data_list: List[Dict]):
    """
    Generates a plotly figure for multiple stocks, with a multi-line title and sorted volume bars.
    """
    logger.info("[SayuStock] Starting to generate multi-stock figure with multi-line title...")

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.05,
        row_heights=[0.7, 0.3],
    )

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

    max_fluctuation = 0.0
    processed_stocks = []
    time_array = None

    # First pass to process data
    for raw_data in raw_data_list:
        raw = raw_data["data"]
        open_price = raw.get("f60")
        if not isinstance(open_price, (int, float)) or open_price == 0:
            print(f"Skipping {raw.get('f58', 'Unknown')} due to invalid open price: {open_price}.")
            continue

        code_id = raw_data.get("file_name", "").split("_")[0]
        if time_array is None:
            time_array = get_trading_minutes(code_id)

        full_data = []
        existing_times = {item["datetime"] for item in raw_data["trends"]}
        for time in time_array:
            if time in existing_times:
                full_data.append(next(item for item in raw_data["trends"] if item["datetime"] == time))
            else:
                full_data.append({"datetime": time, "price": None, "money": 0})

        price_history_pd = pd.DataFrame(full_data)
        price_history_pd["percentage_change"] = ((price_history_pd["price"] / open_price) - 1) * 100

        current_max = price_history_pd["percentage_change"].max()
        current_min = price_history_pd["percentage_change"].min()
        if not np.isnan(current_max):
            max_fluctuation = max(max_fluctuation, abs(current_max))
        if not np.isnan(current_min):
            max_fluctuation = max(max_fluctuation, abs(current_min))

        processed_stocks.append(
            {
                "name": raw["f58"],
                "df": price_history_pd,
                # 🌟 **核心修改点 1: 计算并存储总成交额**
                "total_volume": price_history_pd["money"].sum(),
            }
        )

    # 🌟 **核心修改点 2: 按总成交额降序排序**
    # 这将确保成交额大的股票先被绘制（在底层），成交额小的后绘制（在顶层）
    processed_stocks.sort(key=lambda x: x["total_volume"], reverse=True)

    y_axis_max = (max_fluctuation // 2 + 1) * 2
    y_axis_min = -y_axis_max

    # Second pass to add traces in the new sorted order
    for i, stock_data in enumerate(processed_stocks):
        df = stock_data["df"]
        line_color = colors[i % len(colors)]

        fig.add_trace(
            go.Scatter(
                x=df["datetime"],
                y=df["percentage_change"],
                mode="lines",
                name=stock_data["name"],
                line=dict(width=3, color=line_color),
                showlegend=True,
            ),
            row=1,
            col=1,
        )

        last_valid_index = df["percentage_change"].last_valid_index()
        if last_valid_index is not None:
            last_x = df["datetime"][last_valid_index]
            last_y = df["percentage_change"][last_valid_index]
            fig.add_annotation(
                x=last_x,
                y=last_y,
                text=f"<b>{stock_data['name']}</b>",
                showarrow=False,
                xshift=25,
                yshift=10,
                bgcolor=line_color,
                font=dict(color="white", size=18),
                row=1,
                col=1,
            )

        fig.add_trace(
            go.Bar(
                x=df["datetime"],
                y=df["money"].fillna(0),
                name=stock_data["name"] + " Volume",
                marker_color=line_color,
                showlegend=False,
            ),
            row=2,
            col=1,
        )

    main_title = "<b>分时涨跌幅对比</b>"
    subtitle_parts = []

    for stock in processed_stocks:
        df = stock["df"]
        last_change_series = df["percentage_change"].dropna()
        if not last_change_series.empty:
            last_change = last_change_series.iloc[-1]
            color = "red" if last_change >= 0 else "green"
            sign = "+" if last_change >= 0 else ""
            subtitle_parts.append(
                f"<b>{stock['name']}: <span style='color:{color};'>{sign}{last_change:.2f}%</span></b>"
            )

    final_title = f"{main_title}<br>{'&nbsp;&nbsp;&nbsp;'.join(subtitle_parts)}"

    fig.add_hrect(
        y0=0,
        y1=y_axis_max,
        fillcolor="red",
        opacity=0.1,
        layer="below",
        line_width=0,
        row=1,  # type: ignore
        col=1,  # type: ignore
    )
    fig.add_hrect(
        y0=y_axis_min,
        y1=0,
        fillcolor="green",
        opacity=0.1,
        layer="below",
        line_width=0,
        row=1,  # type: ignore
        col=1,  # type: ignore
    )
    fig.add_hline(
        y=0,
        line=dict(color="yellow", width=1, dash="dash"),
        row=1,  # type: ignore
        col=1,  # type: ignore
    )

    fig.update_layout(
        title=dict(
            text=final_title,
            font=dict(size=60),
            y=0.96,
            x=0.5,
            xanchor="center",
            yanchor="top",
        ),
        margin=dict(t=200, l=70, r=70, b=80),
        paper_bgcolor="black",
        plot_bgcolor="black",
        font=dict(color="white", size=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.08,
            xanchor="right",
            x=1,
            font=dict(size=60),
        ),
        barmode="stack",
    )

    tick_values = [
        p for p in range(int(np.floor(y_axis_min)), int(np.ceil(y_axis_max)) + 1, 2) if y_axis_min <= p <= y_axis_max
    ]
    tick_texts = [f"{p}%" for p in tick_values]

    fig.update_yaxes(
        title_text="<b>涨跌幅 (%)</b>",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.2)",
        range=[y_axis_min, y_axis_max],
        tickvals=tick_values,
        ticktext=tick_texts,
        row=1,
        col=1,
    )

    fig.update_yaxes(title_text="<b>成交额</b>", showgrid=False, row=2, col=1)
    fig.update_xaxes(
        showticklabels=True,
        showgrid=True,
        gridcolor="rgba(255,255,255,0.2)",
        dtick=60,
        tickangle=0,
        row=1,
        col=1,
    )
    fig.update_xaxes(
        title_text="<b>时间</b>",
        showgrid=True,
        gridcolor="rgba(255,255,255,0.2)",
        tickangle=45,
        dtick=30,
        row=2,
        col=1,
    )

    return fig


async def to_fig(
    raw_data: Dict,
    market: str,
    sector: Optional[str] = None,
    layer: int = 2,
):
    """
    layer = 2 是按照F100分类，大盘云图

    layer = 1 就全部都在一起，概念云图
    """
    all_stocks = []
    for item in raw_data.get("data", {}).get("diff", []):
        if item.get("f20") == "-" or item.get("f100") == "-" or item.get("f3") == "-":
            continue

        category_name = item["f100"]
        if item["f14"].startswith(("ST", "*ST")):
            category_name = "ST"

        all_stocks.append(
            {
                "category": category_name,
                "name": item["f14"],
                "value": item["f20"],
                "diff_val": item["f3"],
                "code": item["f12"],
                "sector": sector,
            }
        )

    if not all_stocks:
        return ErroText["notData"]

    grouped_by_category = defaultdict(list)
    for stock in all_stocks:
        grouped_by_category[stock["category"]].append(stock)

    final_stock_list = []

    if market == "大盘云图" or market == "概念云图":
        categories_to_process = list(grouped_by_category.keys())
    elif sector in grouped_by_category:
        categories_to_process = [sector]
    else:
        for i in grouped_by_category.keys():
            if sector in i:
                categories_to_process = [i]
                break
        else:
            return ErroText["notData"]

    for cat_name in categories_to_process:
        stock_items = grouped_by_category[cat_name]
        num_items = len(stock_items)  # 获取当前行业的股票总数
        if layer == 1:
            fit = 1
            num_to_extract = num_items
        else:
            if num_items <= 40:
                fit = 0.6  # 总数40以内，计划显示50%
            elif num_items <= 100:
                fit = 0.4  # 40到100之间，计划显示40%
            elif num_items <= 200:
                fit = 0.3  # 100到200之间，计划显示30%
            else:
                fit = 0.2  # 超过100，计划显示30%

            ideal_count = math.ceil(num_items * fit)
            clamped_count = max(3, min(ideal_count, 15))
            num_to_extract = min(clamped_count, num_items)

        sorted_stocks = sorted(stock_items, key=lambda x: x["value"], reverse=True)
        subset_data = sorted_stocks[:num_to_extract]

        final_stock_list.extend(subset_data)

    if not final_stock_list:
        return ErroText["notData"]

    # 步骤 4, 5, 6: 创建DataFrame并返回指定格式 (此部分不变)
    df = pd.DataFrame(final_stock_list)
    df = df.sort_values(by="value", ascending=False)

    category = ("<b>" + df["category"] + "</b>").tolist()
    stock_name = df["name"].tolist()
    values = df["value"].tolist()
    diff = df["diff_val"].tolist()
    custom_info = df["diff_val"].apply(lambda d: f"+{d}%" if d >= 0 else f"{d}%").tolist()

    data = {
        "Category": category,
        "StockName": stock_name,
        "Values": values,
        "Diff": diff,
        "CustomInfo": custom_info,
        "sector": sector,
    }

    df = pd.DataFrame(data)

    df = df.sort_values(by="Values", ascending=False, inplace=False)

    if layer == 1:
        treemap_path = ["sector", "Category", "StockName"]
    else:
        treemap_path = ["Category", "StockName"]

    # 生成 Treemap
    fig = px.treemap(
        df,
        path=treemap_path,
        values="Values",  # 定义块的大小
        color="Diff",  # 根据数值上色
        color_continuous_scale=[
            [0, "rgba(0, 255, 0, 1)"],  # 绿色，透明度1
            [0.5, "rgba(61, 61, 59, 1)"],
            # [0.4, 'rgba(0, 255, 0, 1)'],
            # [0.6, 'rgba(255, 0, 0, 1)'],
            [1, "rgba(255, 0, 0, 1)"],  # 红色，透明度1
        ],  # 渐变颜色
        color_continuous_midpoint=0,
        range_color=[-10, 10],  # 设置数值范围
        custom_data=["CustomInfo"],
        branchvalues="total",
    )

    # 控制显示内容
    fig.update_traces(
        marker=dict(
            cmin=-10,  # 设置最小值
            cmax=10,  # 设置最大值
        ),
        marker_pad=dict(
            l=5,
            r=5,
            b=5,
            t=60,
        ),
        textfont=dict(
            color="white",
        ),
        textfont_family="MiSans",
        textfont_weight=350,
        texttemplate="%{label}<br>%{customdata[0]}",
        # textinfo="label+text",
        textfont_size=50,  # 设置字体大小
        textposition="middle center",
    )

    fig.update_layout(
        # uniformtext=dict(minsize=30, mode='hide'),
        margin=dict(t=0, b=0, l=0, r=0),
        paper_bgcolor="black",
        plot_bgcolor="black",
        font=dict(color="white"),
        coloraxis_showscale=False,
    )
    return fig


async def render_html(
    market: str = "沪深A",
    sector: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Union[str, Path]:
    _sp_str = None
    logger.info(f"[SayuStock] market: {market} sector: {sector}")

    if sector != "single-stock":
        if market in market_dict and "b:" in market_dict[market]:
            sector = market
        elif market in bk_dict:
            sector = market

    # 如果是个股错误
    if sector == "single-stock" and not market:
        return ErroText["notMarket"]

    if not market:
        market = "沪深A"

    logger.info("[SayuStock] 开始获取数据...")
    m_list = []
    raw_datas = []

    # 对比个股 数据
    if market == "大盘云图":
        if sector:
            raw_data = await get_mtdata(sector, True, 1, 100)
        else:
            raw_data = await get_hotmap()
        # raw_data = await get_mtdata('沪深A', True, 1, 100)
    elif market == "行业云图":
        """
        hybk = await get_menu(2)
        if market in hybk:
            fs = hybk[market]
        else:
            for i in hybk:
                if market in i:
                    fs = hybk[i]
                    break
            else:
                return ErroText['typemap']
        """

        raw_data = await get_hotmap()
    elif market == "概念云图":
        if sector:
            sector = sector.upper()
            gnbk = await get_menu(3)

            if sector in gnbk:
                fs = gnbk[sector]
            else:
                for i in gnbk:
                    if sector in i:
                        sector = i
                        fs = gnbk[i]
                        break
                else:
                    return ErroText["typemap"]

            raw_data = await get_mtdata(fs, True, 1, 100)
        else:
            raw_data = "概念云图需要后跟概念类型, 例如： 概念云图 华为欧拉"
    elif sector and sector.startswith("single-stock-kline"):
        raw_data = await get_gg(
            market,
            sector,
            start_time,
            end_time,
        )
    elif sector == "compare-stock":
        markets = market.split(" ")
        raw_datas: List[Dict] = []
        for m in markets:
            if m == "A500":
                m = "A500ETF"
            raw_data = await get_gg(
                m,
                "single-stock-kline-111",
                start_time,
                end_time,
            )
            if isinstance(raw_data, str):
                return raw_data
            raw_datas.append(raw_data)

        st_f = start_time.strftime("%Y%m%d") if start_time else ""
        et_f = end_time.strftime("%Y%m%d") if end_time else ""
        _sp_str = f"compare-stock-{st_f}-{et_f}"
    elif sector == "single-stock":
        m = get_vix_name(market)
        if m is None:
            m_list = market.split(" ")
            if len(m_list) == 1:
                raw_data = await get_gg(
                    m_list[0],
                    "single-stock",
                    start_time,
                    end_time,
                )
            else:
                TASK = []
                for m in m_list:
                    vix_m = get_vix_name(m)
                    if vix_m is None:
                        TASK.append(get_gg(m, "single-stock", start_time, end_time))
                    else:
                        TASK.append(get_vix(vix_m))
                raw_datas = await asyncio.gather(*TASK)
                raw_data = raw_datas[0]
        else:
            raw_data = await get_vix(m)

    else:
        raw_data = await get_mtdata(market)

    if isinstance(raw_data, str):
        return raw_data

    file = get_file(market, "html", sector, _sp_str)
    if file.exists():
        minutes = STOCK_CONFIG.get_config("mapcloud_refresh_minutes").data
        file_mod_time = datetime.fromtimestamp(file.stat().st_mtime)
        if datetime.now() - file_mod_time < timedelta(minutes=minutes):
            logger.info(f"[SayuStock] html文件在{minutes}分钟内，直接返回文件数据。")
            return file

    # 个股
    if sector == "single-stock":
        if raw_datas:
            fig = await to_multi_fig(raw_datas)
        else:
            fig = await to_single_fig(raw_data)
    # 个股对比
    elif sector == "compare-stock":
        fig = await to_compare_fig(raw_datas)
    # 个股 日k 年k
    elif sector and sector.startswith("single-stock-kline"):
        fig = await to_single_fig_kline(raw_data)
    # 大盘云图
    else:
        fig = await to_fig(
            raw_data,
            market,
            sector,
            2 if market == "大盘云图" else 1,
        )
    if isinstance(fig, str):
        return fig

    # fig.show()
    fig.write_html(file)
    return file


async def render_image(
    market: str = "沪深A",
    sector: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
):
    html_path = await render_html(
        market,
        sector,
        start_time,
        end_time,
    )

    if isinstance(html_path, str):
        return html_path

    if sector and sector.startswith("single-stock-kline") or sector == "compare-stock":
        w = 4600
        h = 3000
        _scale = 1
    elif sector == "single-stock":
        w = 4000
        h = 3000
        _scale = 1
    else:
        w = 0
        h = 0
        _scale = 0

    img = await render_image_by_pw(
        html_path,
        w,
        h,
        _scale,
    )
    
    # --- Pro Max 后处理 ---
    if sector == "single-stock" and isinstance(img, bytes):
        try:
            # 解析原始数据用于 HUD 渲染
            # 注意：这里我们可能需要再次获取数据或者传递数据
            # 为简单起见，我们假设 html_path 包含我们需要的信息（或者我们可以重构以传递数据）
            # 由于 render_html 已经完成了数据获取，这里我们重新获取一次（或者从缓存拿）
            from ..utils.stock.request import get_gg
            raw_data = await get_gg(market, "single-stock")
            if isinstance(raw_data, dict):
                raw = raw_data["data"]
                img = await render_promax_image(
                    base_img_bytes=img,
                    title=raw["f58"],
                    subtitle=f"{market} | 换手 {raw['f168']}% | 额 {number_to_chinese(raw['f48'])}",
                    price=str(raw["f43"]),
                    change_pct=str(raw["f170"]),
                    is_up=raw["f170"] >= 0,
                    footer_info=f"SayuStock Pro Max | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
                )
        except Exception as e:
            logger.error(f"[SayuStock] Pro Max 后处理失败: {e}")

    return img
