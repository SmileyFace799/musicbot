import discord
from discord.ext import commands
import typing
from stuff import *
from exceptions import *
import json
from random import randint

class SongEncoder(json.JSONEncoder):
    def default(self, object):
        if isinstance(object, Song):
            return {
                'class': 'Song',
                'id': object.id,
                'title': object.title,
                'artist': object.artist
            }
        else: return super().default(object)

def convert_songs(dct):
    for k in dct.copy().keys():
        if k.isdigit(): dct[int(k)] = dct.pop(k)
    if 'class' in dct.keys():
        return globals()[dct.pop('class')](**dct)
    else: return dct

class Playlists(dict):
    def __init__(self):
        with open('./playlists.json') as s:
            super().__init__(json.load(s, object_hook=convert_songs))
    def save(self):
        with open('./playlists.json', 'w') as s:
            json.dump(self, s, indent=2, cls=SongEncoder)
    load = __init__
playlists = Playlists()

def get_entry(ctx):
    id = ctx.author.id
    return playlists[id] if id in playlists.keys() else None

def get_list(ctx, name, raise_error=True):
    entry = get_entry(ctx)
    if entry and (name in entry.keys()): return entry[name]
    elif raise_error: raise NotFoundException('Playlist not found')
    else: return None

class Playlist(commands.Cog):
    @commands.group(
        brief='Manages playlists',
        help='This command and it\'s subcommands are used to play, create, edit & delete playlists. Invoking just this command is a shortcut for `playlist view`',
        usage='playlist'
    )
    async def playlist(self, ctx):
        if not ctx.invoked_subcommand:
            await ctx.invoke(ctx.bot.get_command('playlist view'))

    @playlist.command(
        brief='Views playlists',
        help='This commands can be used to view all your playlists, aswell as viewing all the songs within any of them',
        usage='playlist view \\*[playlist]'
    )
    async def view(self, ctx, playlist=None):
        if playlist:
            list = get_list(ctx, playlist)
            if list is None: raise NotFoundException('Playlist not found')
            await ctx.send(f'Showing playlist: **{playlist}**\n' + '\n'.join(f'  **{i + 1}:** {song.title} - {song.artist}' for i, song in enumerate(list)))
        else:
            entry = get_entry(ctx)
            if entry: await ctx.send('Your playlists:\n  **-** ' + '\n  **-** '.join(entry.keys()))
            else: await ctx.send('You don\'t have any playlists')

    @playlist.command(
        brief='Creates a playlist',
        help='This creates a playlist you can add songs to',
        usage='playlist create [name]'
    )
    async def create(self, ctx, name):
        entry = get_entry(ctx)
        if not entry: entry = playlists[ctx.author.id] = {}
        if name in entry.keys(): await ctx.send(f'You already have a playlist named "{name}"')
        else:
            entry[name] = []
            playlists.save()
            await ctx.send(f'Playlist "{name}" created')

    @playlist.command(
        brief='Deletes a playlist',
        help='This deletes an existing playlist',
        usage='playlist delete [playlist]'
    )
    async def delete(self, ctx, name):
        entry = get_entry(ctx)
        if not entry: await ctx.send('You don\'t have any playlists')
        elif name in entry.keys():
            del entry[name]
            if not entry: del playlists[ctx.author.id]
            playlists.save()
            await ctx.send(f'Playlist "{name}" deleted')
        else: await ctx.send('You don\'t have a playlist named that')

    @playlist.command(
        brief='Adds songs to playlists',
        help='This adds a song to a playlist, either by providing a url, or a YouTube search. Currently supports URLs from: YouTube',
        usage='playlist add [search|url]'
    )
    async def add(self, ctx, playlist, *, search):
        list = get_list(ctx, playlist)
        song = await find_song(ctx, search)
        if not song: return
        list.append(song)
        playlists.save()
        await ctx.send(f'"{song.title}" added to "{playlist}"')

    @playlist.command(
        brief='Removes songs from playlists',
        help='This removes a song from a playlist. This command takes the index of the song you want to remove, which can be accessed through the `playlist view` command',
        usage='playlist remove [index]'
    )
    async def remove(self, ctx, playlist, index:int):
        list = get_list(ctx, playlist)
        if not list: raise InvalidStateException('Playlist is empty')
        song = list.pop(index - 1)
        playlists.save()
        await ctx.send(f'"{song.title}" removed from "{playlist}"')

    @vc()
    @commands.guild_only()
    @playlist.command(
        brief='Plays a bot playlist',
        help='This plays a specified playlist in the voice channel you\'re in. Note: This plays bot playlists only, to play other playlists directly, see `playlist quickplay` or `playlist import`',
        usage='playlist play [playlist] *[index]'
    )
    async def play(self, ctx, playlist, index:typing.Optional[int]):
        playlist = get_list(ctx, playlist)
        if index is not None: await queue_song(ctx, playlist[index - 1])
        else:
            playlist = list(playlist)
            playlist.insert(0, playlist.pop(randint(0, len(playlist) - 1)))
            await queue_list(ctx, playlist)

    @vc()
    @commands.guild_only()
    @playlist.command(
        brief='Plays a playlist from URL',
        help='This plays a specified playlist, provided by URL. Note: This does not play bot playlists, to play bot playlists, see `playlist play`. Currently supports: YouTube',
        usage='playlist quickplay [url]'
    )
    async def quickplay(self, ctx, url):
        playlist = search_playlist(url)
        await queue_list(ctx, playlist)

    @playlist.command(
        name='import',
        brief='Imports an external playlist into the bot',
        help='This imports a playlist provided by URL into the bot. Can be imported into an existing playlist, or into a new one. This only imports external playlists, to combine playlists within the bot, see `playlist combine`. Currently supports: YouTube',
        usage='playlist import [name|list] [url]'
    )
    async def import_playlist(self, ctx, name, url):
        playlist = search_playlist(url)
        list = get_list(ctx, name, raise_error=False)
        if list is None:
            await ctx.invoke(ctx.bot.get_command('playlist create'), name=name)
            list = get_list(ctx, name)
        await ctx.send(f'Importing playlist...')
        for song in playlist:
            list.append(song)
        playlists.save()
        await ctx.send('Playlist imported!')

    @playlist.command(
        brief='Combines playlists together',
        help='This combines two playlists together, either by combining them into the 1st list, or a 3rd target list if provided. If the 3rd target list doesn\'t exist, it will be automatically made. This only combines playlists stored within the bot, for external playlists, see `playlist import`',
        usage='playlist combine [list1] [list2] *[name|targetlist]'
    )
    async def combine(self, ctx, name1, name2, targetname=None):
        list1 = get_list(ctx, name1)
        list2 = get_list(ctx, name2)
        if targetname:
            entry = get_entry(ctx)
            if targetname in entry: targetlist = get_list(target_name)
            else: targetlist = entry[targetname] = []
            for song in list1 + list2:
                targetlist.append(song)
        else:
            for song in list2:
                list1.append(song)
        playlists.save()
        await ctx.send('Playlists combined!')

def setup(bot):
    bot.add_cog(Playlist(bot))
