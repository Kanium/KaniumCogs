from redbot.core.bot import Red
from .reginald import ReginaldCog

def setup(bot: Red):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)