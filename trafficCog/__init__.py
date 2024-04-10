from redbot.core.bot import Red
from .trafficCog import TrafficCog

async def setup(bot: Red):
    cog = TrafficCog(bot)
    await bot.add_cog(cog)