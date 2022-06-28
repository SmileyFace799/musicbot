import discord
from discord.ext import commands, tasks
from stuff import *
from exceptions import *

class Cmds:
    def __init__(self, bot):
        self.bot = bot

    async def join(self, member, r_channel=None):
        if type(member) == discord.User:
            member = get_voice_member(member)
        if not member or not member.voice: raise NoVoiceException('Not connected to a voice chat')
        await member.voice.channel.connect()
        make_queue(member.guild, self.bot.loop)
        if r_channel: await r_channel.send('Joined!')

    async def leave(self, member, r_channel=None):
        if type(member) == discord.User:
            member = get_voice_member(member)
        if not member or not member.voice: raise NoVoiceException('Not connected to a voice chat')
        if not member.guild.voice_client: raise InvalidStateException(f'Bot is not connected')
        if member.guild.voice_client.channel != member.voice.channel: raise InvalidStateException('You must be in the same channel as the bot to disconnect it')
        del_queue(member.guild)
        await member.guild.voice_client.disconnect()
        if r_channel: await r_channel.send('Left!')
