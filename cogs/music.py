"""Music commands: play / pause / resume / skip / queue / join / leave."""

# NOTE: Sometimes the queue breaks using the latest version of ffmpeg/ytdl.
#       Not sure if it's my fault or something else.
#       I'll have a deeper look at it later when I'm done uploading the other cogs first :(

import asyncio
import functools
import logging
import discord
from discord import app_commands
import config

log = logging.getLogger(__name__)

class Music(app_commands.Group):
    def __init__(self, client: discord.Client):
        super().__init__(name="music", description="Music commands.")
        self.client = client
        self.queues: dict[int, list[str]] = {}

    # --- internals ---

    async def _extract_info(self, query: str) -> dict:
        """Run yt-dlp in the default executor"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, functools.partial(config.YTDL.extract_info, query, download=False)
        )

    async def _play_next_in_queue(
        self, guild_id: int, original_interaction: discord.Interaction
    ):
        vc = original_interaction.guild.voice_client
        if not vc or not vc.is_connected():
            self.queues.pop(guild_id, None)
            log.info("Bot disconnected from guild %s. Queue cleared.", guild_id)
            return

        queue = self.queues.get(guild_id)
        if not queue:
            await original_interaction.channel.send(
                "Queue is empty. Use `/music play` or `/music queue <URL>` to add songs.",
                delete_after=10,
            )
            return

        link = queue.pop(0)
        try:
            data = await self._extract_info(link)

            if "entries" in data:
                source_url = data["entries"][0]["url"]
                title = data["entries"][0].get("title", "Unknown Title")
            elif "url" in data:
                source_url = data["url"]
                title = data.get("title", "Unknown Title")
            else:
                log.warning("Could not extract source URL from %s", link)
                await original_interaction.channel.send(
                    f"⚠️ Could not process: **{link}**. Skipping.", delete_after=10
                )
                await self._play_next_in_queue(guild_id, original_interaction)
                return

            vc.play(
                discord.FFmpegPCMAudio(source_url, **config.FFMPEG_OPTIONS),
                after=lambda e: asyncio.run_coroutine_threadsafe(
                    self._play_next_in_queue(guild_id, original_interaction),
                    self.client.loop,
                ),
            )
            await original_interaction.channel.send(f"▶️ Now playing: **{title}**")

        except Exception:
            log.exception("Error playing from queue in guild %s", guild_id)
            await original_interaction.channel.send(
                "❌ Error playing the song. Skipping to the next one.", delete_after=10
            )
            await self._play_next_in_queue(guild_id, original_interaction)

    async def _ensure_voice(self, interaction: discord.Interaction):
        """Connect/move to the user's voice channel. Returns the voice client or None."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.followup.send(
                "You must be in a voice channel to use this command."
            )
            return None

        vc = interaction.guild.voice_client
        voice_channel = interaction.user.voice.channel
        if not vc:
            vc = await voice_channel.connect()
        elif vc.channel != voice_channel:
            await vc.move_to(voice_channel)
            await interaction.followup.send(f"✅ Moved to: **{voice_channel.name}**")
        return vc

    # --- commands ---

    @app_commands.command(name="play", description="Play a song from YouTube (URL or search query).")
    @app_commands.describe(query="A YouTube URL or a search query.")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)

        vc = await self._ensure_voice(interaction)
        if vc is None:
            return

        guild_id = interaction.guild.id

        try:
            data = await self._extract_info(query)

            # Playlist: queue all entries.
            if "entries" in data:
                playlist_title = data.get("title", "Playlist")
                await interaction.followup.send(
                    f"Adding playlist: **{playlist_title}** to the queue."
                )
                for entry in data["entries"]:
                    if entry:
                        self.queues.setdefault(guild_id, []).append(entry["webpage_url"])
                if not vc.is_playing() and not vc.is_paused():
                    await self._play_next_in_queue(guild_id, interaction)
                return

            song_url = data.get("url")
            title = data.get("title", "Unknown Title")

            if not song_url:
                return await interaction.followup.send(
                    "Could not find a valid song URL for your query."
                )

            if vc.is_playing() or vc.is_paused():
                self.queues.setdefault(guild_id, []).append(query)
                await interaction.followup.send(
                    f"✅ Added to queue: **{title}** (Position: {len(self.queues[guild_id])})"
                )
            else:
                vc.play(
                    discord.FFmpegPCMAudio(song_url, **config.FFMPEG_OPTIONS),
                    after=lambda e: asyncio.run_coroutine_threadsafe(
                        self._play_next_in_queue(guild_id, interaction), self.client.loop
                    ),
                )
                await interaction.followup.send(f"▶️ Now playing: **{title}**")

        except Exception:
            log.exception("Error during /music play")
            await interaction.followup.send(
                "❌ An error occurred while trying to play the song. Try a different query."
            )

    @app_commands.command(name="pause", description="Pauses the currently playing song.")
    async def pause(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.followup.send("I'm not connected to a voice channel.")

        if vc.is_playing():
            vc.pause()
            await interaction.followup.send("⏸️ Song paused.")
        else:
            await interaction.followup.send("No song is currently playing.")

    @app_commands.command(name="resume", description="Resumes the paused song.")
    async def resume(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.followup.send("I'm not connected to a voice channel.")

        if vc.is_paused():
            vc.resume()
            await interaction.followup.send("▶️ Song resumed.")
        else:
            await interaction.followup.send("No song is currently paused.")

    @app_commands.command(name="skip", description="Skips the current song.")
    async def skip(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.followup.send("I'm not connected to a voice channel.")

        if vc.is_playing() or vc.is_paused():
            vc.stop()
            await interaction.followup.send("⏭️ Song skipped.")
        else:
            await interaction.followup.send("No song is currently playing.")

    @app_commands.command(
        name="queue", description="Show the queue, or add a song to it."
    )
    @app_commands.describe(url="Optional: a YouTube URL to add to the queue.")
    async def queue(self, interaction: discord.Interaction, url: str | None = None):
        await interaction.response.defer(thinking=True)
        guild_id = interaction.guild.id

        if url:
            vc = await self._ensure_voice(interaction)
            if vc is None:
                return

            self.queues.setdefault(guild_id, []).append(url)

            title = url
            try:
                data = await self._extract_info(url)
                title = data.get("title", url)
            except Exception:
                pass

            if not vc.is_playing() and not vc.is_paused():
                await self._play_next_in_queue(guild_id, interaction)
            else:
                await interaction.followup.send(
                    f"✅ Added to queue: **{title}** (Position: {len(self.queues[guild_id])})"
                )
            return

        queue = self.queues.get(guild_id) or []
        if not queue:
            return await interaction.followup.send(
                "Queue is empty. Use `/music play` or `/music queue <URL>` to add songs."
            )

        max_display = 10
        lines = ["Here's the queue:"]
        for i, queued_url in enumerate(queue[:max_display]):
            try:
                data = await self._extract_info(queued_url)
                title = data.get("title", queued_url)
            except Exception:
                title = "Error fetching title"
            lines.append(f"**{i + 1}.** {title}")

        if len(queue) > max_display:
            lines.append(f"\n…and {len(queue) - max_display} more songs.")

        embed = discord.Embed(
            title="Music Queue",
            description="\n".join(lines),
            color=discord.Color.blue(),
        )
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="join", description="Make the bot join your voice channel.")
    async def join(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)

        if not interaction.user.voice or not interaction.user.voice.channel:
            return await interaction.followup.send(
                "You must be in a voice channel for me to join."
            )

        target = interaction.user.voice.channel
        vc = interaction.guild.voice_client

        if vc is None:
            await target.connect()
            await interaction.followup.send(f"✅ Joined voice channel: **{target.name}**")
        elif vc.channel == target:
            await interaction.followup.send("I'm already in your voice channel.")
        else:
            await vc.move_to(target)
            await interaction.followup.send(f"✅ Moved to voice channel: **{target.name}**")

    @app_commands.command(
        name="leave",
        description="Make the bot leave the voice channel and clear the queue.",
    )
    async def leave(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        guild_id = interaction.guild.id
        vc = interaction.guild.voice_client

        if not vc or not vc.is_connected():
            return await interaction.followup.send("I'm not connected to a voice channel.")

        if vc.is_playing() or vc.is_paused():
            vc.stop()

        self.queues.pop(guild_id, None)
        await vc.disconnect()
        await interaction.followup.send("👋 I left the voice channel and cleared the queue.")


async def setup(client: discord.Client, tree: app_commands.CommandTree):
    tree.add_command(Music(client))
