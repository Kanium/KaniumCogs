import discord
import openai
import random
import asyncio
import traceback
from redbot.core import Config, commands
from openai import OpenAIError

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.memory_locks = {}  # ✅ Prevents race conditions per channel

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "memory": {},  # Memory now tracks by channel
            "admin_role": None,
            "allowed_role": None
        }
        self.config.register_global(**default_global)
        self.config.register_guild(**default_guild)

    async def is_admin(self, ctx):
        """✅ Checks if the user is an admin (or has an assigned admin role)."""
        admin_role_id = await self.config.guild(ctx.guild).admin_role()
        if admin_role_id:
            return any(role.id == admin_role_id for role in ctx.author.roles)
        return ctx.author.guild_permissions.administrator

    async def is_allowed(self, ctx):
        """✅ Checks if the user is allowed to use Reginald based on role settings."""
        allowed_role_id = await self.config.guild(ctx.guild).allowed_role()
        return any(role.id == allowed_role_id for role in ctx.author.roles) if allowed_role_id else False

    @commands.command(name="reginald", help="Ask Reginald a question in shared channels")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
        """Handles multi-user memory tracking in shared channels"""
        
        if not await self.is_admin(ctx) and not await self.is_allowed(ctx):
            await ctx.send("You do not have the required role to use this command.")
            return

        if prompt is None:
            await ctx.send(random.choice(["Yes?", "How may I assist?", "You rang?"]))
            return

        api_key = await self.config.guild(ctx.guild).openai_api_key()
        if not api_key:
            await ctx.send("OpenAI API key not set. Use `!setreginaldcogapi`.")
            return

        channel_id = str(ctx.channel.id)  # ✅ Track memory per-channel

        # ✅ Ensure only one update per channel at a time
        if channel_id not in self.memory_locks:
            self.memory_locks[channel_id] = asyncio.Lock()

        async with self.memory_locks[channel_id]:  # ✅ Prevent race conditions
            async with self.config.guild(ctx.guild).memory() as guild_memory:
                memory = guild_memory.get(channel_id, [])

                # ✅ Attach the user's display name to the message
                user_name = ctx.author.display_name  # Uses Discord nickname if available
                memory.append({"user": user_name, "content": prompt})
                memory = memory[-50:]  # Keep only last 50 messages

                # ✅ Format messages with usernames
                formatted_messages = [{"role": "system", "content": (
                    "You are Reginald, the esteemed butler of The Kanium Estate. "
                    "The estate is home to Lords, Ladies, and distinguished guests, each with unique personalities and demands. "
                    "Your duty is to uphold decorum while providing assistance with wit and intelligence. "
                    "You must always recognize the individual names of those speaking and reference them when responding."
                )}] + [{"role": "user", "content": f"{entry['user']}: {entry['content']}"} for entry in memory]

                response_text = await self.generate_response(api_key, formatted_messages)

                # ✅ Store Reginald's response in memory
                memory.append({"user": "Reginald", "content": response_text})
                guild_memory[channel_id] = memory  # ✅ Atomic update inside async context

        await ctx.send(response_text[:2000])  # Discord character limit safeguard

    async def generate_response(self, api_key, messages):
        """✅ Generates a response using OpenAI's new async API client (OpenAI v1.0+)."""
        model = await self.config.openai_model()
        try:
            client = openai.AsyncOpenAI(api_key=api_key)  # ✅ Correct API usage
            response = await client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5
            )

            if not response.choices:
                return "I fear I have no words to offer at this time."

            return response.choices[0].message.content.strip()

        except OpenAIError as e:
            error_message = f"OpenAI Error: {e}"
            reginald_responses = [
                f"Regrettably, I must inform you that I have encountered a bureaucratic obstruction:\n\n```{error_message}```",
                f"It would seem that a most unfortunate technical hiccup has befallen my faculties:\n\n```{error_message}```",
                f"Ah, it appears I have received an urgent memorandum stating:\n\n```{error_message}```",
                f"I regret to inform you that my usual eloquence is presently obstructed by an unforeseen complication:\n\n```{error_message}```"
            ]
            return random.choice(reginald_responses)

    @commands.command(name="reginald_allowrole", help="Allow a role to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx, role: discord.Role):
        """✅ Grants permission to a role to use Reginald."""
        await self.config.guild(ctx.guild).allowed_role.set(role.id)
        await ctx.send(f"The role `{role.name}` (ID: `{role.id}`) is now allowed to use the Reginald command.")

    @commands.command(name="reginald_disallowrole", help="Remove a role's ability to use the Reginald command")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx):
        """✅ Removes a role's permission to use Reginald."""
        await self.config.guild(ctx.guild).allowed_role.clear()
        await ctx.send("The role's permission to use the Reginald command has been revoked.")
        
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    @commands.command(help="Set the OpenAI API key")
    async def setreginaldcogapi(self, ctx, api_key):
        """Allows an admin to set the OpenAI API key for Reginald."""
        await self.config.guild(ctx.guild).openai_api_key.set(api_key)
        await ctx.send("OpenAI API key set successfully.")

async def setup(bot):
    """✅ Correct async cog setup for Redbot"""
    await bot.add_cog(ReginaldCog(bot))
