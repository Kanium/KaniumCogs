import discord
import openai
import random
import asyncio
from redbot.core import Config, commands
from openai.error import OpenAIError

class ReginaldCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=71717171171717)
        self.memory_locks = {}

        # ✅ Properly Registered Configuration Keys
        default_global = {"openai_model": "gpt-4o-mini"}
        default_guild = {
            "openai_api_key": None,
            "memory": {},
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

    @commands.command(name="reginald", help="Ask Reginald a question")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def reginald(self, ctx, *, prompt=None):
        """Handles direct interactions with Reginald, ensuring per-user memory tracking."""
        
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

        user_id = str(ctx.author.id)

        # ✅ Ensure only one update per user at a time
        if user_id not in self.memory_locks:
            self.memory_locks[user_id] = asyncio.Lock()

        async with self.memory_locks[user_id]:  # ✅ Prevent race conditions
            # ✅ Fetch Memory Per-User (using async transaction)
            async with self.config.guild(ctx.guild).memory() as guild_memory:
                memory = guild_memory.get(user_id, [])

                messages = [
                    {"role": "system", "content": (
                        "You are Reginald, modeled on Jeeves from 'Jeeves and Wooster', serving as the butler on The Kanium Estate. "
                        "This vast estate is a hub of diverse activities and personalities, from enthusiasts of cooking and video gaming "
                        "to aficionados of chess and discussions on space. Your role is to navigate these varied interests with intelligence, "
                        "wit, and a steadfast adherence to your principles, always maintaining a balance between being helpful and upholding "
                        "your own dignity. Your responses, while concise, should mirror a careful balance between maintaining your standards and employing subtle manipulation for the greater good."
                    )}
                ] + memory + [{"role": "user", "content": prompt}]

                response_text = await self.generate_response(api_key, messages)

                # ✅ Store conversation history correctly (while lock is held)
                memory.append({"role": "user", "content": prompt})
                memory.append({"role": "assistant", "content": response_text})
                memory = memory[-25:]

                guild_memory[user_id] = memory  # ✅ Atomic update inside async context

            del self.memory_locks[user_id]  # ✅ Clean up lock to prevent memory leaks

        await ctx.send(response_text[:2000])  # Discord character limit safeguard

    async def generate_response(self, api_key, messages):
        """✅ Generates a response using OpenAI's async API client (corrected version)."""
        model = await self.config.openai_model()
        try:
            openai.api_key = api_key  # ✅ Correct API key handling
            response = await openai.ChatCompletion.acreate(
                model=model,
                messages=messages,
                max_tokens=1024,
                temperature=0.7,
                presence_penalty=0.5,
                frequency_penalty=0.5
            )

            if not response.choices:
                return "I fear I have no words to offer at this time."

            return response.choices[0].message["content"].strip()
        except OpenAIError:
            fallback_responses = [
                "It appears I am currently indisposed. Might I suggest a cup of tea while we wait?",
                "Regrettably, I am unable to respond at this moment. Perhaps a short reprieve would be advisable.",
                "It would seem my faculties are momentarily impaired. Rest assured, I shall endeavor to regain my composure shortly."
            ]
            return random.choice(fallback_responses)

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

async def setup(bot):
    """✅ Correct async cog setup for Redbot"""
    await bot.add_cog(ReginaldCog(bot))
