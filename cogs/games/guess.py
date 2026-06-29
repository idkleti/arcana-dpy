"""Guess the number: anyone in the channel can guess until someone wins or attempts run out."""
import asyncio
import logging
import random
import discord
from discord import app_commands

log = logging.getLogger(__name__)

def register(group: app_commands.Group, client: discord.Client) -> None:
    @group.command(name="guess", description="Start a 'guess the number' game.")
    @app_commands.describe(
        min_num="Minimum of the range (default: 1).",
        max_num="Maximum of the range (default: 100).",
    )
    async def guess(
        interaction: discord.Interaction, min_num: int = 1, max_num: int = 100
    ):
        if min_num >= max_num:
            return await interaction.response.send_message(
                "Minimum must be less than the maximum.", ephemeral=True
            )
        if (max_num - min_num) > 1_000_000:
            return await interaction.response.send_message(
                "Range is too large. Keep it within 1,000,000.", ephemeral=True
            )

        active = group.active_guess_games
        if interaction.channel_id in active and active[interaction.channel_id]["game_running"]:
            return await interaction.response.send_message(
                "A 'guess the number' game is already running in this channel.",
                ephemeral=True,
            )

        secret_number = random.randint(min_num, max_num)
        max_attempts = max(7, int((max_num - min_num + 1) ** 0.5 * 2.5))

        initial_embed = discord.Embed(
            title="🎯 Guess the Number! 🎯",
            description=(
                f"I'm thinking of a number between **{min_num}** and **{max_num}**.\n"
                f"You have **{max_attempts}** total attempts. Anyone in this channel can guess!\n\n"
                "**Attempts Made:** 0\n"
                "**Last Player:** None\n"
                "**Last Guess:** None\n"
            ),
            color=discord.Color.blue(),
        )
        initial_embed.set_footer(text=f"Game started by {interaction.user.display_name}")

        await interaction.response.send_message(embed=initial_embed)
        game_message = await interaction.original_response()

        game_state = {
            "secret_number": secret_number,
            "attempts": 0,
            "max_attempts": max_attempts,
            "min_range": min_num,
            "max_range": max_num,
            "starter_id": interaction.user.id,
            "message": game_message,
            "guesses": {},
            "game_running": True,
        }
        active[interaction.channel_id] = game_state

        def check_guess(message: discord.Message) -> bool:
            return (
                message.channel.id == interaction.channel.id
                and message.content.isdigit()
                and not message.author.bot
            )

        try:
            while game_state["attempts"] < game_state["max_attempts"] and game_state["game_running"]:
                try:
                    guess_message = await client.wait_for(
                        "message", check=check_guess, timeout=120.0
                    )
                except asyncio.TimeoutError:
                    game_state["game_running"] = False
                    final = discord.Embed(
                        title="⏰ TIME'S UP! ⏰",
                        description=f"No one guessed in time. The number was **{secret_number}**.",
                        color=discord.Color.red(),
                    )
                    final.set_footer(text=f"Game started by {interaction.user.display_name}")
                    await game_message.edit(embed=final)
                    return

                user_guess = int(guess_message.content)
                guesser = guess_message.author
                game_state["attempts"] += 1
                game_state["guesses"].setdefault(guesser.id, []).append(user_guess)

                current_desc = (
                    f"I'm thinking of a number between **{min_num}** and **{max_num}**.\n"
                    f"You have **{max_attempts}** total attempts. Anyone in this channel can guess!\n\n"
                    f"**Attempts Made:** {game_state['attempts']}/{game_state['max_attempts']}\n"
                    f"**Last Player:** {guesser.mention}\n"
                    f"**Last Guess:** {user_guess}\n"
                )

                if user_guess == secret_number:
                    game_state["game_running"] = False
                    final = discord.Embed(
                        title="✅ NUMBER GUESSED! ✅",
                        description=(
                            f"🎉 CONGRATULATIONS, {guesser.mention}! "
                            f"You guessed the number **{secret_number}** in "
                            f"**{game_state['attempts']}** attempts!"
                        ),
                        color=discord.Color.green(),
                    )
                    final.set_footer(text=f"Game ended. Winner is {guesser.display_name}!")
                    await game_message.edit(embed=final)
                    try:
                        await guess_message.delete()
                    except discord.HTTPException:
                        pass
                    return

                feedback = (
                    f"My number is **higher** than {user_guess}."
                    if user_guess < secret_number
                    else f"My number is **lower** than {user_guess}."
                )
                updated = discord.Embed(
                    title="🎯 Guess the Number! 🎯",
                    description=current_desc + f"**Feedback:** {feedback}",
                    color=discord.Color.blue(),
                )
                updated.set_footer(text=f"Game started by {interaction.user.display_name}")
                await game_message.edit(embed=updated)
                try:
                    await guess_message.delete()
                except discord.HTTPException:
                    pass

            if game_state["game_running"]:
                game_state["game_running"] = False
                final = discord.Embed(
                    title="💔 ATTEMPTS EXHAUSTED! 💔",
                    description=(
                        f"You ran out of attempts! The number was **{secret_number}**. "
                        "Better luck next time!"
                    ),
                    color=discord.Color.dark_grey(),
                )
                final.set_footer(text=f"Game started by {interaction.user.display_name}")
                await game_message.edit(embed=final)
        except Exception:
            log.exception("Error in /games guess")
            game_state["game_running"] = False
            error = discord.Embed(
                title="❌ GAME ERROR ❌",
                description=(
                    f"An unexpected error occurred. The number was **{secret_number}**."
                ),
                color=discord.Color.dark_red(),
            )
            error.set_footer(text=f"Game started by {interaction.user.display_name}")
            await game_message.edit(embed=error)
        finally:
            active.pop(interaction.channel_id, None)
