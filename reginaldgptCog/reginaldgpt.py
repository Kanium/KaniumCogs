import discord
import os
from redbot.core import Config, checks, commands
import openai

class ReginaldGptCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.config.register_global(api_key=None)

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    async def reginaldgpt(self, ctx, *, message):
        try:
            api_key = await self.config.api_key()
            openai.api_key = api_key

            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant who responds succinctly"},
                    {"role": "user", "content": message}
                ]
            )

            content = response['choices'][0]['text']
            finish_reason = response['choices'][0]['finish_reason']

            if finish_reason == 'stop':
                await ctx.send(content)
            else:
                await ctx.send(f"Response not completed. Finish reason: {finish_reason}")

        except Exception as e:
            await ctx.send("As an AI robot, I errored out.")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @commands.command()
    async def setreginaldgptapikey(self, ctx, api_key):
        await self.config.api_key.set(api_key)
        openai.api_key = api_key
        await ctx.send("ReginaldGpt API key has been set.")

def setup(bot):
    cog = ReginaldGptCog(bot)
    bot.add_cog(cog)