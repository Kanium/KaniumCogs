from .reginald import ReginaldCog

def setup(bot):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)