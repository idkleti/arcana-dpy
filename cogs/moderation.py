"""
    Moderation commands: warn / showwarnings / delwarn / ban / kick / mute / unmute / history.

    Every successful action is logged to the `moderation_log` table (see db.py).
    The `id` column doubles as the public action ID surfaced to mods in /history and /showwarnings, and accepted by /delwarn.
"""
import datetime
import logging
import discord
from discord import app_commands
import db

log = logging.getLogger(__name__)

# Action names match the `action` column in moderation_log.
# Keeping them as a constant makes it easier to add new actions later (e.g. softban) :)
ACTION_WARN = "warn"
ACTION_BAN = "ban"
ACTION_KICK = "kick"
ACTION_MUTE = "mute"
ACTION_UNMUTE = "unmute"

ACTION_EMOJI = {
    ACTION_WARN: "⚠️",
    ACTION_BAN: "🔨",
    ACTION_KICK: "👢",
    ACTION_MUTE: "🔇",
    ACTION_UNMUTE: "🔊",
}


# --- DB helpers ---

async def _log_action(
    guild_id: int,
    user_id: int,
    moderator_id: int,
    action: str,
    reason: str,
    duration_minutes: int | None = None,
) -> int:
    """Insert a moderation event. Returns the new log row's ID."""
    async with db.pool().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "INSERT INTO moderation_log "
                "(guild_id, user_id, moderator, action, reason, duration_minutes) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (guild_id, user_id, moderator_id, action, reason, duration_minutes),
            )
            return cur.lastrowid

async def _list_actions(
    guild_id: int, user_id: int, action: str | None = None
) -> list[dict]:
    """All actions for a user, oldest first. 
        Optionally filter to one action type."""
    query = (
        "SELECT id, moderator, action, reason, duration_minutes, created_at "
        "FROM moderation_log WHERE guild_id=%s AND user_id=%s"
    )
    params: tuple = (guild_id, user_id)
    if action is not None:
        query += " AND action=%s"
        params += (action,)
    query += " ORDER BY id ASC"

    async with db.pool().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(query, params)
            rows = await cur.fetchall()

    return [
        {
            "id": r[0],
            "moderator": r[1],
            "action": r[2],
            "reason": r[3],
            "duration_minutes": r[4],
            "created_at": r[5],
        }
        for r in rows
    ]

async def _count_action(guild_id: int, user_id: int, action: str) -> int:
    async with db.pool().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT COUNT(*) FROM moderation_log "
                "WHERE guild_id=%s AND user_id=%s AND action=%s",
                (guild_id, user_id, action),
            )
            (total,) = await cur.fetchone()
    return total

async def _delete_warning(guild_id: int, user_id: int, log_id: int) -> str | None:
    """Hard-delete a warning. Returns its reason, or None if no matching warn exists.
    Restricted to action='warn' so /delwarn can't accidentally remove ban/kick records
    """
    async with db.pool().acquire() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT reason FROM moderation_log "
                "WHERE id=%s AND guild_id=%s AND user_id=%s AND action=%s",
                (log_id, guild_id, user_id, ACTION_WARN),
            )
            row = await cur.fetchone()
            if not row:
                return None
            reason = row[0]
            await cur.execute("DELETE FROM moderation_log WHERE id=%s", (log_id,))
    return reason


# --- Cog ---
def _ensure_utc(dt: datetime.datetime) -> datetime.datetime:
    """MySQL DATETIME columns come back naive so we assume UTC for Discord formatting."""
    return dt.replace(tzinfo=datetime.timezone.utc) if dt.tzinfo is None else dt

class Moderation(app_commands.Group):
    def __init__(self, client: discord.Client):
        super().__init__(name="moderation", description="Moderation commands.")
        self.client = client

    @staticmethod
    def _can_moderate(interaction: discord.Interaction, member: discord.Member) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        return interaction.user.top_role > member.top_role

    @staticmethod
    def _bot_can_moderate(interaction: discord.Interaction, member: discord.Member) -> bool:
        return interaction.guild.me.top_role > member.top_role

    # --- warnings ---
    @app_commands.command(name="warn", description="Issue a warning to a user.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member to warn.", reason="The reason for the warning.")
    async def warn(
        self, interaction: discord.Interaction, member: discord.Member, reason: str
    ):
        if not self._can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ You can't warn this member because their role is equal to or higher than yours.",
                ephemeral=True,
            )

        log_id = await _log_action(
            interaction.guild_id, member.id, interaction.user.id, ACTION_WARN, reason
        )
        total = await _count_action(interaction.guild_id, member.id, ACTION_WARN)

        await interaction.response.send_message(
            f"⚠️ **{member.name}** has been warned (ID `{log_id}`).\n"
            f"**Reason:** {reason}\n"
            f"They now have **{total}** warning(s)."
        )

    @app_commands.command(name="showwarnings", description="Show a user's warnings.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member whose warnings you want to see.")
    async def showwarnings(self, interaction: discord.Interaction, member: discord.Member):
        warns = await _list_actions(interaction.guild_id, member.id, ACTION_WARN)
        if not warns:
            return await interaction.response.send_message(
                f"✅ **{member.display_name}** has no warnings.", ephemeral=True
            )
        embed = discord.Embed(
            title=f"⚠️ Warnings for {member.display_name} ({len(warns)})",
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        for warn in warns:
            embed.add_field(
                name=f"Warning #{warn['id']}",
                value=(
                    f"**ID:** `{warn['id']}`\n"
                    f"**Moderator:** <@{warn['moderator']}>\n"
                    f"**Time:** {discord.utils.format_dt(_ensure_utc(warn['created_at']), 'R')}\n"
                    f"**Reason:** {warn['reason']}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="delwarn", description="Remove a specific warning from a user.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to remove a warning from.",
        warning_id="ID of the warning to remove (see /moderation showwarnings).",
    )
    async def delwarn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        warning_id: int,
    ):
        reason = await _delete_warning(interaction.guild_id, member.id, warning_id)
        if reason is None:
            return await interaction.response.send_message(
                f"❌ Warning with ID `{warning_id}` not found for **{member.display_name}**.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"✅ Warning ID `{warning_id}` for **{member.display_name}** has been removed.\n"
            f"**Reason:** {reason}"
        )

    # --- history ---
    @app_commands.command(
        name="history", description="Show a user's full moderation history."
    )
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(member="The member whose history you want to see.")
    async def history(self, interaction: discord.Interaction, member: discord.Member):
        actions = await _list_actions(interaction.guild_id, member.id)
        if not actions:
            return await interaction.response.send_message(
                f"✅ **{member.display_name}** has no moderation history.", ephemeral=True
            )

        # Summary counts make it easy to eyeball repeat offenders.
        counts: dict[str, int] = {}
        for entry in actions:
            counts[entry["action"]] = counts.get(entry["action"], 0) + 1
        summary = " · ".join(
            f"{ACTION_EMOJI.get(act, '•')} {act}: {n}"
            for act, n in sorted(counts.items())
        )

        embed = discord.Embed(
            title=f"Moderation history for {member.display_name}",
            description=summary,
            color=discord.Color.orange(),
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)

        # Discord embeds cap at 25 fields. Show the most recent 25, oldest of that slice first so the chronological flow still reads top-to-bottom.
        recent = actions[-25:]
        if len(actions) > 25:
            embed.set_footer(text=f"Showing the latest 25 of {len(actions)} events.")

        for entry in recent:
            emoji = ACTION_EMOJI.get(entry["action"], "•")
            duration = entry.get("duration_minutes")
            duration_line = (
                f"**Duration:** {duration} minute(s)\n" if duration is not None else ""
            )
            embed.add_field(
                name=f"#{entry['id']} · {emoji} {entry['action']}",
                value=(
                    f"**Moderator:** <@{entry['moderator']}>\n"
                    f"**Time:** {discord.utils.format_dt(_ensure_utc(entry['created_at']), 'R')}\n"
                    f"{duration_line}"
                    f"**Reason:** {entry['reason']}"
                ),
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # --- ban / kick / mute / unmute ---
    @app_commands.command(name="ban", description="Ban a user from the server.")
    @app_commands.checks.has_permissions(ban_members=True)
    @app_commands.describe(
        member="The member to ban.",
        reason="The reason for the ban (will be logged).",
    )
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided.",
    ):
        if not self._can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ You can't ban this member because their role is equal to or higher than yours.",
                ephemeral=True,
            )
        if not self._bot_can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ My role is not high enough to ban this member.", ephemeral=True
            )

        try:
            await member.ban(reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to ban this user.", ephemeral=True
            )

        await _log_action(
            interaction.guild_id, member.id, interaction.user.id, ACTION_BAN, reason
        )

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been banned.\n**Reason:** {reason}"
        )

    @app_commands.command(name="kick", description="Kick a user from the server.")
    @app_commands.checks.has_permissions(kick_members=True)
    @app_commands.describe(
        member="The member to kick.",
        reason="The reason for the kick (will be logged).",
    )
    async def kick(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided.",
    ):
        if not self._can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ You can't kick this member because their role is equal to or higher than yours.",
                ephemeral=True,
            )
        if not self._bot_can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ My role is not high enough to kick this member.", ephemeral=True
            )

        try:
            await member.kick(reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to kick this user.", ephemeral=True
            )

        await _log_action(
            interaction.guild_id, member.id, interaction.user.id, ACTION_KICK, reason
        )

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been kicked.\n**Reason:** {reason}"
        )

    @app_commands.command(name="mute", description="Timeout (mute) a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to mute.",
        duration_minutes="Mute duration in minutes (max 40320 = 28 days).",
        reason="The reason for the mute.",
    )
    async def mute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration_minutes: app_commands.Range[int, 1, 40320],
        reason: str = "No reason provided.",
    ):
        if not self._can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ You can't mute this member because their role is equal to or higher than yours.",
                ephemeral=True,
            )
        if not self._bot_can_moderate(interaction, member):
            return await interaction.response.send_message(
                "❌ My role is not high enough to mute this member.", ephemeral=True
            )

        try:
            await member.timeout(datetime.timedelta(minutes=duration_minutes), reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to mute this user.", ephemeral=True
            )

        await _log_action(
            interaction.guild_id,
            member.id,
            interaction.user.id,
            ACTION_MUTE,
            reason,
            duration_minutes=duration_minutes,
        )

        if duration_minutes >= 60 and duration_minutes % 60 == 0:
            duration_display = f"{duration_minutes // 60} hour(s)"
        else:
            duration_display = f"{duration_minutes} minute(s)"

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been muted for **{duration_display}**.\n"
            f"**Reason:** {reason}"
        )

    @app_commands.command(name="unmute", description="Remove timeout (unmute) a user.")
    @app_commands.checks.has_permissions(moderate_members=True)
    @app_commands.describe(
        member="The member to unmute.",
        reason="The reason for removing the mute.",
    )
    async def unmute(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided.",
    ):
        if not member.is_timed_out():
            return await interaction.response.send_message(
                "❌ This member is not currently muted.", ephemeral=True
            )

        try:
            await member.timeout(None, reason=reason)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "❌ I don't have permission to unmute this user.", ephemeral=True
            )

        await _log_action(
            interaction.guild_id, member.id, interaction.user.id, ACTION_UNMUTE, reason
        )

        await interaction.response.send_message(
            f"✅ **{member.display_name}** has been unmuted.\n**Reason:** {reason}"
        )

async def setup(client: discord.Client, tree: app_commands.CommandTree):
    tree.add_command(Moderation(client))
