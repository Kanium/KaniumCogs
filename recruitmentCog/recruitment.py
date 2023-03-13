import asyncio
from typing import List
import discord
from redbot.core import Config, checks, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.antispam import AntiSpam
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate

guild_id = 274657393936302080
application_channel_id = 1023172488143839252

class Recruitment(commands.Cog):
    """A cog that lets a user send a membership application."""

    def __init__(self, bot: Red):
        self.bot = bot
        self.message: str = ''


    @commands.group(name="application", usage="[text]", invoke_without_command=True)
    async def application(self, ctx: commands.Context, *, _application: str = ""):
        author = ctx.author
        if await self.is_direct_message(ctx):
            await self.interactive_application(author)


    async def is_direct_message(self, ctx: commands.Context) -> bool:
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("This command can only be used in a direct message to the bot.")
            return False
        return True

    async def interactive_application(self, author: discord.Member):
        """Ask the user several questions to create an application."""
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
        guild = self.bot.get_guild(guild_id)
        member = guild.get_member(author.id)
        if member is None:
            await author.send("You need to join the server before your application can be processed.")
            return

        # Send the embed to the application channel
        application_channel = self.bot.get_channel(application_channel_id)
        message = await application_channel.send(embed=embeddedApplication)

        # Add reactions to the message
        await self.add_reactions(message)

        # Assign the Trial role to the author
        role = guild.get_role(531181363420987423)
        await member.add_roles(role)

        await author.send("Thank you for submitting your application! You have been given the 'Trial' role.")


    async def add_reactions(self, message: discord.Message):
        reactions = ["✅", "❌", "❓"]
        for reaction in reactions:
            await message.add_reaction(reaction)

    async def format_application(self, answers: List[str], author: discord.Member) -> discord.Embed:
        """Format the application answers into an embed."""
        embed = discord.Embed(title=f"Application from {author.display_name}", color=discord.Color.green())
        embed.set_thumbnail(url=author.avatar_url)
        embed.add_field(name="Name", value=answers[0])
        embed.add_field(name="Age", value=answers[1])
        embed.add_field(name="Country", value=answers[2])
        embed.add_field(name="Hobbies", value=answers[3])
        embed.add_field(name="Here for particular game?", value=answers[4])
        embed.add_field(name="Motivation for wanting to join:", value=answers[5])
    
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
                answer = await asyncio.wait_for(self.get_answers(author), timeout=60.0)
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