import asyncio
from typing import List
import discord
from redbot.core import Config, checks, commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import pagify, box
from redbot.core.utils.antispam import AntiSpam
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate

application_channel_id = 1023172488143839252

class Recruitment(commands.Cog):
    """A cog that lets a user send a membership application."""

    def __init__(self, bot: Red):
        self.bot = bot

    @commands.group(name="application")
    async def application(self, ctx: commands.Context):
        """Send an application using an interactive flow!
        """
        author = ctx.author

        # Check if the command was sent in a direct message to the bot
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("This command can only be used in a direct message to the bot.")
            return

        await self.interactive_application(author)


    async def interactive_application(self, author: discord.Member):
        """Ask the user several questions to create an application."""
        questions = ["What's your name?", "What's your age?", "Why do you want to join our community?"]
        try:
            answers = await self.ask_questions(author, questions)
        except asyncio.TimeoutError:
            await author.send("You took too long to answer. Please try again later.")
            return

        embed = await self.format_application(answers, author)

        # Send the embed to the application channel
        application_channel = self.bot.get_channel(application_channel_id)
        message = await application_channel.send(embed=embed)

        # Add reactions to the message
        reactions = ["✅", "❌", "❓"]
        for reaction in reactions:
            await message.add_reaction(reaction)

        # Send a confirmation message to the author
        await author.send("Thank you for submitting your application!")

    async def format_application(self, answers: List[str], author: discord.Member) -> discord.Embed:
        """Format the application answers into an embed."""
        embed = discord.Embed(title=f"Application from {author.display_name}", color=discord.Color.green())
        embed.add_field(name="Name", value=answers[0])
        embed.add_field(name="Discord ID", value=author.id)
        embed.add_field(name="Age", value=answers[1])
        embed.add_field(name="Reason wishing to become a member:", value=answers[2])
        return embed

    async def ask_questions(self, author: discord.Member, questions: List[str]) -> List[str]:
        """Ask the user several questions and return the answers."""
        answers = []

        for question in questions:
            await author.send(question)
            answer = await self.get_answer(author)
            answers.append(answer.content)

        return answers

    async def get_answer(self, author: discord.Member) -> discord.Message:
        """Wait for the user to send a message."""
        return await self.bot.wait_for(
            "message", check=lambda m: m.author == author and m.guild is None
        )