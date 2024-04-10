from redbot.core.bot import Red
from .trafficCog import TrafficCog

def setup(bot):
    cog = TrafficCog(bot)
    bot.add_cog(cog)
