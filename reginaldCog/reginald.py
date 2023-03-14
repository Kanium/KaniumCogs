import openai
from redbot.core import Config, commands
from threading import Lock
from ratelimit import rate_limited

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890)
        self.config.register_global(
            openai_api_key="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",
            openai_model="text-davinci-002"
        )
        self.lock = Lock()

    @rate_limited(1, 10) # Limits command execution to 1 per 10 seconds
    @commands.command()
    @commands.has_permissions(administrator=True)
    async def reginald(self, ctx, *, prompt=None):
        """Ask Reginald a question"""
        if prompt is None:
            prompt = "Hey,"
        async with ctx.typing(), self.lock:
            try:
                self.api_key = await self.config.openai_api_key()
                self.model = await self.config.openai_model()
                openai.api_key = self.api_key
                max_tokens = min(len(prompt) * 2, 2048)
                response = openai.Completion.create(
                    model=self.model,
                    prompt=prompt,
                    max_tokens=max_tokens,
                    n=1,
                    stop=None,
                    temperature=0.5,
                )
                await ctx.send(response.choices[0].text.strip())
            except openai.error.OpenAIError as e:
                await ctx.send("I apologize, sir, but I am unable to generate a response at this time.")
                print(f"OpenAI API Error: {e}")

def setup(bot):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)
