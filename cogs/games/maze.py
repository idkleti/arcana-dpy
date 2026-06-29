"""Reaction-driven maze game."""
import asyncio
import logging
import random
import discord
from discord import app_commands
import config

log = logging.getLogger(__name__)

def _render(maze_data: dict, player_pos: list[int]) -> str:
    grid = maze_data["grid"]
    start_pos = maze_data["start_pos"]
    end_pos = maze_data["end_pos"]

    lines = []
    for r, row in enumerate(grid):
        line = []
        for c, cell in enumerate(row):
            pos = [r, c]
            if pos == player_pos:
                line.append(config.PLAYER_CHAR)
            elif pos == start_pos:
                line.append(config.START_CHAR)
            elif pos == end_pos:
                line.append(config.END_CHAR)
            elif cell == 1:
                line.append(config.WALL_CHAR)
            else:
                line.append(config.PATH_CHAR)
        lines.append("".join(line))
    return "\n".join(lines)

def _move(grid: list[list[int]], current_pos: list[int], direction: str) -> list[int]:
    rows = len(grid)
    cols = len(grid[0])
    new_row, new_col = current_pos

    if direction == config.MOVE_UP_EMOJI:
        new_row -= 1
    elif direction == config.MOVE_DOWN_EMOJI:
        new_row += 1
    elif direction == config.MOVE_LEFT_EMOJI:
        new_col -= 1
    elif direction == config.MOVE_RIGHT_EMOJI:
        new_col += 1

    if not (0 <= new_row < rows and 0 <= new_col < cols):
        return current_pos
    if grid[new_row][new_col] == 1:
        return current_pos
    return [new_row, new_col]

def register(group: app_commands.Group, client: discord.Client) -> None:
    @group.command(name="maze", description="Start an interactive maze game (reactions to move).")
    async def maze(interaction: discord.Interaction):
        active = group.active_maze_games
        if interaction.channel_id in active:
            return await interaction.response.send_message(
                "A maze game is already active in this channel.", ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        chosen = random.choice(config.ALL_MAZES)
        game_state = {
            "grid": chosen["grid"],
            "player_pos": list(chosen["start_pos"]),
            "start_pos": chosen["start_pos"],
            "end_pos": chosen["end_pos"],
            "maze_name": chosen["name"],
            "starter_id": interaction.user.id,
            "game_running": True,
            "message": None,
        }
        active[interaction.channel_id] = game_state

        embed = discord.Embed(
            title=f"Labyrinth Game 🗺️ ({game_state['maze_name']})",
            description=_render(game_state, game_state["player_pos"]),
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Game started by {interaction.user.display_name} | Use reactions to move!"
        )

        game_message = await interaction.followup.send(embed=embed)
        game_state["message"] = game_message
        for emoji in config.MAZE_REACTION_EMOJIS:
            await game_message.add_reaction(emoji)

        final_title = "⏰ TIME'S UP! ⏰"
        final_description = "Time's up! No interaction detected."
        final_color = discord.Color.red()

        try:
            while game_state["game_running"]:
                def check_reaction(reaction, user):
                    return (
                        reaction.message.id == game_message.id
                        and user.id == game_state["starter_id"]
                        and str(reaction.emoji) in config.MAZE_REACTION_EMOJIS
                    )

                try:
                    reaction, user = await client.wait_for(
                        "reaction_add", check=check_reaction, timeout=180.0
                    )
                except asyncio.TimeoutError:
                    game_state["game_running"] = False
                    break

                try:
                    await game_message.remove_reaction(reaction.emoji, user)
                except discord.HTTPException:
                    pass

                if str(reaction.emoji) == config.STOP_GAME_EMOJI:
                    game_state["game_running"] = False
                    final_title = "🛑 Labyrinth Stopped 🛑"
                    final_description = f"The game was stopped by {user.mention}."
                    final_color = discord.Color.dark_grey()
                    break

                new_pos = _move(game_state["grid"], game_state["player_pos"], str(reaction.emoji))
                game_state["player_pos"] = new_pos

                if game_state["player_pos"] == game_state["end_pos"]:
                    game_state["game_running"] = False
                    final_title = "✅ MAZE COMPLETED! ✅"
                    final_description = (
                        f"🎉 CONGRATULATIONS, {user.mention}! You reached the end of the maze!"
                    )
                    final_color = discord.Color.green()
                    break

                updated = discord.Embed(
                    title=f"Labyrinth Game 🗺️ ({game_state['maze_name']})",
                    description=_render(game_state, game_state["player_pos"]),
                    color=discord.Color.blue(),
                )
                updated.set_footer(
                    text=f"Game started by {interaction.user.display_name} | Use reactions to move!"
                )
                await game_message.edit(embed=updated)

        except Exception:
            log.exception("Error in /games maze")
            game_state["game_running"] = False
            final_title = "❌ GAME ERROR ❌"
            final_description = "An unexpected error occurred. The game has ended."
            final_color = discord.Color.dark_red()
        finally:
            final = discord.Embed(title=final_title, description=final_description, color=final_color)
            final.set_footer(text=f"Game ended. Game started by {interaction.user.display_name}.")
            try:
                await game_message.clear_reactions()
            except discord.HTTPException:
                pass
            try:
                await game_message.edit(embed=final)
            except discord.HTTPException:
                pass
            active.pop(interaction.channel_id, None)
