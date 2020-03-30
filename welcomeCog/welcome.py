import asyncio
import discord
import json

from redbot.core import Config, checks, commands
from redbot.core.utils.chat_formatting import box, humanize_list, pagify


def fetchMessage(jsonFormat):
    try:
        message=discord.Embed(title=str(jsonFormat['title']), description=''.join(map(str, jsonFormat['description'])), color=hex(jsonFormat['color']))      
        message.set_thumbnail(url=jsonFormat['thumbnail'])
        for field in jsonFormat['fields']:
            if(field['id']!='links'):
                message.add_field(name=field['name'], value=field['value'], inline=field['inline'])
            else:
                message.add_field(name=field['name'], value=''.join(map(str,field['value'])), inline=field['inline'])

        message.set_footer(text=jsonFormat['footer']['text'], icon_url=jsonFormat['footer']['icon_url'])
        return message

    except:
        message=discord.Embed(title="Kanuim", description='', color=hex(jsonFormat['color']))     
        message.add_field(name="Welcome", value='Welcome To Kanuim !', inline=True) 
        return message

class WelcomeCog(commands.Cog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.message = 'test'

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        #try:
            # message = fetchMessage(self.message)
            # await member.send(content=None, embed=message)
            message = 'helloo'
            await member.send(message)
        # except (discord.NotFound, discord.Forbidden):
        #     print(
        #         f'Error Occured! sending a dm to {member.display_name} didnt work !')
