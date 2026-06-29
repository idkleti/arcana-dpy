"""Fun commands: greetings, parrot, magic 8-ball."""
import random
import discord
from discord import app_commands
import config

class Fun(app_commands.Group):
    def __init__(self, client: discord.Client):
        super().__init__(name="fun", description="Fun bot commands.")
        self.client = client

    @app_commands.command(name="hello", description="Greets the user with a random hello.")
    async def hello(self, interaction: discord.Interaction):
        await interaction.response.send_message(random.choice(config.GREETINGS))

    @app_commands.command(
        name="say",
        description="Make the bot repeat what you wrote (not anonymous).",
    )
    async def say(self, interaction: discord.Interaction, message: str):
        # no mass-mentions
        allowed = discord.AllowedMentions(everyone=False, roles=False, users=True)
        await interaction.response.send_message(message, allowed_mentions=allowed)

    @app_commands.command(name="8ball", description="Ask the bot a yes/no question.")
    async def eight_ball(self, interaction: discord.Interaction, question: str):
        # interaction.user is User in DMs (no .nick); use display_name to cover both.
        await interaction.response.send_message(
            f"❓ | **{interaction.user.display_name}** asked: **{question}**\n"
            f"The bot says... **{random.choice(config.ANSWERS)}**"
        )

async def setup(client: discord.Client, tree: app_commands.CommandTree):
    tree.add_command(Fun(client))
