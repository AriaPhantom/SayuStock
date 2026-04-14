from gsuid_core.sv import SV
from gsuid_core.bot import Bot
from gsuid_core.logger import logger
from gsuid_core.models import Event

sv_stock_kronos = SV("模型预测")


@sv_stock_kronos.on_prefix(("模型预测", "ai预测", "AI预测", "趋势预测"))
async def send_stock_kronos(bot: Bot, ev: Event):
    logger.warning("[SayuStock] [模型预测] 已在默认部署中禁用（依赖可选的 torch/Kronos 运行时）")
    await bot.send(
        "[SayuStock] 模型预测功能当前已禁用；默认部署不再加载 torch/Kronos 依赖。",
        at_sender=True,
    )
