import asyncio
from .recruitment import Recruitment
from redbot.core.bot import Red

async def setup(bot: Red) -> None:
    await asyncio.ensure_future(bot.add_cog(Recruitment(bot)))