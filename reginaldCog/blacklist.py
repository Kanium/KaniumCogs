from redbot.core import commands
import discord

class BlacklistMixin:
    """Handles user blacklisting for Reginald."""

    async def is_blacklisted(self, user: discord.Member) -> bool:
        """Checks if a user is blacklisted from interacting with Reginald."""
        blacklisted_users = await self.config.guild(user.guild).blacklisted_users()
        return str(user.id) in blacklisted_users

    @commands.command(name="reginald_blacklist", help="List users who are explicitly denied access to Reginald.")
    @commands.has_permissions(administrator=True)
    async def list_blacklisted_users(self, ctx):
        """Lists all users currently blacklisted from interacting with Reginald."""
        blacklisted_users = await self.config.guild(ctx.guild).blacklisted_users()
        if not blacklisted_users:
            await ctx.send("✅ No users are currently blacklisted from interacting with Reginald.")
            return

        user_mentions = [f"<@{user_id}>" for user_id in blacklisted_users]
        await ctx.send(f"🚫 **Blacklisted Users:**\n{', '.join(user_mentions)}")

    @commands.command(name="reginald_blacklist_add", help="Blacklist a user from interacting with Reginald.")
    @commands.has_permissions(administrator=True)
    async def add_to_blacklist(self, ctx, user: discord.User):
        """Adds a user to Reginald's blacklist."""
        async with self.config.guild(ctx.guild).blacklisted_users() as blacklisted_users:
            if str(user.id) not in blacklisted_users:
                blacklisted_users.append(str(user.id))
                await ctx.send(f"🚫 {user.display_name} has been **blacklisted** from interacting with Reginald.")
            else:
                await ctx.send(f"⚠️ {user.display_name} is already blacklisted.")

    @commands.command(name="reginald_blacklist_remove", help="Remove a user from Reginald's blacklist.")
    @commands.has_permissions(administrator=True)
    async def remove_from_blacklist(self, ctx, user: discord.User):
        """Removes a user from Reginald's blacklist."""
        async with self.config.guild(ctx.guild).blacklisted_users() as blacklisted_users:
            if str(user.id) in blacklisted_users:
                blacklisted_users.remove(str(user.id))
                await ctx.send(f"✅ {user.display_name} has been removed from the blacklist.")
            else:
                await ctx.send(f"⚠️ {user.display_name} was not on the blacklist.")
