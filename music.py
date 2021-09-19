import discord
from discord.ext import commands, tasks
from stuff import *
from exceptions import *
import re
from lyricsgenius import Genius
import typing
from datetime import datetime as dt
genius = Genius('acU_6ftNqV-0zCxqo7d9gG7r__FnpVh6YAXIQD-CedWBuoxySEidUwoYn8h6Mt9O')

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.queue_cleaner.start()

    @tasks.loop(seconds=5)
    async def queue_cleaner(self):
        now = dt.now()
        ids = reversed(tuple(i for i, queue in queues.items() if not queue.vc.is_playing() and (now - queue.last_played).total_seconds() > 300))
        for i in ids:
            await queues[i].vc.disconnect()
            del queues[i]

    @commands.guild_only()
    @commands.command(
        brief='Joins a voice channel',
        help='Have the bot join a voice channel. If the bot is busy playing music elsewhere, use `mobehere` instead. This command is typically executed automatically, whenever the bot needs to',
        usage='join'
    )
    async def join(self, ctx):
        if not ctx.author.voice: raise NoVoiceException('Not connected to a voice chat')
        await ctx.author.voice.channel.connect()
        make_queue(ctx)
        await ctx.send('Joined!')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Moves the bot to a voice channel',
        help='This moves the bot from a different voice channel to the current one. If the bot is not in a voice channel, use `join` instead, if needed',
        usage='movehere'
    )
    async def movehere(self, ctx):
        if not ctx.voice_client: raise InvalidStateException(f'Bot is not connected. Use {ctx.prefix}join instead')
        if ctx.voice_client.channel == ctx.author.voice.channel: raise InvalidStateException('Bot is already here')
        await ctx.voice_client.move_to(ctx.author.voice.channel)

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Leaves a voice channel',
        help='Makes the bot leave the current voice channel. This command is typically executed automatically, whenever the bot needs to',
        usage='leave'
    )
    async def leave(self, ctx):
        if not ctx.voice_client: raise InvalidStateException(f'Bot is not connected')
        if ctx.voice_client.channel != ctx.author.voice.channel: raise InvalidStateException('You must be in the same channel as the bot to disconnect it')
        del_queue(ctx)
        await ctx.voice_client.disconnect()
        await ctx.send('Left!')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Play a song',
        help='Plays a song or in a voice channel. Can either be a url or a YouTube search. The bot will join automatically upon playing. This can also be used as a shortcut for `playlist quickplay` to play external playlists. Currently supports: YouTube, Spotify',
        usage='play [search|url]'
    )
    async def play(self, ctx, *, search):
        if is_url_playlist(search):
            await ctx.invoke(ctx.bot.get_command('playlist quickplay'), search)
        elif search.startswith('https://www.youtube.com/watch?v='):
            await queue_song(ctx, Song(search[32:43]))
        else:
            if search.startswith('https://open.spotify.com/track/'):
                track = sp.track(search)
                search = f'{track["name"]} {track["artists"][0]["name"]} - topic'
            songs = search_songs(search)
            await queue_song(ctx, next(songs))

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Search for a song to play',
        help='Does an in-depth song search based on search query, returns search results for user to then pick a result. Currently supports: YouTube',
        usage='search [search]'
    )
    async def search(self, ctx, *, search):
        song = await find_song(ctx, search)
        if song: await queue_song(ctx, song)

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Shows the queue',
        help='Shows the bot\'s song queue, and if the queue is shuffled, if the queue is repeating, and if the current song is repeating',
        usage='queue *[page]',
        aliases=['que', 'q']
    )
    async def queue(self, ctx, page:typing.Optional[int]=1):
        get_str = lambda b: 'On' if b else 'Off'
        queue = get_queue(ctx)
        pagecount = (len(queue) - 1) // page_size + 1
        page_queue = queue[page_size * (page - 1):page_size * page]
        if queue:
            await ctx.send(f'**Shuffle:** {get_str(queue.shuffle)}\n**Repeat song:** {get_str(queue.repeat)}\n**Repeat queue:** {get_str(queue.repeatqueue)}' + \
                ('\n\nCurrent queue (not in order):\n' if queue.shuffle else '\n\nCurrent queue:\n') + \
                '\n'.join(f'  **{page_size * (page - 1) + index + 1 if index != 0 or page != 1 else "Current"}:** {song.title} - {song.artist}' for index, song in enumerate(page_queue)) + \
                f'\n\nShowing page **{page}** of **{pagecount}**'
            )
        else: await ctx.send(f'**Shuffle:** {get_str(queue.shuffle)}\n**Repeat song:** {get_str(queue.repeat)}\n**Repeat queue:** {get_str(queue.repeatqueue)}\n\nQueue is empty')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Resumes music',
        help='Resume the current music, if paused',
        usage='resume'
    )
    async def resume(self, ctx):
        if ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await ctx.send('Resuming music')
        else: raise InvalidStateException('Music is already playing')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Pauses music',
        help='Pause the current music, if playing',
        usage='pause'
    )
    async def pause(self, ctx):
        if not ctx.voice_client.is_paused():
            ctx.voice_client.pause()
            await ctx.send('Pausing music')
        else: raise InvalidStateException('Music is already paused')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Skips songs',
        help='Skips the current song. If the current song is repeating, the next song will start repeating instead. Can also skip to a specified song in the queue',
        usage='skip *[index]'
    )
    async def skip(self, ctx, index:typing.Optional[int]=None):
        queue = get_queue(ctx)
        queue.skip = True
        if index:
            queue.next = index
            await ctx.send(f'Skipping to song {index} in the queue')
        else: await ctx.send('Song skipped')
        ctx.voice_client.stop()

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Shuffles queue',
        help='This shuffles the song order of the queue',
        usage='shuffle',
        aliases=['mix', 'shf', 'sf']
    )
    async def shuffle(self, ctx):
        queue = get_queue(ctx)
        queue.shuffle = not queue.shuffle
        await ctx.send('Queue shuffled' if queue.shuffle else 'Queue un-shuffled')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Repeats a song',
        help='Repeats the currently playing song. To repeat the whole queue, use `repeatqueue` instead',
        usage='repeat',
        aliases=['rpt', 'rp']
    )
    async def repeat(self, ctx):
        queue = get_queue(ctx)
        queue.repeat = not queue.repeat
        await ctx.send('Repeating song' if queue.repeat else 'No longer repeating song')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Repeats the queue',
        help='Repeats the queue. To repeat only a song, use `repeat` instead',
        usage='repeatqueue',
        aliases=['repeatque', 'repeatq', 'rqueue', 'rque', 'rq']
    )
    async def repeatqueue(self, ctx):
        queue = get_queue(ctx)
        queue.repeatqueue = not queue.repeatqueue
        await ctx.send('Repeating queue' if queue.repeatqueue else 'No longer repeating queue')

    @vc()
    @commands.guild_only()
    @commands.command(
        brief='Stop the music',
        help='Stop the bot from playing music. The bot also automatically leaves.',
        usage='stop'
    )
    async def stop(self, ctx):
        queue = get_queue(ctx)
        queue.clear()
        ctx.voice_client.stop()
        await ctx.send('Music stopped')

    @commands.command(
        brief='Get the lyrics of some music',
        help='Fetches lyrics for what you or someone else is listening to (depending on who you\'ve pinged, if any). This primarily checks if they\'re listening to the music bot, but can also get lyrics for someone\'s Spotify activity',
        usage='lyrics *[user|search]'
    )
    async def lyrics(self, ctx, *, target:typing.Union[discord.Member, str]=None):
        if not target: target = ctx.author
        queue = get_queue(ctx)
        spotify = next(filter(lambda a: isinstance(a, discord.Spotify), target.activities), None) if isinstance(target, discord.abc.User) else None

        if type(target) == str:
            title = target
            artist = None
        elif queue and target in ctx.voice_client.channel.members:
            title = re.sub('\[.+?\]|\(.+?\)', '', queue.song.title).strip(' ')
            artist = None
        elif spotify:
            title = spotify.title
            artist = spotify.artists[0]
        else: raise InvalidStateException('User not listening to anything')
        lyrics = genius.search_song(title, artist) if artist else genius.search_song(title)
        if not lyrics: raise NotFoundException('No lyrics found. (Genius API sucks balls btw and sometimes trying again just works)')
        textdict = lyrics.to_dict()
        emb = discord.Embed(title=spotify.title, description=spotify.artist, color=spotify.color) if spotify else discord.Embed(title=lyrics.title, description=lyrics.artist, color=0xffff64)
        for i in textdict['lyrics'].split('\n\n'):
            if i.endswith('1EmbedShare URLCopyEmbedCopy'): i = i[:-28]
            emb.add_field(name=re.search('\[(.*)\]', i+'\n').group(1) if '[' in i and ']' in i else 'Lyrics', value=re.sub('\[.+?\]', '', i) if re.sub('\[.+?\]', '', i) else '(No lyrics)', inline=False)
            emb.set_thumbnail(url=spotify.album_cover_url if spotify else lyrics.song_art_image_url)
            emb.set_footer(text=lyrics.url)
        try: await ctx.send(embed=emb)
        except: await ctx.send('These lyrics are too long to sent in a message, but here\'s a link with some lyrics: ' + lyrics.url)

def setup(bot):
    bot.add_cog(Music(bot))
