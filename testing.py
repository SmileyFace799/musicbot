import discord
from discord.ext import tasks, commands
import socket

class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.has_waited = False

    @commands.command(
        brief='This is a test command, don\'t use this',
        help='This is a test command, don\'t use this',
        usage='No, don\'t'
    )
    async def hello(self, ctx, arg1=None, *, arg2=None):
        await ctx.send(f'Hello!\narg1: {arg1}\narg2: {arg2}')

    @commands.is_owner()
    @commands.command(
        brief='Doesn\'t do anything',
        help='Doesn\'t do anything, atleast not for you :)',
        usage='ip'
    )
    async def ip(self, ctx):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        await ctx.author.send(f'||{s.getsockname()[0]}||')
        s.close()

    @tasks.loop(seconds=5)
    async def printer(self):
        if not self.has_waited:
            print('Waiting...')
            self.has_waited = True
            return
        print('Waited')
        self.has_waited = False
        self.printer.cancel()

    @commands.is_owner()
    @commands.command()
    async def dostart(self, ctx):
        self.printer.start()

    @commands.is_owner()
    @commands.command()
    async def dostop(self, ctx):
        self.printer.cancel()
        await ctx.send('Stopped')

def setup(bot):
    bot.add_cog(Test(bot))
