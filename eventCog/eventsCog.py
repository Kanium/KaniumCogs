import discord
from datetime import datetime

from redbot.core import Config, commands

allowed_guilds = {274657393936302080, 693796372092289024, 508781789737648138}
admin_roles = {'Developer', 'admin', 'Council'}
statsThumbnailUrl = 'https://www.kanium.org/machineroom/logomachine-small.png'

# sqlite3 - local - no server
# json object handler

# events = [{
#     messageid,
#     message,
#     users: [{
#         id:
#         name:
#     }]
# }]

# 1. create embedded message
# 2. add reactions
# 3. on reaction added: manage peoples list
# 4. allow edit
# 5. notification on date. 15 minutes before.

# FLOW: 
# react to a pinned mesasge. 
# recieve a private dm to create the event
# once the private interaction is done create an embedded message into discord channel

class EventsCog(commands.Cog):

    def __init__(self, bot):
        self.channel: discord.TextChannel = None

    @commands.command(name='seteventschannel', description='Sets the channel to sends events to')
    @commands.has_any_role(*admin_roles)
    async def setEventsChannel(self, ctx: commands.Context, channel: discord.TextChannel) -> None:
        await ctx.trigger_typing()

        if not channel in ctx.guild.channels:
            await ctx.send('Channel doesnt exist in guild')
            return

        if not channel.permissions_for(ctx.guild.me).send_messages:
            await ctx.send('No permissions to talk in that channel.')
            return

        self.channel = channel

        await ctx.send(f'I will now send event notices to {channel.mention}.')

    @commands.command(name='removeevent', description='Removes a specific event')
    async def resetStatistics(self, ctx: commands.Context) -> None:
        # check self roles 
        # check self id if not one of the roles ot be the creator if said message. 
        # if neither return odnt do shit.
        # if it is then delete message
        pass

    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, member: discord.Member) -> None:
        # check the reaction check the user add it to the message on the server
        pass

    @commands.Cog.listener()
    async def on_reaction_remove(self, reaction: discord.Reaction, member: discord.Member) -> None:
        # check the reaction check the user remove it to the message on the server
        pass

    #Figure out how to do talk with user in private dm. #ON BILBO TO DO