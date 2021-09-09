from discord.ext import commands

class NotFoundException(Exception): pass
class InvalidStateException(Exception): pass
class NoVoiceException(commands.CheckFailure): pass
