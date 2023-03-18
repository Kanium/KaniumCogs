from redbot.core.bot import Red
from .reginaldgpt import ReginaldGptCog

def setup(bot: Red):
    cog = ReginaldGptCog(bot)
    bot.add_cog(cog)