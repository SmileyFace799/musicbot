import discord
from discord.ext import commands
from exceptions import *
from urllib.request import urlopen
import re
import pafy
from html import unescape
from random import randint
from platform import system as get_os

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn'}
queues = {}
guild_id = lambda ctx: ctx.guild.id if ctx.guild else None

class Song:
    def __init__(self, id, title=None, artist=None, ctx=None, source_opts=None):
        self.has_ctx = False
        self.has_source = False
        self.id = id
        self.url = 'https://www.youtube.com/watch?v=' + id
        if not (title and artist): html = urlopen(self.url).read().decode()
        self.title = title if title else unescape(re.search('<title>(.*?)</title>', html).group(1)[:-10])
        self.artist = artist if artist else unescape(re.search('<link itemprop="name" content="(.*?)">', html).group(1))
        if ctx: self.add_ctx(ctx)
        if source_opts: self.add_source(source_opts)

    def add_ctx(self, ctx):
        self.channel = ctx.channel
        self.requestant = ctx.author
        self.has_ctx = True
        return self

    def add_source(self, opts):
        pafy_object = pafy.new(self.id)
        audio = pafy_object.getbestaudio()
        url = audio.url
        self.source = discord.FFmpegPCMAudio(url, executable="./ffmpeg.exe", **opts) if get_os().lower().startswith('win') else discord.FFmpegPCMAudio(url, **opts)
        self.has_source = True
        return self

    def copy(self):
        return self.__class__(self.id, self.title, self.artist)

class Queue(list):
    def __init__(self, ctx):
        self.guild = ctx.guild
        self.loop = ctx.bot.loop
        self.skip = False
        self.shuffle = False
        self.repeat = False
        self.repeatqueue = False

    async def play_song(self):
        if not self.vc:
            await self.song.requestant.voice.channel.connect()
        self.vc.play(self.song.source, after=self.after)

    def play(self, announce=True):
        self.skip = False
        self.song.add_source(FFMPEG_OPTIONS)
        self.loop.create_task(self.play_song())
        if announce: self.loop.create_task(self.song.channel.send(f'**Now playing:** {self.song.title} - {self.song.artist}\n**Requested by:** {self.song.requestant.display_name}\n{self.song.url}'))

    def after(self, e):
        if e:
            self.loop.create_task(self.song.channel.send(f'The following error occured when attempting to play {self.song.title}: {e}'))
            self.skip = True
        if self.repeat and not self.skip:
            self.play(announce=False)
        elif len(self) > 1:
            _song = self.pop(0)
            if self.shuffle:
                self.insert(0, self.pop(randint(0, len(self) - 1)))
            if self.repeatqueue:
                self.append(_song)
            self.play()
        else:
            del_queue(self.vc)
            self.loop.create_task(self.vc.disconnect())

    @property
    def song(self): #Songs currently playing / about to be played
        return self[0]

    @property
    def vc(self):
        return self.guild.voice_client

def get_queue(ctx):
    id = guild_id(ctx)
    return queues[id] if id in queues.keys() else None

def make_queue(ctx):
    id = guild_id(ctx)
    if id not in queues.keys(): queues[id] = Queue(ctx)
    return get_queue(ctx)

def del_queue(ctx):
    id = guild_id(ctx)
    if id in queues.keys(): del queues[id]

async def queue_song(ctx, song, queue=None, announce=True):
    song = song.copy()
    if not song.has_ctx: song.add_ctx(ctx)
    if not queue: queue = make_queue(ctx)
    queue.append(song) #Song must have ctx
    if len(queue) == 1:
        queue.play()
    elif announce:
        await ctx.send(f"**Added to queue:** {song.title} - {song.artist}\n**Added by:** {ctx.author.display_name}\n{song.url}")

async def queue_list(ctx, list):
    msg = await ctx.send(f'Queuing playlist...')
    for index, song in enumerate(list):
        await queue_song(ctx, song, announce=False)
    await ctx.send('Playlist queued!')

async def async_queue(ctx):
    return make_queue(ctx)

def vc():
    def predicate(ctx):
        if not ctx.author.voice: raise NoVoiceException('Not connected to a voice chat')
        if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel: raise InvalidStateException(f'Bot is already playing music elsewhere in the server. Use {ctx.prefix}movehere to move it')
        return True
    return commands.check(predicate)

def search_songs(search):
    search = search.replace(' ', '+')
    html = urlopen(f"https://www.youtube.com/results?search_query={search}&sp=EgIQAQ%253D%253D").read().decode().split('"videoRenderer":{"videoId":')
    html.pop(0)
    if not html: raise NotFoundException('No results')
    #ids = re.findall(r"watch\?v=(\S{11})", html)
    #titles = re.findall(r'"title":{"runs":\[{"text":"(.*?)"}\],"accessibility":', html)
    #artists = re.findall('"longBylineText":{"runs":\[{"text":"(.*?)","navigationEndpoint":', html)
    for text in html:
        id = re.search(r"watch\?v=(\S{11})", text).group(1)
        title = re.search(r'"title":{"runs":\[{"text":"(.*?)"}\],"accessibility":', text).group(1)
        artist = re.search('"longBylineText":{"runs":\[{"text":"(.*?)","navigationEndpoint":', text).group(1)
        yield Song(id, title, artist)

def search_playlist(url):
    if not url.startswith('https://www.youtube.com/playlist?list='): raise commands.BadArgument('Please provide a playlist URL')
    html = urlopen(url).read().decode()
    ids = re.findall('{"playlistVideoRenderer":{"videoId":"(.*?)"', html)
    titles = re.findall(r'"title":{"runs":\[{"text":"(.*?)"}\],"accessibility":', html)
    artists = re.findall('"shortBylineText":{"runs":\[{"text":"(.*?)","navigationEndpoint":', html)
    for id, title, artist in zip(ids, titles, artists):
        yield Song(id, title, artist)

async def find_song(ctx, search):
    songs = search_songs(search)
    songs = tuple([next(songs) for i in range(10)])
    _opts = '\n'.join(f'  **{i + 1}:** {song.title} - {song.artist}' for i, song in enumerate(songs))
    id_list_msg = await ctx.send(f'**Results:**\n{_opts}\n\n*Select a song by entering it\'s corresponding number, or "cancel" to cancel*')
    def check(msg):
        if msg.content.startswith(ctx.prefix): msg[len(ctx.prefix):]
        return msg.author == ctx.author and ((msg.content.isdigit() and 0 < int(msg.content) <= len(songs)) or msg.content.lower() == 'cancel')
    try: response = await ctx.bot.wait_for('message', timeout=60, check=check)
    except: await ctx.send('No response received in time, search cancelled')
    else:
        if response.content.startswith(ctx.prefix): msg[len(ctx.prefix):]
        if response.content == 'cancel': await ctx.send('Search cancelled by user')
        else: return songs[int(response.content) - 1]
        if ctx.guild: await response.delete()
    print((ctx.guild, bool(ctx.guild)))
    if ctx.guild: await id_list_msg.delete()
