"""Single-player Snake driven by buttons + a 1s auto-move loop."""
import asyncio
import logging
import random
import discord
from discord import app_commands, ui
import config
from .views import SnakeGameView

log = logging.getLogger(__name__)

SCORE_TO_WIN = 10
def _generate_food(snake_coords: list[list[int]]) -> list[int] | None:
    for _ in range(100):
        candidate = [
            random.randint(0, config.SNAKE_BOARD_SIZE - 1),
            random.randint(0, config.SNAKE_BOARD_SIZE - 1),
        ]
        if candidate not in snake_coords:
            return candidate
    return None  # board full

def _render_board(snake_coords: list[list[int]], food_coord: list[int] | None) -> str:
    size = config.SNAKE_BOARD_SIZE
    board = [[config.SNAKE_EMPTY_EMOJI for _ in range(size)] for _ in range(size)]

    if food_coord:
        board[food_coord[0]][food_coord[1]] = config.SNAKE_FOOD_EMOJI
    for i, (r, c) in enumerate(snake_coords):
        if 0 <= r < size and 0 <= c < size:
            board[r][c] = config.SNAKE_HEAD_EMOJI if i == 0 else config.SNAKE_BODY_EMOJI

    return "\n".join("".join(row) for row in board)

def register(group: app_commands.Group, client: discord.Client) -> None:
    async def process_move(interaction: discord.Interaction | None):
        """Advance the game one step. Called by buttons and by the auto-tick loop."""
        if interaction is not None:
            channel_id = interaction.channel.id
        else:
            channel_id = next(
                (cid for cid, gs in group.active_snake_games.items() if gs["game_running"]),
                None,
            )
            if channel_id is None:
                return

        game_state = group.active_snake_games.get(channel_id)
        if not game_state or not game_state["game_running"]:
            return
        # adopt the queued direction (set by the most recent button press).
        game_state["direction"] = game_state["next_direction"]

        head_r, head_c = game_state["snake"][0]
        if game_state["direction"] == "up":
            head_r -= 1
        elif game_state["direction"] == "down":
            head_r += 1
        elif game_state["direction"] == "left":
            head_c -= 1
        elif game_state["direction"] == "right":
            head_c += 1
        new_head = [head_r, head_c]

        size = config.SNAKE_BOARD_SIZE
        game_over = False
        final_title = ""
        final_description = ""
        final_color = discord.Color.red()

        if not (0 <= head_r < size and 0 <= head_c < size):
            game_over = True
            final_title = "💥 GAME OVER! 💥"
            final_description = (
                f"{game_state['starter_user'].mention}, you hit a wall!\n\n"
                f"Final Score: **{game_state['score']}**"
            )
        # the tail will move out of the way unless the snake is growing this step.
        elif new_head in game_state["snake"][:-1]:
            game_over = True
            final_title = "💥 GAME OVER! 💥"
            final_description = (
                f"{game_state['starter_user'].mention}, you bit yourself!\n\n"
                f"Final Score: **{game_state['score']}**"
            )
        if game_over:
            game_state["game_running"] = False
        else:
            game_state["snake"].insert(0, new_head)
            if new_head == game_state["food"]:
                game_state["score"] += 1
                game_state["food"] = _generate_food(game_state["snake"])
                if game_state["food"] is None:
                    game_over = True
                    final_title = "🎉 SNAKE GAME ENDED! 🎉"
                    final_description = (
                        f"The board is full, {game_state['starter_user'].mention}! "
                        "You got all the apples!\n\n"
                        f"Final Score: **{game_state['score']}**"
                    )
                    final_color = discord.Color.gold()
                    game_state["game_running"] = False
                elif game_state["score"] >= SCORE_TO_WIN:
                    game_over = True
                    final_title = "🎉 SNAKE GAME WON! 🎉"
                    final_description = (
                        f"Congratulations, {game_state['starter_user'].mention}! "
                        f"You reached **{SCORE_TO_WIN} apples**!\n\n"
                        f"Final Score: **{game_state['score']}**"
                    )
                    final_color = discord.Color.gold()
                    game_state["game_running"] = False
            else:
                game_state["snake"].pop()

        embed = discord.Embed(
            title="🐍 Snake Game! 🍎",
            description=(
                f"Score: {game_state['score']}\n"
                + _render_board(game_state["snake"], game_state["food"])
            ),
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=(
                f"Game started by {game_state['starter_user'].display_name} "
                "| Use buttons to move!"
            )
        )
        new_view = SnakeGameView(game_state, process_move)
        if game_over:
            for item in new_view.children:
                if isinstance(item, ui.Button):
                    item.disabled = True
            embed.title = final_title
            embed.description = final_description
            embed.color = final_color
            embed.set_footer(
                text=f"Game ended. Game started by {game_state['starter_user'].display_name}."
            )
            group.active_snake_games.pop(channel_id, None)

        try:
            if interaction is not None:
                await interaction.followup.edit_message(
                    message_id=game_state["message"].id, embed=embed, view=new_view
                )
            else:
                await game_state["message"].edit(embed=embed, view=new_view)
        except discord.NotFound:
            log.warning("Snake message in channel %s was deleted. Ending game.", channel_id)
            game_state["game_running"] = False
            group.active_snake_games.pop(channel_id, None)
        except Exception:
            log.exception("Error updating Snake message in channel %s", channel_id)
            game_state["game_running"] = False
            group.active_snake_games.pop(channel_id, None)

    @group.command(name="snake", description="Start an interactive Snake game.")
    async def snake(interaction: discord.Interaction):
        if interaction.channel_id in group.active_snake_games:
            return await interaction.response.send_message(
                "A Snake game is already active in this channel.", ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        size = config.SNAKE_BOARD_SIZE
        initial_snake = [[size // 2, size // 2]]
        initial_food = _generate_food(initial_snake)
        game_state = {
            "starter_user": interaction.user,
            "starter_id": interaction.user.id,
            "channel_id": interaction.channel.id,
            "snake": initial_snake,
            "food": initial_food,
            "direction": "right",
            "next_direction": "right",
            "score": 0,
            "game_running": True,
            "message": None,
            "parent_cog": group,
        }
        group.active_snake_games[interaction.channel_id] = game_state

        embed = discord.Embed(
            title="🐍 Snake Game! 🍎",
            description=f"Score: 0\n" + _render_board(initial_snake, initial_food),
            color=discord.Color.blue(),
        )
        embed.set_footer(
            text=f"Game started by {interaction.user.display_name} | Use buttons to move!"
        )
        view = SnakeGameView(game_state, process_move)
        game_message = await interaction.followup.send(embed=embed, view=view)
        game_state["message"] = game_message

        try:
            while game_state["game_running"]:
                await asyncio.sleep(config.SNAKE_AUTO_MOVE_DELAY)
                if game_state["game_running"]:
                    await process_move(None)
        except asyncio.CancelledError:
            log.info("Snake game cancelled in channel %s.", interaction.channel_id)
        except Exception:
            log.exception("Unhandled error in Snake loop")
            if game_state["game_running"]:
                game_state["game_running"] = False
                error = discord.Embed(
                    title="❌ GAME ERROR ❌",
                    description="An unexpected error occurred during your Snake game.",
                    color=discord.Color.dark_red(),
                )
                error.set_footer(text=f"Game started by {interaction.user.display_name}.")
                try:
                    final_view = SnakeGameView(game_state, process_move)
                    for item in final_view.children:
                        if isinstance(item, ui.Button):
                            item.disabled = True
                    await game_state["message"].edit(embed=error, view=final_view)
                except Exception:
                    log.exception("Failed to edit Snake message with error state")
        finally:
            group.active_snake_games.pop(interaction.channel.id, None)
