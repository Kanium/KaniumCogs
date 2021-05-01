from .eventsCog import EventsCog
from redbot.core.bot import Red

def setup(bot: Red):
    bot.add_cog(EventsCog(bot))