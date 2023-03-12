from redbot.core import commands
from .recruitment import Recruitment


def setup(bot: commands.Bot) -> None:
    cog = Recruitment(bot)
    bot.add_cog(cog)