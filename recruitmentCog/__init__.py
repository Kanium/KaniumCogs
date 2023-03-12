from redbot.core.bot import Red
from .recruitment import Recruitment


def setup(bot: Red):
    bot.add_cog(Recruitment(bot))
