from redbot.core import commands

async def list_allowed_roles_logic(ctx):
    """Handles the logic for listing allowed roles."""
    allowed_roles = await ctx.cog.config.guild(ctx.guild).allowed_roles() or []

    # Ensure roles still exist in the server
    valid_roles = [role_id for role_id in allowed_roles if ctx.guild.get_role(role_id)]
    await ctx.cog.config.guild(ctx.guild).allowed_roles.set(valid_roles)

    if not valid_roles:
        await ctx.send("⚠️ No roles are currently allowed to interact with Reginald.")
        return

    role_mentions = [f"<@&{role_id}>" for role_id in valid_roles]
    await ctx.send(f"✅ **Roles with access to Reginald:**\n{', '.join(role_mentions)}")
