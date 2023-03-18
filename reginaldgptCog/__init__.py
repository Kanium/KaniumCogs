from .reginaldgptCog import ReginaldGptCog
from redbot.core.bot import Red

def setup(bot: Red):
    cog = ReginaldGptCog(bot)
    bot.add_cog(cog)