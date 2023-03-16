import discord
import json
import openai
import os
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
        self.config.register_global(
            openai_model="text-davinci-002"
        )
        self.config.register_guild(
            openai_api_key=None
        )

    def has_kanium_role():
        async def predicate(ctx):
            kanium_role_id = 280260875678515200
            return any(role.id == kanium_role_id for role in ctx.author.roles)
        return commands.check(predicate)

    def has_admin_role():
        async def predicate(ctx):
            #janitor_role_id = 672156832323600396
            #has_janitor_role = any(role.id == janitor_role_id for role in ctx.author.roles) # Uncomment this line
            has_admin_permission = ctx.author.guild_permissions.administrator
            #return has_janitor_role or has_admin_permission
            return has_admin_permission
        return commands.check(predicate)


    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

    @commands.guild_only()
    @has_kanium_role()
    @commands.command(help="Ask Reginald a question")
    @commands.cooldown(1, 60, commands.BucketType.user)  # 1-minute cooldown per user
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
            for chunk in self.split_response(response_text, 2000):
                await ctx.send(chunk)
        except OpenAIError as e:
            await ctx.send(f"I apologize, but I am unable to generate a response at this time. Error message: {str(e)}")
        except commands.CommandOnCooldown as e:
            remaining_seconds = int(e.retry_after)
            await ctx.author.send(f'Please wait {remaining_seconds} seconds before using the "reginald" command again.')

    async def generate_response(self, api_key, prompt):
        model = await self.config.openai_model()
        url = f"https://api.openai.com/v1/engines/{model}/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "prompt": prompt,
            "max_tokens": 1000,
            "n": 1,
            "stop": None,
            "temperature": 0.5,
            "presence_penalty": 0.5,
            "frequency_penalty": 0.5,
            "best_of": 3,
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=data) as resp:
                response = await resp.json()

        return response['choices'][0]['text'].strip()

    @staticmethod
    def split_response(response_text, max_chars):
        chunks = []
        while len(response_text) > max_chars:
            split_index = response_text[:max_chars].rfind(' ')
            chunk = response_text[:split_index]
            chunks.append(chunk)
            response_text = response_text[split_index:].strip()
        chunks.append(response_text)
        return chunks
    
    @commands.guild_only()
    @has_admin_role()
    @commands.command(help="Ask Reginald to generate an image based on a prompt")
    @commands.cooldown(1, 300, commands.BucketType.user)  # 5-minute cooldown per user
    async def reginaldimagine(self, ctx, *, prompt=None):
        ignored_user_id = 138125632876838912
        if ctx.author.id == ignored_user_id:
            return

        if prompt is None:
            await ctx.author.send("Please provide a prompt for the image.")
            return

        api_key = await self.config.guild(ctx.guild).openai_api_key()
        if api_key is None:
            await ctx.author.send('OpenAI API key not set. Please use the "!setreginaldcogapi" command to set the key.')
            return

        try:
            image_url = await self.generate_image(api_key, prompt)
            if image_url:
                async with ctx.typing():
                    async with aiohttp.ClientSession() as session:
                        async with session.get(image_url) as resp:
                            image_data = await resp.read()
                            image = Image.open(BytesIO(image_data))
                            with tempfile.TemporaryDirectory() as temp_dir:
                                image_path = os.path.join(temp_dir, "image.png")
                                image.save(image_path)
                                await ctx.send(file=discord.File(image_path))
            else:
                await ctx.author.send("I apologize, but I am unable to generate an image based on the provided prompt.")
        except Exception as e:
            await ctx.author.send(f"I apologize, but I am unable to generate an image at this time. Error message: {str(e)}")

    async def generate_image(self, api_key, prompt):
        url = "https://api.openai.com/v1/images/generations"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }
        data = {
            "prompt": prompt,
            "n": 1,
            "size": "512x512",
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, data=json.dumps(data)) as resp:
                response = await resp.json()

        if response and "data" in response and len(response["data"]) > 0:
            return response["data"][0]["url"]
        return None

    @reginald.error
    async def reginald_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("I'm sorry, but I couldn't understand your input. Please check your message and try again.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required role to use this command.")
        else:
            await ctx.send(f"An unexpected error occurred: {error}")

    @reginaldimagine.error
    async def reginaldimagine_error(self, ctx, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("I'm sorry, but I couldn't understand your input. Please check your message and try again.")
        elif isinstance(error, commands.CheckFailure):
            await ctx.send("You do not have the required role to use this command.")
        else:
            await ctx.send(f"An unexpected error occurred: {error}")

def setup(bot):
    cog = ReginaldCog(bot)
    bot.add_cog(cog)
