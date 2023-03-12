import asyncio
from typing import Union, List, Literal
from datetime import timedelta
from copy import copy
import contextlib
import discord

from redbot.core import Config, checks, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.antispam import AntiSpam
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate
from redbot.core.utils.tunnel import Tunnel



class Recruitment(commands.Cog):
    """Create user applications that server staff can respond to.

    Users can open an application using `[p]apply`. These are then sent
    to a channel in the server for staff, and the application creator
    gets a DM. Both can be used to communicate.
    """

    default_guild_settings = {"output_channel": None, "active": False, "next_application": 1}

    default_application = {"apply": {}}

    # This can be made configurable later if it
    # becomes an issue.
    # Intervals should be a list of tuples in the form
    # (period: timedelta, max_frequency: int)
    # see redbot/core/utils/antispam.py for more details

    intervals = [
        (timedelta(seconds=5), 1),
        (timedelta(minutes=5), 3),
        (timedelta(hours=1), 10),
        (timedelta(days=1), 24),
    ]

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 42631423034200142, force_registration=True)
        self.config.register_guild(**self.default_guild_settings)
        self.antispam = {}
        self.user_cache = []
        self.tunnel_store = {}

        # (guild, ticket#):
        #   {'tun': Tunnel, 'msgs': List[int]}

    @property
    def tunnels(self):
        return [x["tun"] for x in self.tunnel_store.values()]

    @checks.admin_or_permissions(manage_guild=True)
    @commands.guild_only()
    @commands.group(name="applicationset")
    async def applicationset(self, ctx: commands.Context):
        """+++Manage Applications+++"""
        pass

    @checks.admin_or_permissions(manage_guild=True)
    @applicationset.command(name="output")
    async def reportset_output(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Set the channel where applications will be sent."""
        await self.config.guild(ctx.guild).output_channel.set(channel.id)
        await ctx.send(_("The application channel has been set."))

    @checks.admin_or_permissions(manage_guild=True)
    @applicationset.command(name="toggle", aliases=["toggleactive"])
    async def applicationset_toggle(self, ctx: commands.Context):
        """Enable or disable applications for this server."""
        active = await self.config.guild(ctx.guild).active()
        active = not active
        await self.config.guild(ctx.guild).active.set(active)
        if active:
            await ctx.send(_("Applications are now enabled"))
        else:
            await ctx.send(_("Applications are now disabled"))

    async def internal_filter(self, m: discord.Member, mod=False, perms=None):
        if perms and m.guild_permissions >= perms:
            return True
        if mod and await self.bot.is_mod(m):
            return True
        # The following line is for consistency with how perms are handled
        # in Red, though I'm not sure it makes sense to use here.
        if await self.bot.is_owner(m):
            return True

    async def discover_guild(
        self,
        author: discord.User,
        *,
        mod: bool = False,
        permissions: Union[discord.Permissions, dict] = None,
        prompt: str = "",
    ):
        """
        discovers which of shared guilds between the bot
        and provided user based on conditions (mod or permissions is an or)

        prompt is for providing a user prompt for selection
        """
        shared_guilds = []
        if permissions is None:
            perms = discord.Permissions()
        elif isinstance(permissions, discord.Permissions):
            perms = permissions
        else:
            perms = discord.Permissions(**permissions)

        async for guild in AsyncIter(self.bot.guilds, steps=100):
            x = guild.get_member(author.id)
            if x is not None:
                if await self.internal_filter(x, mod, perms):
                    shared_guilds.append(guild)
        if len(shared_guilds) == 0:
            raise ValueError("No Qualifying Shared Guilds")
        if len(shared_guilds) == 1:
            return shared_guilds[0]
        output = ""
        guilds = sorted(shared_guilds, key=lambda g: g.name)
        for i, guild in enumerate(guilds, 1):
            output += "{}: {}\n".format(i, guild.name)
        output += "\n{}".format(prompt)

        for page in pagify(output, delims=["\n"]):
            await author.send(box(page))

        try:
            message = await self.bot.wait_for(
                "message",
                check=MessagePredicate.same_context(channel=author.dm_channel, user=author),
                timeout=45,
            )
        except asyncio.TimeoutError:
            await author.send(_("You took too long to select. Try again later."))
            return None

        try:
            message = int(message.content.strip())
            guild = guilds[message - 1]
        except (ValueError, IndexError):
            await author.send(_("That wasn't a valid choice."))
            return None
        else:
            return guild

    async def send_application(self, ctx: commands.Context, msg: discord.Message, guild: discord.Guild):
        author = guild.get_member(msg.author.id)
        application = msg.clean_content

        channel_id = await self.config.guild(guild).output_channel()
        channel = guild.get_channel(channel_id)
        if channel is None:
            return None

        files: List[discord.File] = await Tunnel.files_from_attach(msg)

        application_number = await self.config.guild(guild).next_application()
        await self.config.guild(guild).next_application.set(application_number + 1)

        if await self.bot.embed_requested(channel):
            em = discord.Embed(description=application, colour=await ctx.embed_colour())
            em.set_author(
                name=_("Application from {author}{maybe_nick}").format(
                    author=author, maybe_nick=(f" ({author.nick})" if author.nick else "")
                ),
                icon_url=author.display_avatar,
            )
            em.set_footer(text=_("Application #{}").format(application_number))
            send_content = None
        else:
            em = None
            send_content = _("Application from {author.mention} (Application #{number})").format(
                author=author, number=application_number
            )
            send_content += "\n" + application

        try:
            await Tunnel.message_forwarder(
                destination=channel, content=send_content, embed=em, files=files
            )
        except (discord.Forbidden, discord.HTTPException):
            return None

        return application_number

    @commands.group(name="Application", usage="[text]", invoke_without_command=True)
    async def application(self, ctx: commands.Context, *, _application: str = ""):
        """Send an application.

        Use without arguments for an interactive experience, or do
        `[p]apply [text]` to use it non-interactively.
        """
        author = ctx.author
        guild = ctx.guild
        if guild is None:
            guild = await self.discover_guild(
                author, prompt=_("Select a server to make an application in by number.")
            )
        if guild is None:
            return
        g_active = await self.config.guild(guild).active()
        if not g_active:
            return await author.send(_("Applications are currently closed"))
        if guild.id not in self.antispam:
            self.antispam[guild.id] = {}
        if author.id not in self.antispam[guild.id]:
            self.antispam[guild.id][author.id] = AntiSpam(self.intervals)
        if self.antispam[guild.id][author.id].spammy:
            return await author.send(
                _(
                    "You've sent too many applications recently. "
                    "Are you sure you are in the right place? "
                )
            )
        if author.id in self.user_cache:
            return await author.send(
                _(
                    "Please finish making your prior application before trying to make an "
                    "additional one!"
                )
            )
        self.user_cache.append(author.id)

        if _application:
            _m = copy(ctx.message)
            _m.content = _application
            _m.content = _m.clean_content
            val = await self.send_application(ctx, _m, guild)
        else:
            try:
                await author.send(
                    _(
                        "Please respond to this message with your application."
                        "\nYour application should be a single message"
                    )
                )
            except discord.Forbidden:
                return await ctx.send(_("This requires DMs enabled."))

            try:
                message = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.same_context(ctx, channel=author.dm_channel),
                    timeout=180,
                )
            except asyncio.TimeoutError:
                return await author.send(_("You took too long. Try again later."))
            else:
                val = await self.send_application(ctx, message, guild)
                # Get the role to assign using its ID
                trialRole_id = 531181363420987423 
                role = get(ctx.guild.roles, id=trialRole_id)

                # Assign the role to the user who sent the application
                if role is not None:
                    await author.add_roles(role)

        with contextlib.suppress(discord.Forbidden, discord.HTTPException):
            if val is None:
                if await self.config.guild(ctx.guild).output_channel() is None:
                    await author.send(
                        _(
                            "Hmm, most embarrassing, it rather seems Hatt has neglected to tell me where the applications room is. Please contact him for me."
                        )
                    )
                else:
                    await author.send(
                        _("Drat! There was an error sending your application, please contact Hatt.")
                    )
            else:
                await author.send(_("Your application was submitted. (Application #{})").format(val))
                self.antispam[guild.id][author.id].stamp()

    @application.after_invoke
    async def application_cleanup(self, ctx: commands.Context):
        """
        The logic is cleaner this way
        """
        if ctx.author.id in self.user_cache:
            self.user_cache.remove(ctx.author.id)
        if ctx.guild and ctx.invoked_subcommand is None:
            if ctx.bot_permissions.manage_messages:
                try:
                    await ctx.message.delete()
                except discord.NotFound:
                    pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        to_remove = []

        for k, v in self.tunnel_store.items():
            guild, application_number = k
            if await self.bot.cog_disabled_in_guild(self, guild):
                to_remove.append(k)
                continue

            topic = _("Re: application# {application_number} in {guild.name}").format(
                application_number=application_number, guild=guild
            )
            # Tunnels won't forward unintended messages, this is safe
            msgs = await v["tun"].communicate(message=message, topic=topic)
            if msgs:
                self.tunnel_store[k]["msgs"] = msgs

        for key in to_remove:
            if tun := self.tunnel_store.pop(key, None):
                guild, application = key
                await tun["tun"].close_because_disabled(
                    _(
                        "Correspondence about application# {application_number} in "
                        "{guild.name} has been ended due "
                        "to applications being closed."
                    ).format(application_number=application, guild=guild)
                )