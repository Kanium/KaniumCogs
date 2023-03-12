from redbot.core.bot import Red
from .recruitment import Recruitment

async def setup(bot: Red) -> None:
    await bot.add_cog(Recruitment(bot))