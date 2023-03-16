import asyncio
import datetime
import re
from typing import List
from datetime import timedelta

import discord
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.utils.antispam import AntiSpam


def sanitize_input(input_text: str) -> str:
    """Sanitize input to remove mentions, links, and special characters."""
    sanitized_text = re.sub(r'<@!?&?(\d+)>', '', input_text)
    sanitized_text = re.sub(r'http\S+', '', sanitized_text)
    sanitized_text = re.sub(r'([^\w\s.,?!`~@#$%^&*()_+=-])', '', sanitized_text)
    return sanitized_text


class Recruitment(commands.Cog):
    """A cog that lets a user send a membership application."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.message: str = ''
        self.config = Config.get_conf(self, identifier=101101101101001110101)  # Replace with your own unique identifier
        default_guild = {"guild_id": 274657393936302080, "application_channel_id": None}
        self.config.register_guild(**default_guild)
        self.antispam = {}

    async def cog_check(self, ctx: commands.Context):
        if await ctx.bot.is_admin(ctx.author):
            return True

        guild_id = ctx.guild.id
        if guild_id not in self.antispam:
            self.antispam[guild_id] = AntiSpam([(datetime.timedelta(hours=1), 1)])
        antispam = self.antispam[guild_id]

        if antispam.spammy:
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass
            await ctx.author.send("Please wait for an hour before sending another application.")
            return False

        antispam.stamp()
        return True


    @commands.guild_only()
    @checks.admin_or_permissions(manage_guild=True)
    @commands.group(name="setapplicationschannel", pass_context=True, no_pm=True)
    async def setapplicationschannel(self, ctx: commands.Context):
        """Set the channel where applications will be sent."""
        if ctx.invoked_subcommand is None:
            guild = ctx.guild
            channel = ctx.channel
            await self.config.guild(guild).guild_id.set(guild.id)
            await self.config.guild(guild).application_channel_id.set(channel.id)
            await ctx.send(f"Application channel set to {channel.mention}.")

    @setapplicationschannel.command(name="clear")
    async def clear_application_channel(self, ctx: commands.Context):
        """Clear the current application channel."""
        guild = ctx.guild
        await self.config.guild(guild).clear_raw("application_channel_id")
        await ctx.send("Application channel cleared.")

    @commands.group(name="application", usage="[text]", invoke_without_command=True)
    async def application(self, ctx: commands.Context, *, _application: str = ""):
        # Input validation and sanitization for _application
        _application = sanitize_input(_application)
        if len(_application) > 2000:
            await ctx.send("Your application is too long. Please limit it to 2000 characters.")
            return

        guild_id = await self.get_guild_id(ctx)
        guild = discord.utils.get(self.bot.guilds, id=guild_id)
        if guild is None:
            await ctx.send(f"The guild with ID {guild_id} could not be found.")
            return

        author = ctx.author
        if author.guild != guild:
            await ctx.send(f"You need to be in the {guild.name} server to submit an application.")
            return

        if await self.check_author_is_member_and_channel_is_dm(ctx):
            await self.interactive_application(author)

    async def get_guild_id(self, ctx: commands.Context) -> int:
        guild_id = await self.config.guild(ctx.author.guild).guild_id()
        return guild_id

    async def check_author_is_member_and_channel_is_dm(self, ctx: commands.Context) -> bool:
        if not isinstance(ctx.author, discord.Member):
            await ctx.send("You need to join the server before your application can be processed.")
            return False
        if not isinstance(ctx.channel, discord.DMChannel):
            try:
                await ctx.message.delete()
            except:
                pass
            await self.interactive_application(ctx)
            return False
        return True


    async def interactive_application(self, ctx: commands.Context):
        """Ask the user several questions to create an application."""
        author = ctx.author
        embed = discord.Embed(
            title="+++ KANIUM APPLICATION SYSTEM +++",
            description="Ah, you wish to apply for Kanium membership. Very well, understand that This process is very important to us so we expect you to put effort in and be glorious about it. Let us begin!",
            color=discord.Color.green(),
        )
        await author.send(embed=embed)

        answers = await self.ask_questions(author)

        if not answers:
            return

        embeddedApplication = await self.format_application(answers, author)
        
        # Call the sendApplication to check if the author is a member of the guild and send the application if they are
        await self.sendApplication(author, embeddedApplication)


    async def sendApplication(self, author: discord.Member, embeddedApplication: discord.Embed):
        # Check if the author is a member of the guild
        guild = author.guild
        member = guild.get_member(author.id)
        if member is None:
            await author.send("You need to join the server before your application can be processed.")
            return

        # Send the embed to the application channel
        application_channel_id = await self.config.guild(guild).application_channel_id()
        if not application_channel_id:
            await author.send("The application channel has not been set. Please use the `setapplicationschannel` command to set it.")
            return

        application_channel = guild.get_channel(application_channel_id)
        if application_channel is None:
            await author.send(f"The application channel with ID {application_channel_id} could not be found.")
            return

        try:
            message = await application_channel.send(embed=embeddedApplication)
        except discord.Forbidden:
            await author.send("I do not have permission to send messages in the application channel.")
            return

        # Add reactions to the message
        try:
            await self.add_reactions(message)
        except discord.Forbidden:
            await author.send("I do not have permission to add reactions to messages in the application channel.")
            return

        # Assign the Trial role to the author
        role = guild.get_role(531181363420987423)
        try:
            await member.add_roles(role)
        except discord.Forbidden:
            await author.send("I do not have permission to assign roles.")
            return

        await author.send("Thank you for submitting your application! You have been given the 'Trial' role.")


    async def add_reactions(self, message: discord.Message):
        reactions = ["✅", "❌", "❓"]
        for reaction in reactions:
            await message.add_reaction(reaction)

    async def format_application(self, answers: List[str], author: discord.Member) -> discord.Embed:
        """Format the application answers into an embed."""
        application_date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trial_end_date = (datetime.datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")

        embed = discord.Embed(title=f"Application from {author.name}#{author.discriminator}", color=discord.Color.green())
        embed.set_thumbnail(url=author.avatar_url)
        embed.add_field(name="Name", value=answers[0])
        embed.add_field(name="Age", value=answers[1])
        embed.add_field(name="Country", value=answers[2])
        embed.add_field(name="Hobbies", value=answers[3])
        embed.add_field(name="Specific game?", value=answers[4])
        embed.add_field(name="\u200b", value="\u200b")  # Empty field for spacing
        embed.add_field(name="Motivation for wanting to join:", value=answers[5], inline=False)
        embed.set_footer(text=f"Application received: {application_date}, Trial ends: {trial_end_date}")
    
        return embed

    async def ask_questions(self, author: discord.Member) -> List[str]:
        """Ask the user several questions and return the answers."""
        questions = [
            "First of all, what is your name?",
            "What age are you?",
            "Where are you from?",
            "Do you have any hobbies?",
            "Are you wishing to join because of a particular game? If so, which game?",
            "Write out, in a free-style way, what your motivation is for wanting to join us in particular and how you would be a good fit for Kanium",
        ]

        answers = []

        for question in questions:
            await author.send(question)

            try:
                answer = await asyncio.wait_for(self.get_answers(author), timeout=300.0)
                answers.append(answer.content)
            except asyncio.TimeoutError:
                await author.send("You took too long to answer. Please start over by using the application command again.")
                return []

        return answers

    async def get_answers(self, author: discord.Member) -> discord.Message:
        """Wait for the user to send a message."""
        return await self.bot.wait_for(
            "message", check=lambda m: m.author == author and m.guild is None
        )   