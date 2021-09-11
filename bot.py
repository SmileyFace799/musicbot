import discord
from discord.ext import commands
from exceptions import *
import json
import re
from traceback import print_tb
import socket

class Active_Bot:
    def __init__(self, name):
        self.name = name
        with open('./login.json') as f:
            login = json.load(f)[name.lower()]
        self.token = login['token']
        self.prefix = login['prefix']
active = Active_Bot('WeeBot')

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

exts = ('music', 'playlist')
for ext in exts:
    bot.load_extension(ext)

@bot.event
async def on_ready():
    print('Bot is ready')

@bot.event
async def on_command_error(ctx, e):
    if isinstance(e, commands.CheckFailure):
        await ctx.send(f'{type(e).__name__}: {e}')
    else:
        await ctx.send(str(e))
    raise e

@bot.command(
    brief='This is a test command, don\'t use this',
    help='This is a test command, don\'t use this',
    usage='No, don\'t'
)
async def hello(self, ctx, arg1=None, *, arg2=None):
    await ctx.send(f'Hello!\narg1: {arg1}\narg2: {arg2}')

@commands.is_owner()
@bot.command(
    brief='Doesn\'t do anything',
    help='Doesn\'t do anything, atleast not for you :)',
    usage='ip'
)
async def ip(ctx):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("8.8.8.8", 80))
    await ctx.author.send(f'||{s.getsockname()[0]}||')
    s.close()

#bot.run('NjUxNTYzMjUxODk2OTQyNjAy.XebtkA.5Rp2Ebx5UjwZR62Eotz8r7Hvf9c') #YorthiccBot
#bot.run('NTg1OTU1NzExMzczMjc5MjYx.XPg_yA.f_jmUmoOAftaC_sSiGhVDOaFdTY') #WeeBot
#bot.run('NjM3MDQ1NDg2NDIyOTgyNjc2.XbIc1w.vZrfMy6MG0qxQNPe_HJfm99N8Ps') #WeeBotDev

bot.run(active.token)
