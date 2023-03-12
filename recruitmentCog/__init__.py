from .recruitment import Recruitment
from redbot.core.bot import Red

async def setup(bot: Red) -> None:
    await bot.add_cog(Recruitment(bot))