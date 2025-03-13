from redbot.core import commands
import discord

class PermissionsMixin:
    """Handles role-based access control for Reginald."""

    @commands.command(name="reginald_list_roles", help="List roles that can interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def list_allowed_roles(self, ctx: commands.Context):
        """Lists all roles that are allowed to interact with Reginald."""
        allowed_roles = await self.config.guild(ctx.guild).allowed_roles() or []

        # Ensure all roles still exist in the server
        valid_roles = [role_id for role_id in allowed_roles if ctx.guild.get_role(role_id)]
        if valid_roles != allowed_roles:  # Update config only if there's a difference
            await self.config.guild(ctx.guild).allowed_roles.set(valid_roles)

        if not valid_roles:
            await ctx.send("⚠️ No roles are currently allowed to interact with Reginald.")
            return

        role_mentions = [f"<@&{role_id}>" for role_id in valid_roles]
        await ctx.send(f"✅ **Roles with access to Reginald:**\n{', '.join(role_mentions)}")

    @commands.command(name="reginald_allowrole", help="Grant a role permission to interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def allow_role(self, ctx: commands.Context, role: discord.Role):
        """Grants a role permission to interact with Reginald."""
        async with self.config.guild(ctx.guild).allowed_roles() as allowed_roles:
            if role.id not in allowed_roles:
                allowed_roles.append(role.id)
                await ctx.send(f"✅ Role **{role.name}** has been granted access to Reginald.")
            else:
                await ctx.send(f"⚠️ Role **{role.name}** already has access.")

    @commands.command(name="reginald_disallowrole", help="Revoke a role's access to interact with Reginald.")
    @commands.has_permissions(administrator=True)
    async def disallow_role(self, ctx: commands.Context, role: discord.Role):
        """Revokes a role's permission to interact with Reginald."""
        async with self.config.guild(ctx.guild).allowed_roles() as allowed_roles:
            if role.id in allowed_roles:
                allowed_roles.remove(role.id)
                await ctx.send(f"❌ Role **{role.name}** has been removed from Reginald's access list.")
            else:
                await ctx.send(f"⚠️ Role **{role.name}** was not in the access list.")
