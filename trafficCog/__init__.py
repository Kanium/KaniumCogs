from .trafficCog import TrafficCog
from redbot.core.bot import Red

async def setup(bot: Red):
    await bot.add_cog(TrafficCog(bot))