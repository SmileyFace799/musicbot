import discord
from discord.ext import commands
from exceptions import *
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from urllib.request import urlopen
from urllib.parse import quote
import re
import pafy_local as pafy
from html import unescape
from datetime import datetime as dt
from random import randint
from platform import system as get_os

FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5','options': '-vn'}
page_size = 20
queues = {}
guild_id = lambda ctx: ctx.guild.id if ctx.guild else None
sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(client_id='50a7e02b71c24576a259fe1e8b2df078', client_secret='dba494661d2c4812b1d158cd87f54f98'))

youtube_playlist_urls = ('https://www.youtube.com/playlist?list=',)
spotify_album_urls = ('https://open.spotify.com/album/',)
spotify_playlist_urls = ('https://open.spotify.com/playlist/', *spotify_album_urls)
playlist_urls = (*youtube_playlist_urls, *spotify_playlist_urls)
check_urltype = lambda url, url_types: any(filter(lambda url_type: url.startswith(url_type), url_types))

class Song:
    def __init__(self, id, title=None, artist=None, ctx=None, source_opts=None, topic=None):
        self.has_ctx = False
        self.has_source = False
        self.id = id
        self.url = 'https://www.youtube.com/watch?v=' + id
        html = urlopen(self.url).read().decode() if not (title and artist) else None
        self.title = title if title else unescape(re.search('<title>(.*?)</title>', html).group(1)[:-10]).encode('utf-8').decode('unicode-escape') if html else None
        self.artist = artist if artist else unescape(re.search('<link itemprop="name" content="(.*?)">', html).group(1)).encode('utf-8').decode('unicode-escape') if html else None
        if ctx: self.add_ctx(ctx)
        if source_opts: self.add_source(source_opts)

    def add_ctx(self, ctx):
        self.channel = ctx.channel
        self.requestant = ctx.author
        self.has_ctx = True
        return self

    def add_source(self, opts):
        for i in range(5):
            try: pafy_object = pafy.new(self.id)
            except Exception as e:
                print(e)
                if i == 4:
                    self.has_source = None
                    return self
                else: print(f'Unable to play song, trying again ({4 - i} attempts left)')
            else: break
        audio = pafy_object.getbestaudio()
        url = audio.url
        self.source = discord.FFmpegPCMAudio(url, executable="./ffmpeg.exe", **opts) if get_os().lower().startswith('win') else discord.FFmpegPCMAudio(url, **opts)
        self.has_source = True
        return self

    def copy(self):
        return self.__class__(self.id, self.title, self.artist)

class Queue(list):
    def __init__(self, guild, loop):
        self.guild = guild
        self.loop = loop
        self.skip = False
        self.shuffle = False
        self.repeat = False
        self.repeatqueue = False
        self.last_played = dt.now()
        self.next = None

    async def play_song(self):
        if not self.vc:
            await self.song.requestant.voice.channel.connect()
        self.vc.play(self.song.source, after=self.after)

    def play(self, announce=True):
        self.skip = False
        self.song.add_source(FFMPEG_OPTIONS)
        if self.song.has_source == None:
            self.loop.create_task(self.song.channel.send('Failed to play the current song, skipping...'))
            return self.after(None)
        self.loop.create_task(self.play_song())
        if announce: self.loop.create_task(self.song.channel.send(f'**Now playing:** {self.song.title} - {self.song.artist}\n**Requested by:** {self.song.requestant.display_name}\n{self.song.url}'))

    def after(self, e):
        self.last_played = dt.now()
        if e:
            self.loop.create_task(self.song.channel.send(f'The following error occured when attempting to play {self.song.title}: {e}'))
            self.skip = True
        if self.skip and self.next:
            if self.next == 1: pass
            elif self.shuffle:
                _song = self.pop(0)
                self.insert(0, self.pop(self.next - 2))
                if self.repeatqueue: self.append(_song)
            else:
                _songs = self[:self.next - 1]
                del self[:self.next - 1]
                if self.repeatqueue: self.extend(_songs)
            self.play()
            self.next = None
        elif self.repeat and not self.skip:
            self.play(announce=False)
        elif self:
            _song = self.pop(0)
            if self.shuffle and len(self) > 1:
                self.insert(0, self.pop(randint(0, len(self) - 1)))
            if self.repeatqueue:
                self.append(_song)
            if self: self.play()

    @property
    def song(self): #Songs currently playing / about to be played
        return self[0]

    @property
    def vc(self):
        return self.guild.voice_client

def get_queue(guild):
    return queues[guild.id] if guild.id in queues.keys() else None

def make_queue(guild, loop):
    if guild.id not in queues.keys(): queues[guild.id] = Queue(guild, loop)
    return get_queue(guild)

def del_queue(guild):
    if guild.id in queues.keys(): del queues[guild.id]

def get_voice_member(user):
    for guild in user.mutual_guilds:
        for channel in filter(lambda channel: type(channel) == discord.VoiceChannel, guild.channels):
            if user.id in (member.id for member in channel.members):
                return guild.get_member(user.id)

async def queue_song(ctx, song, queue=None, announce=True):
    song = song.copy()
    if not song.has_ctx: song.add_ctx(ctx)
    if not queue: queue = make_queue(ctx.guild, ctx.bot.loop)
    queue.append(song) #Song must have ctx
    if len(queue) == 1:
        queue.play()
    elif announce:
        await ctx.send(f"**Added to queue:** {song.title} - {song.artist}\n**Added by:** {ctx.author.display_name}\n{song.url}")

async def queue_list(ctx, playlist):
    msg = await ctx.send('Queuing playlist... (Songs queued: 0)')
    _count = 0
    _now = dt.now()
    for song in playlist:
        await queue_song(ctx, song, announce=False)
        _count += 1
        if msg and (dt.now() - _now).total_seconds() > 2:
            await msg.edit(content=f'Queuing playlist... (Songs queued: {_count})')
            _now = dt.now()
    await msg.edit(content=f'Queuing playlist... (Songs queued: {_count})')
    await ctx.send('Playlist queued!')

def vc():
    def predicate(ctx):
        if not ctx.author.voice: raise NoVoiceException('Not connected to a voice chat')
        if ctx.voice_client and ctx.voice_client.channel != ctx.author.voice.channel: raise InvalidStateException(f'Bot is already playing music elsewhere in the server. Use {ctx.prefix}movehere to move it')
        return True
    return commands.check(predicate)

def search_songs(search):
    if search.startswith('*') and search.endswith('*'): search = search[1:-1] + ' "auto-generated by YouTube"'
    search = search.replace(' ', '+')
    search = quote(search, safe='+')
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

def get_playlist_tracks(url): #For spotify playlists & albums
    results = sp.album(url) if check_urltype(url, spotify_album_urls) else sp.playlist(url)
    results = results['tracks']
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def search_playlist(url):
    if check_urltype(url, youtube_playlist_urls):
        html = urlopen(url).read().decode()
        ids = re.findall('{"playlistVideoRenderer":{"videoId":"(.*?)"', html)
        titles = re.findall(r'"title":{"runs":\[{"text":"(.*?)"}\],"accessibility":', html)
        artists = re.findall('"shortBylineText":{"runs":\[{"text":"(.*?)","navigationEndpoint":', html)
        for id, title, artist in zip(ids, titles, artists):
            yield Song(id, title, artist)
    elif check_urltype(url, spotify_playlist_urls):
        tracks= get_playlist_tracks(url)
        for track in tracks:
            if not check_urltype(url, spotify_album_urls): track = track['track']
            yield next(search_songs(f'*{track["name"]} {" ".join(artist["name"] for artist in track["artists"])}*'))
    else: raise commands.BadArgument('Please provide a playlist URL')

async def find_song(ctx, search):
    songs = search_songs(search)
    songs = tuple([next(songs, None) for i in range(10)])
    while not songs[-1]: songs = songs[:-1]
    _opts = '\n'.join(f'  **{i + 1}:** {song.title} - {song.artist}' for i, song in enumerate(songs))
    _results_text = 'Results (showing only videos auto-generated by YouTube)' if search.startswith('*') and search.endswith('*') else 'Results'
    id_list_msg = await ctx.send(f'**{_results_text}:**\n{_opts}\n\n*Select a song by entering it\'s corresponding number, or "cancel" to cancel*')
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
    if ctx.guild: await id_list_msg.delete()
