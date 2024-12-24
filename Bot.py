import discord
from discord.ext import commands
import os
import asyncio
import yt_dlp
from dotenv import load_dotenv
import urllib.parse, urllib.request, re

load_dotenv()
TOKEN = os.getenv('Token')
Pre = os.getenv('Prefix')

intents = discord.Intents.default()
intents.message_content = True
client = commands.Bot(command_prefix=Pre, intents=intents)

queues = {}
voice_clients = {}
youtube_base_url = 'https://www.youtube.com/'
youtube_results_url = youtube_base_url + 'results?'
youtube_watch_url = youtube_base_url + 'watch?v='
yt_dl_options = {"format": "bestaudio/best"}
ytdl = yt_dlp.YoutubeDL(yt_dl_options)

ffmpeg_options = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
                  'options': '-vn -filter:a "volume=0.25"'}

ALLOWED_CHANNEL_ID = int(os.getenv('AllowedChannelID'))

@client.event
async def on_ready():
    print(f'{client.user} is now jamming!')

async def play_next(ctx):
    if queues[ctx.guild.id]:
        link = queues[ctx.guild.id].pop(0)
        await play(ctx, link=link)

@client.command(name="play")
async def play(ctx, *, link):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    try:
        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel to use this command.")
            return

        if ctx.guild.id not in voice_clients or voice_clients[ctx.guild.id].is_connected() == False:
            voice_client = await ctx.author.voice.channel.connect()
            voice_clients[ctx.guild.id] = voice_client

        if youtube_base_url not in link:
            query_string = urllib.parse.urlencode({'search_query': link})
            content = urllib.request.urlopen(youtube_results_url + query_string)
            search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
            link = youtube_watch_url + search_results[0]

        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(link, download=False))

        song = data['url']
        title = data['title']
        duration = data.get('duration', 0)
        thumbnail = data.get('thumbnail', '')

        embed = discord.Embed(title="Now Playing", description=f"[{title}]({link})", color=discord.Color.green())
        embed.add_field(name="Requested by", value=ctx.author.mention)
        embed.add_field(name="Duration", value=f"{duration // 60}:{duration % 60:02}")
        embed.set_thumbnail(url=thumbnail)

        await ctx.send(embed=embed)

        player = discord.FFmpegOpusAudio(song, **ffmpeg_options)
        voice_clients[ctx.guild.id].play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), client.loop))
    except yt_dlp.utils.DownloadError:
        await ctx.send("An error occurred while trying to process the YouTube link. Please try a different link.")
    except Exception as e:
        print(e)
        await ctx.send("An unexpected error occurred. Please try again later.")

@client.command(name="skip")
async def skip(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    try:
        if ctx.guild.id in voice_clients and voice_clients[ctx.guild.id].is_playing():
            voice_clients[ctx.guild.id].stop()
            await ctx.send(embed=discord.Embed(description="Skipped the current song!", color=discord.Color.orange()))
        else:
            await ctx.send(embed=discord.Embed(description="There is no song playing to skip.", color=discord.Color.red()))
    except Exception as e:
        print(e)
        await ctx.send("An error occurred while trying to skip the song.")

@client.command(name="stop")
async def stop(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    try:
        if ctx.guild.id in voice_clients:
            await voice_clients[ctx.guild.id].disconnect()
            del voice_clients[ctx.guild.id]
            if ctx.guild.id in queues:
                queues[ctx.guild.id].clear()
            await ctx.send(embed=discord.Embed(description="Stopped playback and disconnected!", color=discord.Color.red()))
        else:
            await ctx.send(embed=discord.Embed(description="The bot is not connected to a voice channel.", color=discord.Color.red()))
    except Exception as e:
        print(e)
        await ctx.send("An error occurred while trying to stop the playback.")

@client.command(name="clear_queue")
async def clear_queue(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    if ctx.guild.id in queues:
        queues[ctx.guild.id].clear()
        await ctx.send(embed=discord.Embed(description="Queue cleared!", color=discord.Color.red()))
    else:
        await ctx.send(embed=discord.Embed(description="There is no queue to clear.", color=discord.Color.red()))

@client.command(name="queue")
async def queue(ctx, *, url):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []
    queues[ctx.guild.id].append(url)
    await ctx.send(embed=discord.Embed(description="Added to queue!", color=discord.Color.blue()))
    
    
    
@client.command(name="join")
async def join(ctx):
    if ctx.channel.id != ALLOWED_CHANNEL_ID:
        await ctx.send("You can only use commands in the designated channel.")
        return

    try:
        song_query = "bbno$ Edamame"  # Song you want to play
        # Search the song on YouTube
        query_string = urllib.parse.urlencode({'search_query': song_query})
        content = urllib.request.urlopen(youtube_results_url + query_string)
        search_results = re.findall(r'/watch\?v=(.{11})', content.read().decode())
        if search_results:
            link = youtube_watch_url + search_results[0]
            await play(ctx, link=link)  # Play the song using the existing play function
        else:
            await ctx.send("Could not find the song. Please try again.")
    except Exception as e:
        print(e)
        await ctx.send("An error occurred while trying to play the song.")


client.run(TOKEN)

