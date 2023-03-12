from .recruitment import Recruitment
from redbot.core.bot import Red

def setup(bot: Red):
    bot.add_cog(Recruitment(bot))
##async def setup(bot: Red) -> None:
##    await bot.add_cog(Recruitment(bot))