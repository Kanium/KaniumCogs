import discord
import openai
from redbot.core import Config, commands

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        default_global = {"openai_model": "gpt-3.5-turbo"}
        default_guild = {"openai_api_key": None, "memory": {}, "shared_memory": []}
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def is_admin(self, ctx):
        admin_role = await self.config.guild(ctx.guild).admin_role()
        return discord.utils.get(ctx.author.roles, name=admin_role) is not None or ctx.author.guild_permissions.administrator

    async def is_allowed(self, ctx):
        allowed_role = await self.config.guild(ctx.guild).allowed_role()
        return discord.utils.get(ctx.author.roles, name=allowed_role) is not None

    @commands.command(name="reginald_allowrole", help="Allow a role to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx, role: discord.Role):
        await self.config.guild(ctx.guild).allowed_role.set(role.name)
        await ctx.send(f"The {role.name} role is now allowed to use the Reginald command.")

    @commands.command(name="reginald_disallowrole", help="Remove a role's ability to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx):
        await self.config.guild(ctx.guild).allowed_role.clear()
        await ctx.send(f"The role's permission to use the Reginald command has been revoked.")

    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

    @commands.guild_only()
    @commands.command(help="Ask Reginald a question")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
        if not await self.is_admin(ctx) and not await self.is_allowed(ctx):
            raise commands.CheckFailure("You do not have the required role to use this command.")
        
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
            user_id = str(ctx.author.id)
            memory = await self.config.guild(ctx.guild).memory()
            shared_memory = await self.config.guild(ctx.guild).shared_memory()
            
            if user_id not in memory:
                memory[user_id] = []

            memory[user_id].append({"role": "user", "content": prompt})
            response_text = await self.generate_response(api_key, memory[user_id] + shared_memory)
            memory[user_id].append({"role": "assistant", "content": response_text})
            await self.config.guild(ctx.guild).memory.set(memory)

            # Optionally, add to shared memory if relevant
            shared_memory.append({"role": "user", "content": prompt})
            shared_memory.append({"role": "assistant", "content": response_text})
            await self.config.guild(ctx.guild).shared_memory.set(shared_memory)

            for chunk in self.split_response(response_text, 2000):
                await ctx.send(chunk)
        except OpenAIError as e:
            await ctx.send(f"I apologize, but I am unable to generate a response at this time. Error message: {str(e)}")

    async def generate_response(self, api_key, messages):
        model = await self.config.openai_model()
        openai.api_key = api_key
        response = openai.ChatCompletion.create(
            model=model,
            max_tokens=512,
            n=1,
            stop=None,
            temperature=0.7,
            presence_penalty=0.5,
            frequency_penalty=0.5,
            messages=messages
        )
        return response['choices'][0]['message']['content'].strip()

    @staticmethod
    def split_response(response_text, max_chars):
        chunks = []
        while len(response_text) > max_chars:
            split_index = response_text[:max_chars].rfind(' ')
            chunk = response_text[:max_chars] if split_index == -1 else response_text[:split_index]
            chunks.append(chunk.strip())
            response_text = response_text[split_index:].strip() if split_index != -1 else response_text[max_chars:]
        chunks.append(response_text)
        return chunks

    @reginald.error
    async def reginald_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.author.send("I'm sorry, but I couldn't understand your input. Please check your message and try again.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.author.send("You do not have the required role to use this command.")
        else:
            await ctx.author.send(f"An unexpected error occurred: {error}")

def setup(bot):
    bot.add_cog(ReginaldCog(bot))
