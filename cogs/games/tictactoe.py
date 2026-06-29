"""Two-player Tic-Tac-Toe via Discord buttons."""
import discord
from discord import app_commands, ui
import config
from .views import TicTacToeJoinView, TicTacToeView

def _render(board: list[list[str]]) -> str:
    return "\n".join("".join(row) for row in board)

def _check_win(board: list[list[str]], player_char: str) -> bool:
    for row in board:
        if all(cell == player_char for cell in row):
            return True
    for c in range(3):
        if all(board[r][c] == player_char for r in range(3)):
            return True
    if all(board[i][i] == player_char for i in range(3)):
        return True
    if all(board[i][2 - i] == player_char for i in range(3)):
        return True
    return False

def _is_draw(board: list[list[str]]) -> bool:
    return all(cell != config.TTT_EMPTY for row in board for cell in row)


def _disable(view: ui.View) -> None:
    for item in view.children:
        if isinstance(item, ui.Button):
            item.disabled = True

def register(group: app_commands.Group, client: discord.Client) -> None:
    async def handle_move(interaction: discord.Interaction, row: int, col: int):
        game_state = group.active_tictactoe_games.get(interaction.channel_id)
        if not game_state or not game_state["game_running"]:
            return await interaction.response.send_message(
                "This Tic-Tac-Toe game is no longer active.", ephemeral=True
            )
        board = game_state["board"]
        if board[row][col] != config.TTT_EMPTY:
            return await interaction.response.send_message(
                "This spot is already taken!", ephemeral=True
            )

        current_player = game_state["current_player"]
        char = (
            game_state["player1_char"]
            if current_player.id == game_state["player1"].id
            else game_state["player2_char"]
        )
        board[row][col] = char

        view = game_state["view"]
        # Mark the played button.
        for item in view.children:
            if isinstance(item, ui.Button) and item.custom_id == f"{row}{col}":
                item.label = char
                item.disabled = True
                break
        player1 = game_state["player1"]
        player2 = game_state["player2"]

        if _check_win(board, char):
            game_state["game_running"] = False
            _disable(view)
            final = discord.Embed(
                title="🎉 TIC-TAC-TOE GAME OVER! 🎉",
                description=(
                    f"**{current_player.mention} ({char}) won the game!**\n\n"
                    + _render(board)
                ),
                color=discord.Color.green(),
            )
            final.set_footer(text=f"Game started by {player1.display_name}")
            await interaction.response.edit_message(embed=final, view=view)
            group.active_tictactoe_games.pop(interaction.channel_id, None)
            return

        if _is_draw(board):
            game_state["game_running"] = False
            _disable(view)
            final = discord.Embed(
                title="🤝 TIC-TAC-TOE GAME DRAW! 🤝",
                description="No one won. It's a draw!\n\n" + _render(board),
                color=discord.Color.orange(),
            )
            final.set_footer(text=f"Game started by {player1.display_name}")
            await interaction.response.edit_message(embed=final, view=view)
            group.active_tictactoe_games.pop(interaction.channel_id, None)
            return

        # switch turn and rebuild view so the timeout resets.
        game_state["current_player"] = player2 if current_player.id == player1.id else player1
        new_view = TicTacToeView(game_state, handle_move)
        for i in range(3):
            for j in range(3):
                button = new_view.children[i * 3 + j]
                button.label = board[i][j]
                button.disabled = board[i][j] != config.TTT_EMPTY
        game_state["view"] = new_view

        char_for_turn = (
            config.TTT_PLAYER_X
            if game_state["current_player"].id == player1.id
            else config.TTT_PLAYER_O
        )
        updated = discord.Embed(
            title="Tic-Tac-Toe ❌⭕ - Game in progress...",
            description=(
                f"{player1.mention} (❌) vs {player2.mention} (⭕)\n\n"
                f"It's {game_state['current_player'].mention}'s turn ({char_for_turn})\n\n"
                + _render(board)
            ),
            color=discord.Color.blue(),
        )
        updated.set_footer(text="Click a square to make your move!")
        await interaction.response.edit_message(embed=updated, view=new_view)

    @group.command(
        name="tictactoe", description="Start a Tic-Tac-Toe game with another player."
    )
    async def tictactoe(interaction: discord.Interaction):
        if interaction.channel_id in group.active_tictactoe_games:
            return await interaction.response.send_message(
                "There's already a Tic-Tac-Toe game in this channel.", ephemeral=True
            )
        game_state = {
            "board": [[config.TTT_EMPTY for _ in range(3)] for _ in range(3)],
            "player1": interaction.user,
            "player2": None,
            "current_player": None,
            "player1_char": config.TTT_PLAYER_X,
            "player2_char": config.TTT_PLAYER_O,
            "game_running": False,
            "message": None,
            "view": None,
            "parent_cog": group,
        }
        group.active_tictactoe_games[interaction.channel_id] = game_state

        join_embed = discord.Embed(
            title="Tic-Tac-Toe ❌⭕ - Waiting for an opponent...",
            description=(
                f"{interaction.user.mention} has started a Tic-Tac-Toe game!\n"
                "Click the **Join** button to challenge them."
            ),
            color=discord.Color.gold(),
        )
        join_embed.set_footer(text="The game will expire in 2 minutes if no one joins.")

        async def start_game(button_interaction: discord.Interaction):
            game_board_view = TicTacToeView(game_state, handle_move)
            game_state["view"] = game_board_view
            char_for_turn = config.TTT_PLAYER_X  # player 1 always starts as X
            game_embed = discord.Embed(
                title="Tic-Tac-Toe ❌⭕ - Game Started!",
                description=(
                    f"{game_state['player1'].mention} (❌) vs {game_state['player2'].mention} (⭕)\n\n"
                    f"It's {game_state['current_player'].mention}'s turn ({char_for_turn})\n\n"
                    + _render(game_state["board"])
                ),
                color=discord.Color.blue(),
            )
            game_embed.set_footer(text="Click a square to make your move!")
            await game_state["message"].edit(embed=game_embed, view=game_board_view)

        join_view = TicTacToeJoinView(game_state, start_game)
        await interaction.response.send_message(embed=join_embed, view=join_view)
        game_state["message"] = await interaction.original_response()
        await join_view.wait()
