import asyncio
import datetime
import re
from typing import Dict, List, Optional

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.antispam import AntiSpam

# Define your application questions and field settings\
QUESTIONS_LIST = [
    {
        "key": "name",
        "prompt": "First of all, what is your name?",
        "field_name": "Name",
        "inline": True,
    },
    {
        "key": "age",
        "prompt": "What age are you?",
        "field_name": "Age",
        "inline": True,
    },
    {
        "key": "country",
        "prompt": "Where are you from?",
        "field_name": "Country",
        "inline": True,
    },
    {
        "key": "hobbies",
        "prompt": "Do you have any hobbies?",
        "field_name": "Hobbies",
        "inline": True,
    },
    {
        "key": "game",
        "prompt": "Are you wishing to join because of a particular game? If so, which game?",
        "field_name": "Specific game?",
        "inline": True,
    },
    {
        "key": "motivation",
        "prompt": "Write out, in a free-style way, what your motivation is for wanting to join us in particular and how you would be a good fit for Kanium",
        "field_name": "Motivation for wanting to join:",
        "inline": False,
    },
]


def sanitize_input(input_text: str) -> str:
    """Sanitize input to remove mentions, links, and unwanted special characters."""
    text = re.sub(r'<@!?(?:&)?\d+>', '', input_text)
    text = re.sub(r'http\S+', '', text)
    # Allow unicode letters and common punctuation
    text = re.sub(r'[^\w\s\p{L}\.,\?!`~@#$%^&*()_+=-]', '', text)
    return text


class Recruitment(commands.Cog):  # noqa
    """A cog that lets a user send a membership application."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xFAB123ABC456)
        default_guild = {"application_channel_id": None}
        self.config.register_guild(**default_guild)
        # antispam store per guild per user
        self.antispam: Dict[int, Dict[int, AntiSpam]] = {}
        self.cog_check_enabled = True

    async def cog_check(self, ctx: commands.Context) -> bool:
        if (
            await ctx.bot.is_admin(ctx.author)
            or not self.cog_check_enabled
            or (ctx.guild and ctx.author.guild_permissions.manage_guild)
            or (ctx.guild and ctx.author.guild_permissions.administrator)
        ):
            return True

        gid = ctx.guild.id
        uid = ctx.author.id
        if gid not in self.antispam:
            self.antispam[gid] = {}
        if uid not in self.antispam[gid]:
            self.antispam[gid][uid] = AntiSpam([(datetime.timedelta(hours=1), 1)])
        spam = self.antispam[gid][uid]
        if spam.spammy:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            try:
                await ctx.author.send("Please wait for an hour before sending another application.")
            except discord.Forbidden:
                pass
            return False
        spam.stamp()
        return True

    @commands.command(name="togglecogcheck")
    @checks.is_owner()
    async def toggle_cog_check(self, ctx: commands.Context) -> None:
        """Toggle the cog_check functionality on or off."""
        self.cog_check_enabled = not self.cog_check_enabled
        await ctx.send(f"Cog checks are now {'enabled' if self.cog_check_enabled else 'disabled'}.")

    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @commands.group(
        name="setapplicationschannel",
        invoke_without_command=True,
    )
    async def set_applications_channel(self, ctx: commands.Context) -> None:
        """Set the channel where applications will be sent."""
        await self.config.guild(ctx.guild).application_channel_id.set(ctx.channel.id)
        await ctx.send(f"Application channel set to {ctx.channel.mention}.")

    @set_applications_channel.command(name="clear")
    async def clear_applications_channel(self, ctx: commands.Context) -> None:
        """Clear the current application channel."""
        await self.config.guild(ctx.guild).clear_raw("application_channel_id")
        await ctx.send("Application channel cleared.")

    @commands.group(name="application", invoke_without_command=True)
    async def application(self, ctx: commands.Context, *, text: Optional[str] = None) -> None:
        """Start an application process."""
        # Direct free-text application (optional)
        if text:
            text = sanitize_input(text)
            if len(text) > 2000:
                await ctx.send("Your application is too long (max 2000 chars).")
                return
        # Determine if in guild or DM
        if isinstance(ctx.channel, discord.DMChannel):
            await self._start_application(ctx.author)
        else:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            try:
                await ctx.author.send(
                    "Let's move this to DM so we can process your application."
                )
            except discord.Forbidden:
                await ctx.send("I cannot DM you. Please enable DMs and try again.")
                return
            await self._start_application(ctx.author)

    async def _start_application(self, member: discord.Member) -> None:
        # Kick off interactive questions
        if not await self._send_embed(
            member,
            title="+++ KANIUM APPLICATION SYSTEM +++",
            description=(
                "This is the process to join Kanium."
                " Please take your time and answer thoughtfully."
            ),
            color=discord.Color.green(),
        ):
            return

        answers = await self.ask_questions(member)
        if not answers:
            return
        embed = self.format_application(answers, member)
        await self.send_application(member, embed)

    async def _send_embed(
        self,
        member: discord.Member,
        *,
        title: str,
        description: str,
        color: discord.Color,
    ) -> bool:
        embed = discord.Embed(title=title, description=description, color=color)
        try:
            await member.send(embed=embed)
            return True
        except discord.Forbidden:
            return False

    async def ask_questions(self, member: discord.Member) -> Optional[Dict[str, str]]:
        """
        Ask each question, let the user confirm their answer,
        and return the final answers (or None on abort).
        """
        answers: Dict[str, str] = {}

        for q in QUESTIONS_LIST:
            prompt = q["prompt"]

            while True:
                # 1) send the question
                try:
                    await member.send(prompt)
                except discord.Forbidden:
                    return None  # can't DM

                # 2) wait for their reply (match on ID, not object)
                try:
                    msg = await asyncio.wait_for(
                        self.bot.wait_for(
                            "message",
                            check=lambda m: (
                                m.author.id == member.id
                                and isinstance(m.channel, discord.DMChannel)
                            )
                        ),
                        timeout=300.0,
                    )
                except asyncio.TimeoutError:
                    await member.send(
                        "You took too long to answer. Please restart the application with `!application`."
                    )
                    return None

                answer = sanitize_input(msg.content)

                # 3) echo back for confirmation
                try:
                    await member.send(f"You answered:\n> {answer}\n\nIs that correct? (yes/no)")
                except discord.Forbidden:
                    return None

                # 4) wait for a yes/no
                try:
                    confirm = await asyncio.wait_for(
                        self.bot.wait_for(
                            "message",
                            check=lambda m: (
                                m.author.id == member.id
                                and isinstance(m.channel, discord.DMChannel)
                                and m.content.lower() in ("y", "yes", "n", "no")
                            )
                        ),
                        timeout=60.0,
                    )
                except asyncio.TimeoutError:
                    await member.send(
                        "Confirmation timed out. Please restart the application with `!application`."
                    )
                    return None

                if confirm.content.lower() in ("y", "yes"):
                    # user confirmed, save and move on
                    answers[q["key"]] = answer
                    break
                else:
                    # user said “no” → repeat this question
                    await member.send("Okay, let's try that again.")

        return answers


    def format_application(
        self, answers: Dict[str, str], member: discord.Member
    ) -> discord.Embed:
        now = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        trial_ends = (
            datetime.datetime.utcnow() + datetime.timedelta(days=30)
        ).strftime("%Y-%m-%d UTC")

        embed = discord.Embed(
            title=f"Application from {member}", color=discord.Color.green()
        )
        embed.set_thumbnail(url=member.avatar.url)
        for q in QUESTIONS_LIST:
            embed.add_field(
                name=q["field_name"],
                value=answers[q["key"]],
                inline=q["inline"],
            )
        embed.set_footer(text=f"Received: {now} | Trial ends: {trial_ends}")
        return embed

    async def send_application(
        self, member: discord.Member, embed: discord.Embed
    ) -> None:
        guild = member.guild
        if guild is None:
            try:
                await member.send("You need to be in the server to apply.")
            except discord.Forbidden:
                pass
            return

        channel_id = await self.config.guild(guild).application_channel_id()
        if not channel_id:
            try:
                await member.send(
                    "Application channel not set. Ask an admin to run `setapplicationschannel`."
                )
            except discord.Forbidden:
                pass
            return

        channel = guild.get_channel(channel_id)
        if not channel:
            try:
                await member.send("Application channel was not found. Please ask an admin to re-set it.")
            except discord.Forbidden:
                pass
            return

        try:
            sent = await channel.send(embed=embed)
            await self.add_reactions(sent)
        except discord.Forbidden:
            try:
                await member.send("I cannot post or react in the application channel.")
            except discord.Forbidden:
                pass
            return

        # Assign Trial role
        role = guild.get_role(531181363420987423)
        if role:
            try:
                await member.add_roles(role)
                await member.send("Thank you! You've been granted the Trial role.")
            except discord.Forbidden:
                try:
                    await member.send("I lack permissions to assign roles.")
                except discord.Forbidden:
                    pass

    @staticmethod
    async def add_reactions(message: discord.Message) -> None:
        for emoji in ("✅", "❌", "❓"):
            await message.add_reaction(emoji)
