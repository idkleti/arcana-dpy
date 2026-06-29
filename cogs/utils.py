"""Utility commands: ping / serverinfo / userinfo / avatar, plus /help."""

import datetime
import discord
from discord import app_commands
import config

class Utils(app_commands.Group):
    def __init__(self, client: discord.Client):
        super().__init__(name="utils", description="Utility commands.")
        self.client = client

    @app_commands.command(name="ping", description="Show the bot's latency.")
    async def ping(self, interaction: discord.Interaction):
        latency_ms = round(self.client.latency * 1000)
        await interaction.response.send_message(f"🏓 Pong! Latency: **{latency_ms}ms**")

    @app_commands.command(name="serverinfo", description="Show information about the current server.")
    async def serverinfo(self, interaction: discord.Interaction):
        guild = interaction.guild
        if not guild:
            return await interaction.response.send_message(
                "This command can only be used in a server.", ephemeral=True
            )

        embed = discord.Embed(title=f"Server Info: {guild.name}", color=discord.Color.blue())
        embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        embed.add_field(name="Server ID", value=guild.id, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.add_field(
            name="Boost Level",
            value=f"Level {guild.premium_tier} ({guild.premium_subscription_count} boosts)",
            inline=True,
        )
        embed.add_field(
            name="Created On",
            value=discord.utils.format_dt(guild.created_at, "F"),
            inline=False,
        )
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="userinfo", description="Show extensive information about a user.")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        user = user or interaction.user

        color = (
            user.color
            if isinstance(user, discord.Member) and user.color != discord.Color.default()
            else discord.Color.blue()
        )

        embed = discord.Embed(title=f"User Info: {user.display_name}", color=color)
        embed.set_thumbnail(url=user.display_avatar.url)

        embed.add_field(name="Username", value=f"@{user.name}", inline=True)
        if user.discriminator != "0":
            embed.add_field(name="Discriminator", value=f"#{user.discriminator}", inline=True)
        else:
            embed.add_field(name="Global Name", value=user.global_name or "N/A", inline=True)
        embed.add_field(name="ID", value=user.id, inline=True)
        embed.add_field(
            name="Account Created",
            value=discord.utils.format_dt(user.created_at, "F"),
            inline=False,
        )

        if isinstance(user, discord.Member):
            if user.joined_at:
                embed.add_field(
                    name="Joined Server",
                    value=discord.utils.format_dt(user.joined_at, "F"),
                    inline=True,
                )
            embed.add_field(name="Nickname", value=user.nick or "None", inline=True)

            status_label = {
                discord.Status.online: "🟢 Online",
                discord.Status.idle: "🟡 Idle",
                discord.Status.dnd: "🔴 Do Not Disturb",
                discord.Status.offline: "⚫ Offline",
            }.get(user.status, "❓ Unknown")
            embed.add_field(name="Status", value=status_label, inline=True)

            activity_lines = []
            for activity in user.activities:
                if isinstance(activity, discord.Game):
                    activity_lines.append(f"Playing **{activity.name}**")
                elif isinstance(activity, discord.Streaming):
                    activity_lines.append(
                        f"Streaming **{activity.name}** on [{activity.platform}]({activity.url})"
                    )
                elif isinstance(activity, discord.Activity):
                    if activity.type == discord.ActivityType.custom:
                        activity_lines.append(f"Custom Status: {activity.name}")
                    elif activity.type == discord.ActivityType.listening:
                        activity_lines.append(f"Listening to **{activity.name}**")
                    else:
                        activity_lines.append(f"{activity.type.name.capitalize()} **{activity.name}**")
            
            embed.add_field(
                name="Activity",
                value="\n".join(activity_lines) if activity_lines else "None",
                inline=False,
            )

            roles = [r.mention for r in user.roles if r.name != "@everyone"]
            embed.add_field(
                name=f"Roles ({len(roles)})" if roles else "Roles",
                value=", ".join(roles) if roles else "No roles (other than @everyone)",
                inline=False,
            )

            if user.premium_since:
                embed.add_field(
                    name="Server Booster",
                    value=f"Since {discord.utils.format_dt(user.premium_since, 'D')}",
                    inline=True,
                )
            else:
                embed.add_field(name="Server Booster", value="No", inline=True)

        embed.set_footer(
            text=f"Requested by {interaction.user.display_name}",
            icon_url=interaction.user.display_avatar.url,
        )

        embed.timestamp = datetime.datetime.now()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="avatar", description="Show a user's avatar.")
    async def avatar(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        user = user or interaction.user

        embed = discord.Embed(title=f"Avatar of {user.display_name}", color=discord.Color.purple())
        embed.set_image(url=user.display_avatar.url)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)


# ---- /help ---
# Built from the command tree once everything else is loaded.
ALL_COMMANDS_MAP: dict[str, dict] = {}

def _build_command_map(tree: app_commands.CommandTree) -> dict:
    """Index every / command and subcommand by both its short and full name."""
    command_map: dict[str, dict] = {}

    for command in tree.get_commands():
        if isinstance(command, app_commands.Group):
            command_map[command.name.lower()] = {
                "name": command.name,
                "full_name": command.name,
                "description": command.description,
                "type": "group",
            }
            for sub in command.commands:
                entry = {
                    "name": sub.name,
                    "full_name": f"{command.name} {sub.name}",
                    "description": sub.description,
                    "parent_group": command.name,
                    "type": "command",
                }
                # Allow lookup by both "ping" and "utils ping".
                command_map[sub.name.lower()] = entry
                command_map[entry["full_name"].lower()] = entry
        else:
            command_map[command.name.lower()] = {
                "name": command.name,
                "full_name": command.name,
                "description": command.description,
                "type": "command",
            }

    return command_map

@app_commands.command(
    name="help",
    description="List all available commands, or show details about a specific one.",
)
@app_commands.describe(command_name="Name of the command to get more info on.")
async def help_command(
    interaction: discord.Interaction, command_name: str | None = None
):
    if command_name:
        info = ALL_COMMANDS_MAP.get(command_name.lower())
        if not info:
            return await interaction.response.send_message(
                f"❌ Command **/{command_name}** not found. Use **/help** to see all commands.",
                ephemeral=True,
            )

        embed = discord.Embed(
            title=f"Command Info: /{info['full_name']}",
            description=info["description"],
            color=discord.Color.green(),
        )

        if info.get("parent_group"):
            embed.add_field(
                name="Group (Category)",
                value=f"This command is part of the `/{info['parent_group']}` group.",
                inline=False,
            )

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        embed.timestamp = datetime.datetime.now()
        return await interaction.response.send_message(embed=embed)

    embed = discord.Embed(
        title="Bot Commands",
        description=(
            "Here are all the commands you can use.\n"
            "Use `/help [command_name]` for details on a specific one."
        ),
        color=discord.Color.blue(),
    )

    for category, commands_list in config.COMMAND_CATEGORIES.items():
        if not commands_list:
            continue
        emoji = config.CATEGORY_EMOJIS.get(category, "❓")
        commands_text = " ".join(f"`/{cmd['name']}`" for cmd in commands_list)
        embed.add_field(name=f"{emoji} {category}", value=commands_text, inline=False)

    embed.set_footer(text="Use /<command> to execute a command.")
    embed.timestamp = datetime.datetime.now()
    await interaction.response.send_message(embed=embed)

async def setup(client: discord.Client, tree: app_commands.CommandTree):
    global ALL_COMMANDS_MAP
    tree.add_command(Utils(client))
    tree.add_command(help_command)
    ALL_COMMANDS_MAP = _build_command_map(tree)
