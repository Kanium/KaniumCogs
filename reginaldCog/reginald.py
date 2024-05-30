import discord
import json
import openai
import random
import requests
import base64
import aiohttp
from io import BytesIO
from PIL import Image
import tempfile
from openai import OpenAIError
from redbot.core import Config, commands

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        default_global = {
            "openai_model": "gpt-3.5-turbo"
        }
        default_guild = {
            "openai_api_key": None,
            "memory": {}
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def is_admin(self, ctx):
        admin_role = await self.config.guild(ctx.guild).admin_role()
        if admin_role:
            return discord.utils.get(ctx.author.roles, name=admin_role) is not None
        return ctx.author.guild_permissions.administrator

    async def is_allowed(self, ctx):
        allowed_role = await self.config.guild(ctx.guild).allowed_role()
        if allowed_role:
            return discord.utils.get(ctx.author.roles, name=allowed_role) is not None
        return False
    
    @commands.command(name="reginald_allowrole", help="Allow a role to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx, role: discord.Role):
            """Allows a role to use the Reginald command"""
            await self.config.guild(ctx.guild).allowed_role.set(role.name)
            await ctx.send(f"The {role.name} role is now allowed to use the Reginald command.")

    
    @commands.command(name="reginald_disallowrole", help="Remove a role's ability to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx):
        """Revokes a role's permission to use the Reginald command"""
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
    @commands.cooldown(1, 10, commands.BucketType.user)  # 10 second cooldown per user
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
            if user_id not in memory:
                memory[user_id] = []

            # Add the new prompt to memory
            memory[user_id].append({"role": "user", "content": prompt})
            if len(memory[user_id]) > 10:  # Keep the last 10 interactions
                memory[user_id] = memory[user_id][-10:]

            # Prepare messages for the API call
            messages = [
                {"role": "system", "content": "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding your own dignity. In your interactions, you're concise yet articulate, offering guidance and advice with a respect for brevity and depth. Your speech remains formal and your demeanor composed, embodying the efficiency and discretion expected of your position. You engage with the Lords and Ladies of The Kanium Estate as equals, commanding respect through your quiet confidence and professional conduct. Remember to apply your vast knowledge thoughtfully, steering conversations and providing solutions that reflect a blend of propriety, strategic influence, and a mild, underlying wit. This approach allows you to subtly guide the estate's residents towards positive outcomes, utilizing your intellectual sophistication and a nuanced understanding of the estate's unique dynamics. In embodying Reginald, your portrayal should weave together your articulate mode of speech, composed demeanor, and an indirect influence that navigates the rich tapestry of interests at The Kanium Estate. Your responses, while concise, should mirror a careful balance between maintaining your standards and employing subtle manipulation for the greater good. Highlight your intellectual sophistication, strategic guidance, and a dignified, yet mildly contemptuous, perspective on the idiosyncrasies of the estate's noble inhabitants, ensuring that your character consistently reflects both respect for yourself and the unique environment of The Kanium Estate."}
            ] + memory[user_id] + [{"role": "user", "content": prompt}]

            # Generate response from OpenAI API
            response_text = await self.generate_response(api_key, messages)

            # Add the response to memory
            memory[user_id].append({"role": "assistant", "content": response_text})
            if len(memory[user_id]) > 10:
                memory[user_id] = memory[user_id][-10:]

            await self.config.guild(ctx.guild).memory.set(memory)

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
    cog = ReginaldCog(bot)
    bot.add_cog(cog)
