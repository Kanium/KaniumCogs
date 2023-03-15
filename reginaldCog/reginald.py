import openai
import os
import random
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
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

    @commands.guild_only()
    @commands.command(help="Ask Reginald a question")
    @commands.cooldown(1, 300, commands.BucketType.user)  # 5-minute cooldown per user
    async def reginald(self, ctx, *, prompt=None):
        ignored_user_id = 138125632876838912
        if ctx.author.id == ignored_user_id:
            return

        greetings = [
            "Greetings! How may I be of assistance to you?",
            "Yes? How may I help?",
            "Good day! How can I help you?",
            "You rang? What can I do for you?",
        ]
        if prompt is None:
            await ctx.send(random.choice(greetings))
            return

        api_key = await self.config.guild(ctx.guild).openai_api_key()
        if api_key is None:
            await ctx.author.send('OpenAI API key not set. Please use the "!setreginaldcogapi" command to set the key.')
            return

        try:
            response_text = await self.generate_response(api_key, prompt)
            await ctx.send(response_text)
        except openai.error.OpenAIError as e:
            await ctx.send(f"I apologize, but I am unable to generate a response at this time. Error message: {str(e)}")

    async def generate_response(self, api_key, prompt):
        model = await self.config.openai_model()
        openai.api_key = api_key
        max_tokens = 1000
        temperature = 0.7
        response = openai.Completion.create(
            model=model,
            prompt=prompt,
            max_tokens=max_tokens,
            n=1,
            stop=None,
            temperature=temperature,
            presence_penalty=0.3,
            frequency_penalty=0.3,
            best_of=3
        )
        return response.choices[0].text.strip()

def setup(bot):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)
