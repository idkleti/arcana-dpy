import logging

import discord
from discord import app_commands

import config
import db
from cogs import fun, games, moderation, music, poll, utils

log = logging.getLogger("bot")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# utils must come last cause its setup() walks the populated tree to build /help.
# if you want to remove a cog just take it out of this list below and edit out the commands in cogs/utils.py
COGS = [fun, music, poll, games, moderation, utils]

class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await db.init()

        log.info("--- Loading cogs ---")
        for cog_module in COGS:
            name = cog_module.__name__.rsplit(".", 1)[-1]
            try:
                await cog_module.setup(self, self.tree)
                log.info("Loaded cog: %s", name)
            except Exception:
                log.exception("Failed to load cog: %s", name)
        log.info("--------------------")

        await self.tree.sync()

    async def close(self):
        await db.close()
        await super().close()


client = Bot()

@client.event
async def on_ready():
    await client.change_presence(activity=discord.Game(name="/help to get started ;)"))
    log.info("Logged in as %s (ID: %s)", client.user, client.user.id)

@client.event
async def on_app_command_error(
    interaction: discord.Interaction, error: app_commands.AppCommandError
):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Slow down! This command is on cooldown. Try again in {error.retry_after:.2f}s."
    elif isinstance(error, app_commands.MissingPermissions):
        msg = f"You don't have the required permissions: {', '.join(error.missing_permissions)}."
    elif isinstance(error, app_commands.BotMissingPermissions):
        msg = f"I'm missing the required permissions: {', '.join(error.missing_permissions)}."
    else:
        cmd = interaction.command.name if interaction.command else "<unknown>"
        guild = interaction.guild.name if interaction.guild else "DM"
        log.exception(
            "Unhandled error in command '%s' by %s in %s",
            cmd, interaction.user, guild,
        )
        msg = "An unexpected error occurred while executing the command."

    if interaction.response.is_done():
        await interaction.followup.send(msg, ephemeral=True)
    else:
        await interaction.response.send_message(msg, ephemeral=True)


if __name__ == "__main__":
    client.run(config.TOKEN, log_handler=None)
