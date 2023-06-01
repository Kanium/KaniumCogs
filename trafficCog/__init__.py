from .trafficCog import TrafficCog
from redbot.core.bot import Red

async def setup(bot: Red):
    cog = TrafficCog(bot)
    await bot.add_cog(cog)