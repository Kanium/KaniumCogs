from redbot.core import commands
from .recruitment import Recruitment


async def setup(bot: commands.Bot) -> None:
    cog = Recruitment(bot)
    await bot.add_cog(cog)