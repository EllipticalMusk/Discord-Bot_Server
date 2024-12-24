import discord
import os
import asyncio
import yt_dlp
import json
from dotenv import load_dotenv

def run_bot():
    # Load configuration
    load_dotenv()
    TOKEN = os.getenv("Token")
    CONFIG_FILE = "config.json"

    # Load or initialize config
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)
    else:
        config = {"prefix": "?", "channel_id": None}
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f)

    prefix = config.get("prefix", "?")
    allowed_channel_id = config.get("channel_id")

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents)

    queues = {}
    voice_clients = {}
    yt_dl_options = {"format": "bestaudio/best"}
    ytdl = yt_dlp.YoutubeDL(yt_dl_options)

    ffmpeg_options = {
        "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
        "options": '-vn -filter:a "volume=0.25"',
    }

    async def play_next_song(guild_id):
        """Play the next song in the queue."""
        
        if guild_id in queues and queues[guild_id]:
            song_data = queues[guild_id].pop(0)
            song_url = song_data["url"]
            voice_client = voice_clients[guild_id]
            player = discord.FFmpegOpusAudio(song_url, **ffmpeg_options)

            # Play the next song and send the "Now Playing" embed
            voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next_song(guild_id), asyncio.get_event_loop()))
            
            embed = discord.Embed(
                title="Now Playing",
                description=f"**{song_data['title']}**",
                color=discord.Color.green(),
            )
            embed.add_field(name="Uploader", value=song_data.get("uploader", "Unknown"), inline=True)
            embed.add_field(name="Requested by", value=song_data["requester"], inline=True)
            embed.set_thumbnail(url=song_data["thumbnail"])
            await song_data["channel"].send(embed=embed)

    @client.event
    async def on_ready():
        print(f"{client.user} is online and ready!")

    @client.event
    async def on_message(message):
        nonlocal prefix, allowed_channel_id

        # Ignore messages from the bot itself
        if message.author == client.user:
            return

        # Restrict to specific channel if set
        if allowed_channel_id and message.channel.id != allowed_channel_id:
            return

        if message.content.startswith(f"{prefix}setprefix"):
            try:
                new_prefix = message.content.split()[1]
                prefix = new_prefix
                config["prefix"] = new_prefix
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f)
                await message.channel.send(f"Prefix updated to `{new_prefix}`")
            except IndexError:
                await message.channel.send("Usage: setprefix <new_prefix>")

        if message.content.startswith(f"{prefix}setchannel"):
            try:
                allowed_channel_id = message.channel.id
                config["channel_id"] = allowed_channel_id
                with open(CONFIG_FILE, "w") as f:
                    json.dump(config, f)
                await message.channel.send(f"Commands restricted to this channel.")
            except Exception as e:
                await message.channel.send("Failed to set the allowed channel.")
                print(e)

        if message.content.startswith(f"{prefix}play"):
            try:
                # Connect to the voice channel
                if message.guild.id not in voice_clients or not voice_clients[message.guild.id].is_connected():
                    voice_client = await message.author.voice.channel.connect()
                    voice_clients[message.guild.id] = voice_client
                else:
                    voice_client = voice_clients[message.guild.id]

                # Extract the search query or URL
                query = " ".join(message.content.split()[1:])
                loop = asyncio.get_event_loop()

                # Determine if it's a search or URL
                if "http://" in query or "https://" in query:
                    data = await loop.run_in_executor(None, lambda: ytdl.extract_info(query, download=False))
                else:
                    # Perform a YouTube search
                    data = await loop.run_in_executor(
                        None, lambda: ytdl.extract_info(f"ytsearch:{query}", download=False)["entries"][0]
                    )

                # Extract song details
                song = {
                    "url": data["url"],
                    "title": data["title"],
                    "uploader": data.get("uploader", "Unknown"),
                    "thumbnail": data["thumbnail"],
                    "requester": message.author.mention,
                    "channel": message.channel,
                }

                # Add to queue
                if message.guild.id not in queues:
                    queues[message.guild.id] = []

                is_playing = voice_client.is_playing()
                queues[message.guild.id].append(song)

                # Send "Added to Queue" embed
                embed = discord.Embed(
                    title="Added to Queue",
                    description=f"**{song['title']}**",
                    color=discord.Color.blue(),
                )
                embed.add_field(name="Uploader", value=song.get("uploader", "Unknown"), inline=True)
                embed.add_field(name="Added by", value=song["requester"], inline=True)
                embed.set_thumbnail(url=song["thumbnail"])
                await message.channel.send(embed=embed)

                # Play if nothing is currently playing
                if not is_playing:
                    await play_next_song(message.guild.id)

            except Exception as e:
                print(e)
                await message.channel.send("An error occurred while trying to play the song.")

        if message.content.startswith(f"{prefix}pause"):
            try:
                voice_clients[message.guild.id].pause()
                await message.channel.send("Playback paused.")
            except Exception as e:
                print(e)

        if message.content.startswith(f"{prefix}resume"):
            try:
                voice_clients[message.guild.id].resume()
                await message.channel.send("Playback resumed.")
            except Exception as e:
                print(e)

        if message.content.startswith(f"{prefix}stop"):
            try:
                voice_clients[message.guild.id].stop()
                queues[message.guild.id] = []
                await voice_clients[message.guild.id].disconnect()
                await message.channel.send("Playback stopped and disconnected.")
            except Exception as e:
                print(e)

        if message.content.startswith(f"{prefix}skip"):
            try:
                voice_clients[message.guild.id].stop()
                await message.channel.send("Song skipped.")
                await play_next_song(message.guild.id)
            except Exception as e:
                print(e)
                await message.channel.send("An error occurred while trying to skip the song.")

    client.run(TOKEN)
