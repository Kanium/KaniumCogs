import openai
import os
from redbot.core import Config, commands

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.config.register_global(
            openai_model="text-davinci-002"
        )
        self.config.register_guild(
            openai_api_key=None
        )

    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command()
    async def setreginaldcogapi(self, ctx, api_key):
        """Set the OpenAI API key"""
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

    @commands.guild_only()
    @commands.command()
    async def reginald(self, ctx, *, prompt=None):
        """Ask Reginald a question"""
        if prompt is None:
            prompt = "Hey,"
        try:
            api_key = await self.config.guild(ctx.guild).openai_api_key()
            if api_key is None:
                await ctx.author.send('OpenAI API key not set. Please use the "!setreginaldcogapi" command to set the key.')
                return
            model = await self.config.openai_model()
            openai.api_key = api_key
            max_tokens = min(len(prompt) * 2, 2048)
            response = openai.Completion.create(
                model=model,
                prompt=prompt,
                max_tokens=max_tokens,
                n=1,
                stop=None,
                temperature=0.5,
            )
            await ctx.send(response.choices[0].text.strip())
        except openai.error.OpenAIError as e:
            import traceback
            traceback.print_exc()
            await ctx.send(f"I apologize, sir, but I am unable to generate a response at this time. Error message: {str(e)}")

def setup(bot):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)