"""Poll commands: yes/no polls, multiple-choice polls, closing polls."""
import logging
import discord
from discord import app_commands
import config

log = logging.getLogger(__name__)

YESNO_NO = "❎"
YESNO_YES = "✅"

class Polls(app_commands.Group):
    def __init__(self, client: discord.Client):
        super().__init__(name="poll", description="Commands for managing polls.")
        self.client = client
        # {guild_id: {user_id: message_id}}: which user has which open poll, per guild.
        self.active_polls: dict[int, dict[int, int]] = {}
        # {guild_id: {message_id: poll_info}}: metadata for each open poll message.
        self.poll_messages: dict[int, dict[int, dict]] = {}

    # --- internals ---

    def _has_active_poll(self, guild_id: int, user_id: int) -> bool:
        return user_id in self.active_polls.get(guild_id, {})

    def _track_poll(self, guild_id: int, user_id: int, message_id: int, info: dict):
        self.active_polls.setdefault(guild_id, {})[user_id] = message_id
        self.poll_messages.setdefault(guild_id, {})[message_id] = info

    def _untrack_poll(self, guild_id: int, user_id: int, message_id: int):
        guild_active = self.active_polls.get(guild_id, {})
        guild_active.pop(user_id, None)
        if not guild_active:
            self.active_polls.pop(guild_id, None)

        guild_msgs = self.poll_messages.get(guild_id, {})
        guild_msgs.pop(message_id, None)
        if not guild_msgs:
            self.poll_messages.pop(guild_id, None)

    @staticmethod
    def _author_block(user: discord.abc.User) -> dict:
        return {
            "name": user.display_name,
            "icon_url": user.avatar.url if user.avatar else None,
        }

    # --- commands ---

    @app_commands.command(name="yesnopoll", description="Start a yes/no poll.")
    async def yesnopoll(
        self,
        interaction: discord.Interaction,
        question: str,
        nooption: str,
        yesoption: str,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        guild_id = interaction.guild.id
        if self._has_active_poll(guild_id, interaction.user.id):
            return await interaction.response.send_message(
                "You already have an active poll in this server. Close it with `/poll close` first.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title=question,
            description=f"React with {YESNO_NO} or {YESNO_YES} to vote.",
            color=discord.Color.green(),
        )
        embed.add_field(name=f"{YESNO_NO} {nooption}", value=" ", inline=False)
        embed.add_field(name=f"{YESNO_YES} {yesoption}", value=" ", inline=False)
        embed.set_footer(
            text=f"Poll started by {interaction.user.display_name} | Use /poll close to end."
        )
        embed.set_author(**self._author_block(interaction.user))

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()
        await message.add_reaction(YESNO_NO)
        await message.add_reaction(YESNO_YES)

        self._track_poll(
            guild_id,
            interaction.user.id,
            message.id,
            {
                "author_id": interaction.user.id,
                "channel_id": interaction.channel_id,
                "guild_id": interaction.guild_id,
                "type": "yesno",
                "question": question,
                "no_option": nooption,
                "yes_option": yesoption,
            },
        )

    @app_commands.command(name="choicepoll", description="Start a multiple-choice poll (max 5 options).")
    @app_commands.describe(
        question="The poll question.",
        option1="First option.",
        option2="Second option.",
        option3="Third option (optional).",
        option4="Fourth option (optional).",
        option5="Fifth option (optional).",
    )
    async def choicepoll(
        self,
        interaction: discord.Interaction,
        question: str,
        option1: str,
        option2: str,
        option3: str | None = None,
        option4: str | None = None,
        option5: str | None = None,
    ):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        guild_id = interaction.guild.id
        if self._has_active_poll(guild_id, interaction.user.id):
            return await interaction.response.send_message(
                "You already have an active poll in this server. Close it with `/poll close` first.",
                ephemeral=True,
            )

        options = [o for o in (option1, option2, option3, option4, option5) if o is not None]
        if len(options) < 2:
            return await interaction.response.send_message(
                "You need to provide at least two options.", ephemeral=True
            )
        if len(options) > len(config.OPTION_EMOJIS):
            return await interaction.response.send_message(
                f"You can provide at most {len(config.OPTION_EMOJIS)} options.",
                ephemeral=True,
            )

        emojis = config.OPTION_EMOJIS[: len(options)]
        description_lines = ["React with the corresponding emoji to vote:"]
        description_lines += [f"{e} {text}" for e, text in zip(emojis, options)]

        embed = discord.Embed(
            title=question,
            description="\n".join(description_lines),
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Poll started by {interaction.user.display_name} | Use /poll close to end."
        )
        embed.set_author(**self._author_block(interaction.user))

        await interaction.response.send_message(embed=embed)
        message = await interaction.original_response()

        for emoji in emojis:
            await message.add_reaction(emoji)

        self._track_poll(
            guild_id,
            interaction.user.id,
            message.id,
            {
                "author_id": interaction.user.id,
                "channel_id": interaction.channel_id,
                "guild_id": interaction.guild_id,
                "type": "choice",
                "question": question,
                "options": options,
                "emojis": emojis,
            },
        )

    @app_commands.command(name="close", description="Close your active poll and show the results.")
    async def close(self, interaction: discord.Interaction):
        if not interaction.guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        guild_id = interaction.guild.id
        if not self._has_active_poll(guild_id, interaction.user.id):
            return await interaction.response.send_message(
                "You don't have an active poll in this server.", ephemeral=True
            )

        message_id = self.active_polls[guild_id][interaction.user.id]
        poll_info = self.poll_messages.get(guild_id, {}).get(message_id)
        if not poll_info:
            self._untrack_poll(guild_id, interaction.user.id, message_id)
            return await interaction.response.send_message(
                "I could not retrieve your active poll. Try starting a new one.",
                ephemeral=True,
            )

        try:
            channel = self.client.get_channel(poll_info["channel_id"]) or await self.client.fetch_channel(
                poll_info["channel_id"]
            )
            poll_message = await channel.fetch_message(message_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException) as e:
            self._untrack_poll(guild_id, interaction.user.id, message_id)
            log.warning(
                "Could not fetch poll message %s in guild %s: %s", message_id, guild_id, e
            )
            return await interaction.response.send_message(
                "I couldn't find your poll message (deleted, or I lack channel access).",
                ephemeral=True,
            )

        await interaction.response.defer(ephemeral=True)
        await self._render_results(poll_message, interaction.user, poll_info)
        self._untrack_poll(guild_id, interaction.user.id, message_id)
        await interaction.followup.send("Your poll has been closed and the results are in!", ephemeral=True)

    async def _render_results(
        self,
        poll_message: discord.Message,
        author: discord.abc.User,
        poll_info: dict,
    ):
        poll_type = poll_info.get("type", "unknown")
        question = poll_info.get("question", "Poll")

        result_embed = discord.Embed(
            title=f"Poll Closed: {question}",
            description="Final results:",
            color=discord.Color.dark_grey(),
        )

        if poll_type == "yesno":
            no_count = await self._count_reactors(poll_message, YESNO_NO)
            yes_count = await self._count_reactors(poll_message, YESNO_YES)
            total = no_count + yes_count

            no_option = poll_info.get("no_option", "No")
            yes_option = poll_info.get("yes_option", "Yes")

            result_embed.add_field(
                name=f"{YESNO_NO} {no_option}",
                value=f"Votes: **{no_count}** ({self._pct(no_count, total)})",
                inline=False,
            )
            result_embed.add_field(
                name=f"{YESNO_YES} {yes_option}",
                value=f"Votes: **{yes_count}** ({self._pct(yes_count, total)})",
                inline=False,
            )
            result_embed.add_field(name="Total Votes", value=f"**{total}**", inline=False)

        elif poll_type == "choice":
            options = poll_info.get("options", [])
            emojis = poll_info.get("emojis", [])
            counts = {emoji: await self._count_reactors(poll_message, emoji) for emoji in emojis}
            total = sum(counts.values())

            for emoji, option_text in zip(emojis, options):
                count = counts.get(emoji, 0)
                result_embed.add_field(
                    name=f"{emoji} {option_text}",
                    value=f"Votes: **{count}** ({self._pct(count, total)})",
                    inline=False,
                )
            result_embed.add_field(name="Total Votes", value=f"**{total}**", inline=False)

        else:
            result_embed.description = "Could not determine results for this poll type."

        result_embed.set_footer(text=f"Poll closed by author {author.display_name}")
        result_embed.set_author(**self._author_block(author))

        await poll_message.edit(embed=result_embed)
        await poll_message.clear_reactions()

    async def _count_reactors(self, message: discord.Message, emoji: str) -> int:
        for reaction in message.reactions:
            if str(reaction.emoji) == emoji:
                count = 0
                async for user in reaction.users():
                    if user.id != self.client.user.id:
                        count += 1
                return count
        return 0

    @staticmethod
    def _pct(value: int, total: int) -> str:
        if total <= 0:
            return "0.00%"
        return f"{(value / total) * 100:.2f}%"


async def setup(client: discord.Client, tree: app_commands.CommandTree):
    tree.add_command(Polls(client))
