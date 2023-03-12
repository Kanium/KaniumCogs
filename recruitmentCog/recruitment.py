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
        `[p]apply [text]` to use it non-interactively.
        """
        author = ctx.author

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

            # Combine the answers into a single message and send to the application channel
            application_text = "\n".join([f"{question}: {answer}" for question, answer in zip(questions, answers)])
            application_channel = self.bot.get_channel(application_channel_id)
            await application_channel.send(application_text)

            # Send a confirmation message to the author
            await author.send("Thank you for submitting your application!")
        else:
            # If there is a text argument, use a non-interactive flow
            application_channel = self.bot.get_channel(application_channel_id)
            await application_channel.send(_application)
            await author.send("Thank you for submitting your application!")
