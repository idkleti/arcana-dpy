"""Dice roller. With `faces` argument: roll immediately. Without: show a selector."""
import asyncio
import random
import discord
from discord import app_commands
from .views import DiceRollView

async def _roll_and_display(
    original_interaction: discord.Interaction,
    num_faces: int,
    interaction_to_defer: discord.Interaction | None = None,
):
    """Animate a 3s rolling message and reveal the result."""
    if interaction_to_defer is not None and not interaction_to_defer.response.is_done():
        await interaction_to_defer.response.defer()
    elif interaction_to_defer is None and not original_interaction.response.is_done():
        await original_interaction.response.defer()

    rolling = discord.Embed(
        title="🎲 Rolling the Dice...",
        description=f"You chose a **{num_faces}**-sided die. The result will be here shortly...",
        color=discord.Color.light_grey(),
    )
    await original_interaction.edit_original_response(embed=rolling, view=None)
    await asyncio.sleep(3)

    result = random.randint(1, num_faces)
    color = discord.Color.green() if result > num_faces / 2 else discord.Color.red()

    final = discord.Embed(
        title="🎲 Roll Result! 🎲",
        description=(
            f"{original_interaction.user.mention}, you rolled a **{num_faces}**-sided die.\n\n"
            f"The result is: **{result}**!"
        ),
        color=color,
    )
    final.set_footer(text=f"Rolled by {original_interaction.user.display_name}")
    await original_interaction.edit_original_response(embed=final, view=None)

def register(group: app_commands.Group, client: discord.Client) -> None:
    @group.command(
        name="roll",
        description="Roll a die. Pass `faces` directly, or pick from a menu.",
    )
    @app_commands.describe(faces="Number of faces (1 to 1,000,000).")
    async def roll(
        interaction: discord.Interaction,
        faces: app_commands.Range[int, 1, 1_000_000] | None = None,
    ):
        if faces is not None:
            await _roll_and_display(interaction, faces)
            return

        embed = discord.Embed(
            title="🎲 Choose Your Die! 🎲",
            description="Pick a preset from the menu, or choose Custom… to enter your own.",
            color=discord.Color.blue(),
        )
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        view = DiceRollView(interaction, _roll_and_display)
        await interaction.response.send_message(embed=embed, view=view)
