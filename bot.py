import discord
from discord.ext import commands
from exceptions import *
import json
import re
from traceback import print_tb
import requests

class Active_Bot:
    def __init__(self, name):
        self.name = name
        with open('./login.json') as l:
            login = json.load(l)[name.lower()]
        self.token = login['token']
        self.prefix = login['prefix']
with open('./active.txt') as a:
    active = Active_Bot(a.read().strip('\n'))

cmd_order = {
    'playlist': ('view', 'create', 'delete', 'add', 'remove', 'play', 'quickplay', 'import')
}
class MyHelpCommand(commands.HelpCommand):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.usage_desc = '\nUsage guide:\n* - Argument is optional\n| - Choose one of the specified arguments'

    def desc(self):
        return f'''Use `{self.clean_prefix}help [command]` for more info on a command.
        You can also use `{self.clean_prefix}help [category]` for more info on a category.
        *Note: The category or command you enter will be case sensitive. I don't know how to change that*'''

    async def send_bot_help(self, mapping):
        e = discord.Embed(title=f'{active.name.upper()} HELP', color=discord.Color.blurple(), description=self.desc())
        for cog in mapping:
            e.add_field(name=cog.qualified_name if cog else 'No category', value='\n'.join(f'**-** {command.name}' for command in mapping[cog]), inline=False)
        await self.get_destination().send(embed=e)

    async def send_cog_help(self, cog):
        e = discord.Embed(title=f'{cog.qualified_name.upper()} CATEGORY HELP', color=discord.Color.blurple(), description=self.desc())
        for command in cog.get_commands():
            e.add_field(name=command.name, value=command.brief, inline=False)
        await self.get_destination().send(embed=e)

    async def send_group_help(self, group):
        e = discord.Embed(title=f'{group.name.upper()} COMMAND HELP', color=discord.Color.blurple(), description=group.help)
        e.add_field(name='Usage:', value=self.clean_prefix + group.usage, inline=False)
        e.add_field(name=f'**{group.name.upper()} SUBCOMMANDS**', value=f'{self.desc()}', inline=False)
        for subcommand in sorted(group.commands, key=lambda command: cmd_order[group.name].index(command.name) if group.name in cmd_order and command.name in cmd_order[group.name] else 9999):
            e.add_field(name=f'{group.name} {subcommand.name}', value=subcommand.brief, inline=False)
        e.set_footer(text=self.usage_desc)
        await self.get_destination().send(embed=e)

    async def send_command_help(self, command):
        e = discord.Embed(title=f'{command.name.upper()} COMMAND HELP', color=discord.Color.blurple(), description=command.help)
        e.add_field(name='Usage:', value=self.clean_prefix + command.usage, inline=False)
        e.set_footer(text=self.usage_desc)
        await self.get_destination().send(embed=e)

bot = commands.Bot(command_prefix=active.prefix, case_insensitive=True, intents=discord.Intents.all(), help_command=MyHelpCommand(verify_checks=None))

exts = ('music', 'playlist', 'testing')
for ext in exts:
    bot.load_extension(ext)

@bot.event
async def on_ready():
    print(f'{active.name} is ready')
    music_cog = bot.get_cog('Music')
    music_cog.online_player_url = 'http://192.168.50.197/devbot/' if active.name == 'WeeBot' else 'https://smiles.itzfaded.page/bot/'
    try: requests.get(music_cog.online_player_url + 'player.json')
    except: music_cog.con = False
    else:
        music_cog.con = True
        requests.post(music_cog.online_player_url + 'save-to-log.php', data={'jsonTxt': '{}'})
        if not music_cog.online_player.is_running():
            music_cog.online_player.start()
    print(('C' if music_cog.con else 'Not c') + 'onnected to online player')

@bot.event
async def on_message(msg):
    if msg.content.startswith(active.prefix) and msg.author.id == 549302960601956363 and msg.channel.id != 777639867974680577 and msg.guild and msg.guild.id == 777638039391698995:
        await msg.channel.send(f'Haven\'t we told you to place bot comands in {msg.guild.get_channel(777639867974680577).mention}? that should be obvious. You bot spamming, ass looking command spewing sun of a gun. What absolute ass shittery, who even does something like that, you chat littering bitch ass looking dipshit')
        return
    await bot.process_commands(msg)

@bot.event
async def on_command_error(ctx, e):
    if isinstance(e, commands.CheckFailure):
        await ctx.send(f'{type(e).__name__}: {e}')
    else:
        await ctx.send(str(e))
    raise e

bot.run(active.token)
