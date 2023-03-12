import asyncio
from typing import Union, List
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

application_channel_id = 1023172488143839252


class Recruitment(commands.Cog):
    """A cog that lets a user send a membership application.

    Users can open an application using `[!]apply`. These are then sent
    to a channel in the server for staff, and the application creator
    gets a DM. Both can be used to communicate.
    """

    def __init__(self, bot):
        self.bot = bot
        self.message: str = ''
        self.active = True

    @commands.group(name="application", usage="[text]", invoke_without_command=True)
    async def application(self, ctx: commands.Context, *, _application: str = ""):
        """Send an application.

        Use without arguments for an interactive application creation flow, or do
        `[p]application [text]` to use it non-interactively.
        """
        author = ctx.author

        # Check if the command was sent in a direct message to the bot
        if not isinstance(ctx.channel, discord.DMChannel):
            await ctx.send("This command can only be used in a direct message to the bot.")
            return

        # If there is no text argument, use an interactive flow
        if not _application:
            # Send a DM to the author to initiate the application
            await author.send("Please answer the following questions to complete your application.")
            questions = ["What's your name?", "What's your age?", "Why do you want to join our community?"]
            answers = []

            # Ask the user the questions
            for question in questions:
                await author.send(question)
                # Wait for the user to respond
                answer = await self.bot.wait_for(
                    "message", check=lambda m: m.author == author and m.guild is None
                )
                answers.append(answer.content)

            # Create an embed with the application information
            application_embed = await format_application(answers, author)

            # Send the embed to the application channel
            application_channel = self.bot.get_channel(application_channel_id)
            await application_channel.send(embed=application_embed)

            # Send a confirmation message to the author
            await author.send("Thank you for submitting your application!")
        else:
            # If there is a text argument, use a non-interactive flow
            application_channel = self.bot.get_channel(application_channel_id)
            await application_channel.send(_application)
            await author.send("Thank you for submitting your application!")

async def format_application(answers: List[str], author: discord.Member) -> discord.Embed:
        embed = discord.Embed(title="Application", color=discord.Color.green())
        embed.add_field(name="Name", value=author.display_name)
        embed.add_field(name="Discord ID", value=author.id)
        embed.add_field(name="Age", value=answers[1])
        embed.add_field(name="Reason for joining", value=answers[2])
        return embed
