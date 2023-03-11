import aiohttp
import discord
import json

from redbot.core import Config, commands

url = 'https://raw.githubusercontent.com/Kanium/KaniumCogs/master/welcomeCog/data/embedded_message.json'

allowed_guilds = {274657393936302080, 693796372092289024, 508781789737648138}
admin_roles = {'Developer', 'admin', 'Council'}
access_roles = {'HasAcceptedKaniumTerms'}


class WelcomeCog(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.message: str = ''
        self.active = True

    @staticmethod
    async def fetchMessage():
        async def fetch():
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    html = await response.text()
                    x = json.loads(str(html))
                    return x
        return await fetch()

    @staticmethod
    def formatMessage(jsonFormat: str):
        try:
            message = discord.Embed(title=str(jsonFormat['title']), description=''.join(
                map(str, jsonFormat['description'])), color=int(jsonFormat['color'], 16))
            message.set_thumbnail(url=jsonFormat['thumbnail'])
            for field in jsonFormat['fields']:
                if (field['id'] != 'links'):
                    message.add_field(
                        name=field['name'], value=field['value'], inline=field['inline'])
                else:
                    message.add_field(name=field['name'], value=''.join(
                        map(str, field['value'])), inline=field['inline'])

            message.set_footer(
                text=jsonFormat['footer']['text'], icon_url=jsonFormat['footer']['icon_url'])
            return message

        except:
            message = discord.Embed(
                title='Kanium', description='', color=0x3399ff)
            message.add_field(
                name='Welcome', value='Welcome To Kanium !', inline=True)
            return message

    @commands.command(name='pullmessage', description='pulls the message from github again')
    @commands.has_any_role(*admin_roles)
    async def pullMessage(self, ctx: commands.Context) -> None:
        try:
            await ctx.trigger_typing()
            self.message = await WelcomeCog.fetchMessage()
            await ctx.send('Welcome message updated')
        except:
            print('error occured fetching message')

    @commands.command(name='welcomepreview', case_insensitive=True, description='Shows a preview of the welcome message')
    @commands.has_any_role(*admin_roles)
    async def previewMessage(self, ctx: commands.Context) -> None:
        try:
            await ctx.trigger_typing()
            if ctx.guild.id not in allowed_guilds:
                return
            if self.message == '':
                self.message = await WelcomeCog.fetchMessage()
            message = WelcomeCog.formatMessage(self.message)
            await ctx.send(content=None, embed=message)
        except ():
            print(f'Error Occured!')

    @commands.command(name='dmWelcomeMessage', case_insensitive=True, description='Sends')
    @commands.has_any_role(*access_roles)
    async def dmWelcomeMessage(self, ctx: commands.Context) -> None:
        try:
            await ctx.trigger_typing()
            if ctx.guild.id not in allowed_guilds:
                return
            if self.message == '':
                self.message = await WelcomeCog.fetchMessage()
            message = WelcomeCog.formatMessage(self.message)
            await ctx.author.send(content=None, embed=message)
        except ():
            print(f'Error Occured!')

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        try:
            if not self.active:  # Check if the listener is active
                return
            if member.guild.id not in allowed_guilds:
                return
            if self.message == '':
                self.message = await WelcomeCog.fetchMessage()
            message = WelcomeCog.formatMessage(self.message)
            await member.send(content=None, embed=message)
        except (discord.NotFound, discord.Forbidden):
            print(
                f'Error Occured! sending a dm to {member.display_name} didnt work !')
    
    @commands.command(name='togglewelcome', case_insensitive=True, description='Toggles the welcome message listener')
    @commands.has_any_role(*admin_roles)
    async def toggleWelcome(self, ctx: commands.Context) -> None:
        self.active = not self.active
        await ctx.send(f'Welcome message listener {"activated" if self.active else "deactivated"}')
