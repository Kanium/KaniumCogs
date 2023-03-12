import asyncio
from typing import List

import discord
from redbot.core import commands
from redbot.core.utils import AsyncIter
from redbot.core.utils.antispam import AntiSpam
from redbot.core.utils.chat_formatting import box, pagify
from redbot.core.bot import Red
from redbot.core.utils.predicates import MessagePredicate


class Recruitment(commands.Cog):
    """A cog that lets a user send a membership application.

    Users can open an application using `[p]apply`. These are then sent
    to a channel in the server for staff, and the application creator
    gets a DM. Both can be used to communicate.
    """

    def __init__(self, bot: Red):
        self.bot = bot
        self.message: str = ''
        self.active = True
        self.application_channel_id = 1023172488143839252
        self.ask_questions_timeout = 300.0

    @commands.group(name="apply", invoke_without_command=True)
    async def apply(self, ctx: commands.Context):
        """Send a membership application."""
        author = ctx.author

        # Check if the command was sent in a direct message to the bot
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("This command can only be used in a direct message to the bot.")
            return

        # Ask the user the questions and get the answers with a timeout
        questions = ["What's your name?", "What's your age?", "Why do you want to join our community?"]
        try:
            answers = await asyncio.wait_for(self.ask_questions(author, questions), timeout=self.ask_questions_timeout)
        except asyncio.TimeoutError:
            await author.send("You took too long to answer. Please try again later.")
            return

        # Create an embed with the application information
        application_embed = await self.format_application(answers, author)

        # Send the embed to the application channel
        application_channel = self.bot.get_channel(self.application_channel_id)
        await application_channel.send(embed=application_embed)

        # Send a confirmation message to the author
        await author.send("Thank you for submitting your application!")

    async def format_application(self, answers: List[str], author: discord.Member) -> discord.Embed:
        embed = discord.Embed(title=f"Application from {author.display_name}", color=discord.Color.green())
        embed.add_field(name="Name", value=author.name)
        embed.add_field(name="Discord ID", value=author.id)
        embed.add_field(name="Age", value=answers[1])
        embed.add_field(name="Reason wishing to become a member:", value=answers[2])
        return embed

    async def ask_questions(self, author: discord.Member, questions: List[str]) -> List[str]:
        """Ask the user a list of questions and return the answers."""
        answers = []

        # Ask the user the questions
        for question in questions:
            await author.send(question)

            # Wait for the user to respond
            answer = await self.bot.wait_for(
                "message", check=lambda m: m.author == author and m.guild is None
            )
            answers.append(answer.content)

        return answers