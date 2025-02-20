import discord
from redbot.core import Config, commands
from datetime import datetime
import pytz

class TrafficCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=123456789, force_registration=True)
        default_guild = {
            "traffic_channel": None,
            "daily_stats": {"joined": 0, "left": 0, "banned": 0},
            "total_stats": {"joined": 0, "left": 0, "banned": 0},
            "last_reset": datetime.now(pytz.UTC).isoformat(),
            "admin_roles": ['Developer', 'admin', 'Council'],
            "stats_thumbnail_url": 'https://example.com/default-thumbnail.png',
        }
        self.config.register_guild(**default_guild)

    async def _check_reset(self, guild_id):
        async with self.config.guild_from_id(guild_id).all() as guild_data:
            last_reset = datetime.fromisoformat(guild_data.get('last_reset', datetime.now(pytz.UTC).isoformat()))
            if last_reset.date() < datetime.now(pytz.UTC).date():
                guild_data['daily_stats'] = {"joined": 0, "left": 0, "banned": 0}
                guild_data['last_reset'] = datetime.now(pytz.UTC).isoformat()

    async def _update_stat(self, guild_id, stat_type):
        async with self.config.guild_from_id(guild_id).all() as guild_data:
            guild_data['daily_stats'][stat_type] += 1
            guild_data['total_stats'][stat_type] += 1

    @commands.group(name='traffic', invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def traffic_commands(self, ctx):
        """Base command for managing TrafficCog settings."""
        await ctx.send_help(ctx.command)

    @traffic_commands.command(name='setchannel')
    async def set_traffic_channel(self, ctx, channel: discord.TextChannel):
        """Sets the channel for traffic logs."""
        await self.config.guild(ctx.guild).traffic_channel.set(channel.id)
        await ctx.send(f"Traffic logs will now be sent to {channel.mention}.")

    @traffic_commands.command(name='stats')
    async def show_stats(self, ctx):
        """Displays current traffic statistics."""
        await self._check_reset(ctx.guild.id)
    
        guild_data = await self.config.guild(ctx.guild).all()
        daily_stats = guild_data.get('daily_stats', {"joined": 0, "left": 0, "banned": 0})
        total_stats = guild_data.get('total_stats', {"joined": 0, "left": 0, "banned": 0})
        thumbnail_url = guild_data.get('stats_thumbnail_url', 'https://example.com/default-thumbnail.png')

        embed = discord.Embed(title="Server Traffic Stats", description="Statistics on server activity", color=0x3399ff)
        embed.set_thumbnail(url=thumbnail_url)
        embed.add_field(name="Daily Joined", value=daily_stats['joined'], inline=True)
        embed.add_field(name="Daily Left", value=daily_stats['left'], inline=True)
        embed.add_field(name="Daily Banned", value=daily_stats['banned'], inline=True)
        embed.add_field(name="Total Joined", value=total_stats['joined'], inline=True)
        embed.add_field(name="Total Left", value=total_stats['left'], inline=True)
        embed.add_field(name="Total Banned", value=total_stats['banned'], inline=True)

        await ctx.send(embed=embed)

    @commands.Cog.listener()
    async def on_member_join(self, member):
        await self._check_reset(member.guild.id)
        await self._update_stat(member.guild.id, 'joined')

        channel_id = await self.config.guild(member.guild).traffic_channel()
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id) or await member.guild.fetch_channel(channel_id)
        if channel:
            await channel.send(f"{member.display_name} has joined the server.")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        await self._check_reset(member.guild.id)
        await self._update_stat(member.guild.id, 'left')

        channel_id = await self.config.guild(member.guild).traffic_channel()
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id) or await member.guild.fetch_channel(channel_id)
        if channel:
            await channel.send(f"{member.display_name} has left the server.")

    @commands.Cog.listener()
    async def on_member_ban(self, guild, member):
        await self._check_reset(guild.id)
        await self._update_stat(guild.id, 'banned')

        channel_id = await self.config.guild(guild).traffic_channel()
        if not channel_id:
            return
        channel = guild.get_channel(channel_id) or await guild.fetch_channel(channel_id)
        if channel:
            await channel.send(f"{member.display_name} has been banned from the server.")
