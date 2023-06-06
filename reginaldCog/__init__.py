from redbot.core.bot import Red
from .reginald import ReginaldCog

async def setup(bot: Red):
    cog = ReginaldCog(bot)
    await bot.add_cog(cog)