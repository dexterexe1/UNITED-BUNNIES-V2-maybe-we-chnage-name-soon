from bot.ui.premium_cards import quick_card_view, style_card_view, embed_to_view
"""
music.py — Music engine (play, queue, volume, loop, playlist).
Extracted from the original monolithic bot.py. Logic unchanged.
"""
import discord
from discord.ext import commands
import discord.app_commands as app_commands
import yt_dlp
import asyncio
import datetime

from bot.config import (
    bot, quick_embed, song_queues, now_playing, song_volumes, loop_modes,
)
from bot.database import add_liked_song, get_liked_songs, clear_liked_songs

def play_next_in_queue(ctx):
    guild_id = ctx.guild.id
    vc = ctx.voice_client
    if not vc or not vc.is_connected():
        return

    # Handle looping: re-queue the track that just finished before picking the next one
    finished_track = now_playing.get(guild_id)
    mode = loop_modes.get(guild_id, "off")
    if finished_track:
        if mode == "track":
            song_queues.setdefault(guild_id, []).insert(0, finished_track)
        elif mode == "queue":
            song_queues.setdefault(guild_id, []).append(finished_track)

    if guild_id in song_queues and len(song_queues[guild_id]) > 0:
        next_track = song_queues[guild_id].pop(0)
        now_playing[guild_id] = next_track

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn',
            'ffmpeg_location': '/usr/bin/ffmpeg'  # ← ADD THIS LINE
        }

        volume = song_volumes.get(guild_id, 1.0)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(next_track["url"], **ffmpeg_options), volume=volume)

        vc.play(
            source,
            after=lambda e: play_next_in_queue(ctx)
        )
        
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{next_track['title']}]({next_track['url']})** \n⏱️ Duration: `{next_track['duration']}`",
            color=0x2f3136
        )
        if next_track["thumbnail"]:
            embed.set_thumbnail(url=next_track["thumbnail"])
        embed.set_footer(text="Enjoy the stream session matrix 🔊")
        bot.loop.create_task(ctx.send(view=embed_to_view(embed)))
    else:
        now_playing.pop(guild_id, None)
        bot.loop.create_task(ctx.send("🏁 **Queue completed.** The audio stream has finished."))

@bot.hybrid_command(name="play", description="Play or queue a song in your voice channel")
@app_commands.describe(search_or_url="Song name, search term, or a direct URL")
async def play_audio_command(ctx, *, search_or_url: str = None):
    if not ctx.author.voice:
        await ctx.send(view=quick_card_view("❌ You must join a voice channel first!"))
        return

    if search_or_url is None and ctx.message and ctx.message.attachments:
        search_or_url = ctx.message.attachments[0].url

    if not search_or_url:
        await ctx.send(view=quick_card_view("❌ Provide a track name or URL! Syntax: `?play <song title or link>`"))
        return

    vc = ctx.voice_client
    if not vc:
        vc = await ctx.author.voice.channel.connect()

    async with ctx.typing():
        info = None
        stream_url = None
        
        # Try SoundCloud search loop first to handle cloud engines safely
        try:
            with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'scsearch'}) as ydl:
                info = ydl.extract_info(search_or_url, download=False)
                if 'entries' in info and len(info['entries']) > 0:
                    info = info['entries'][0]
                elif 'entries' in info and len(info['entries']) == 0:
                    info = None
                
                if info:
                    stream_url = info['url']
        except Exception:
            info = None  

        # Fallback Strategy: If SoundCloud fails or hits DRM, automatically use alternate parsing
        if not stream_url:
            try:
                with yt_dlp.YoutubeDL({'format': 'bestaudio/best', 'noplaylist': True, 'quiet': True, 'default_search': 'ytsearch'}) as ydl:
                    info = ydl.extract_info(search_or_url, download=False)
                    if 'entries' in info:
                        info = info['entries'][0]
                    stream_url = info['url']
            except Exception as e:
                await ctx.send(view=quick_card_view(f"❌ Failed to parse media details from all engine paths: {e}"))
                return

        song_title = info.get('title', 'Unknown Track') if info else 'Unknown Track'
        thumbnail = info.get('thumbnail', None) if info else None
        duration_secs = info.get('duration', 0) if info else 0
        duration_str = str(datetime.timedelta(seconds=duration_secs))[2:7] if duration_secs else "Live Stream"

    guild_id = ctx.guild.id
    if guild_id not in song_queues:
        song_queues[guild_id] = []

    track_data = {
        "url": stream_url,
        "title": song_title,
        "duration": duration_str,
        "thumbnail": thumbnail,
        "ctx": ctx
    }

    ffmpeg_options = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
        'options': '-vn',
        'ffmpeg_location': '/usr/bin/ffmpeg'  # ← Render's ffmpeg path
    }

    if vc.is_playing():
        song_queues[guild_id].append(track_data)
        position = len(song_queues[guild_id])
        
        embed = discord.Embed(
            title=f"Queued at position #{position}",
            description=f"**[{song_title}]({stream_url})**\n⏱️ Duration: `[{duration_str}]`",
            color=0x1E1F22
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        embed.set_footer(text="Not the correct track? Try being more specific.")
        await ctx.send(view=embed_to_view(embed))
    else:
        now_playing[guild_id] = track_data
        volume = song_volumes.get(guild_id, 1.0)
        source = discord.PCMVolumeTransformer(discord.FFmpegPCMAudio(stream_url, **ffmpeg_options), volume=volume)
        vc.play(
            source,
            after=lambda e: play_next_in_queue(ctx)
        )
        # ✅ FIXED: This embed block is now at the correct indentation level
        embed = discord.Embed(
            title="🎶 Now Playing",
            description=f"**[{song_title}]({stream_url})**\n⏱️ Duration: `[{duration_str}]`",
            color=0x2f3136
        )
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        await ctx.send(view=embed_to_view(embed))
@bot.hybrid_command(name="skip", aliases=["s", "next"], description="Skip the current track")
async def skip_audio_command(ctx):
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
        await ctx.send(view=quick_card_view("⏭️ **Track skipped.** Loading next active layout..."))
    else:
        await ctx.send(view=quick_card_view("❌ No active music streaming tracks detected."))

@bot.hybrid_command(name="stop", aliases=["end"], description="Stop playback and clear the queue")
async def stop_audio_command(ctx):
    guild_id = ctx.guild.id
    if guild_id in song_queues:
        song_queues[guild_id] = []
    now_playing.pop(guild_id, None)
    loop_modes[guild_id] = "off"
    vc = ctx.voice_client
    if vc and vc.is_playing():
        vc.stop()
    await ctx.send(view=quick_card_view("⏹️ **Playback halted.** Core audio queues flushed completely."))

@bot.hybrid_command(name="leave", aliases=["dc", "disconnect"], description="Disconnect the bot from voice")
async def leave_voice_command(ctx):
    vc = ctx.voice_client
    if vc:
        guild_id = ctx.guild.id
        song_queues.pop(guild_id, None)
        now_playing.pop(guild_id, None)
        await vc.disconnect()
        await ctx.send(view=quick_card_view("👋 **Disconnected successfully** from local voice rooms."))
    else:
        await ctx.send(view=quick_card_view("❌ I am not connected to any voice rooms."))

@bot.hybrid_command(name="queue", aliases=["q"], description="Show the current music queue")
async def queue_command(ctx):
    guild_id = ctx.guild.id
    queue = song_queues.get(guild_id, [])
    current = now_playing.get(guild_id)

    if not current and not queue:
        await ctx.send(view=quick_card_view("📭 Nothing is playing and the queue is empty."))
        return

    embed = discord.Embed(title="🎶 Music Queue", color=0x2f3136)
    if current:
        embed.add_field(
            name="▶️ Now Playing",
            value=f"**[{current['title']}]({current['url']})** — `{current['duration']}`",
            inline=False,
        )
    if queue:
        lines = [f"**{i}.** [{t['title']}]({t['url']}) — `{t['duration']}`" for i, t in enumerate(queue[:10], 1)]
        embed.add_field(name=f"⏭️ Up Next ({len(queue)})", value="\n".join(lines), inline=False)
        if len(queue) > 10:
            embed.set_footer(text=f"...and {len(queue) - 10} more track(s) queued.")
    else:
        embed.add_field(name="⏭️ Up Next", value="Queue is empty.", inline=False)
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="nowplaying", aliases=["np"], description="Show what's currently playing")
async def nowplaying_command(ctx):
    current = now_playing.get(ctx.guild.id)
    if not current:
        await ctx.send(view=quick_card_view("❌ Nothing is currently playing."))
        return

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"**[{current['title']}]({current['url']})**\n⏱️ Duration: `{current['duration']}`",
        color=0x2f3136,
    )
    if current.get("thumbnail"):
        embed.set_thumbnail(url=current["thumbnail"])
    vol = int(song_volumes.get(ctx.guild.id, 1.0) * 100)
    mode = loop_modes.get(ctx.guild.id, "off")
    embed.set_footer(text=f"🔊 Volume: {vol}%  •  🔁 Loop: {mode}")
    await ctx.send(view=embed_to_view(embed))

@bot.hybrid_command(name="volume", aliases=["vol"], description="Get or set the playback volume")
@app_commands.describe(percent="Volume percentage (0-200)")
async def volume_command(ctx, percent: int = None):
    guild_id = ctx.guild.id
    if percent is None:
        current_vol = int(song_volumes.get(guild_id, 1.0) * 100)
        await ctx.send(view=quick_card_view(f"🔊 Current volume: **{current_vol}%**. Usage: `?volume <0-200>`"))
        return

    percent = max(0, min(200, percent))
    song_volumes[guild_id] = percent / 100

    vc = ctx.voice_client
    if vc and vc.source and isinstance(vc.source, discord.PCMVolumeTransformer):
        vc.source.volume = percent / 100

    await ctx.send(view=quick_card_view(f"🔊 Volume set to **{percent}%**."))

@bot.hybrid_command(name="loop", description="Set the loop mode (off, track, or queue)")
@app_commands.describe(mode="off, track, or queue")
async def loop_command(ctx, mode: str = None):
    guild_id = ctx.guild.id
    valid_modes = ["off", "track", "queue"]
    if mode is None or mode.lower() not in valid_modes:
        current_mode = loop_modes.get(guild_id, "off")
        await ctx.send(view=quick_card_view(f"🔁 Usage: `?loop <off|track|queue>`. Current mode: **{current_mode}**"))
        return

    loop_modes[guild_id] = mode.lower()
    await ctx.send(view=quick_card_view(f"🔁 Loop mode set to **{mode.lower()}**."))

@bot.hybrid_command(name="like", description="Save a song link to your personal playlist")
@app_commands.describe(song_url="Link to the track", title="Title to save it under")
async def like_song_command(ctx, song_url: str = None, *, title: str = "Saved Track"):
    if song_url is None and ctx.message and ctx.message.attachments:
        song_url = ctx.message.attachments[0].url

    if not song_url:
        await ctx.send(view=quick_card_view("❌ Specify a link or attach a track file to save! Syntax: `?like <url> [title]`"))
        return

    add_liked_song(ctx.author.id, title, song_url)
    await ctx.send(view=quick_card_view(f"❤️ **Track Saved!** Added **'{title}'** directly to your personal Database Playlist."))

@bot.hybrid_command(name="playlist", description="View, play, or clear your saved playlist")
@app_commands.describe(action="view, play, or clear")
async def view_or_play_playlist(ctx, action: str = "view"):
    songs = get_liked_songs(ctx.author.id)
    if not songs:
        await ctx.send(view=quick_card_view("💔 Your private Liked Playlist is empty! Log songs using `?like <url>` first."))
        return

    if action.lower() == "play":
        if not ctx.author.voice:
            await ctx.send(view=quick_card_view("❌ You must join a voice channel first!"))
            return
        vc = ctx.voice_client
        if not vc: vc = await ctx.author.voice.channel.connect()

        guild_id = ctx.guild.id
        if guild_id not in song_queues: song_queues[guild_id] = []

        for title, url in songs:
            song_queues[guild_id].append({"url": url, "title": title, "duration": "Saved Track", "thumbnail": None, "ctx": ctx})

        await ctx.send(view=quick_card_view(f"📦 Loaded **{len(songs)} tracks** out of your playlist directly into active queues!"))
        if not vc.is_playing():
            play_next_in_queue(ctx)
    elif action.lower() == "clear":
        clear_liked_songs(ctx.author.id)
        await ctx.send(view=quick_card_view("🗑️ Your Liked Playlist ledger has been wiped out completely."))
    else:
        embed = discord.Embed(title=f"❤️ {ctx.author.display_name}'s Private Playlist Ledger", color=discord.Color.magenta())
        description_text = ""
        for i, (title, url) in enumerate(songs, 1):
            description_text += f"**{i}. {title}**\n🔗 [Stream Track]({url})\n\n"
        embed.description = description_text
        await ctx.send(view=embed_to_view(embed))


