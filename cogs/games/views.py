"""Shared UI components (Views and Modals) for the games."""
import functools
import discord
from discord import ui
import config

# --- Snake ---
class SnakeGameView(ui.View):
    """Movement buttons for the snake. A fresh instance is created after every
    move so the user's interaction timeout resets cleanly."""

    def __init__(self, game_state: dict, on_move_callback, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.game_state = game_state
        self.on_move_callback = on_move_callback
        self._add_buttons()

    def _add_buttons(self):
        buttons = [
            (config.MOVE_LEFT_EMOJI, "left", discord.ButtonStyle.secondary),
            (config.MOVE_UP_EMOJI, "up", discord.ButtonStyle.secondary),
            (config.MOVE_DOWN_EMOJI, "down", discord.ButtonStyle.secondary),
            (config.MOVE_RIGHT_EMOJI, "right", discord.ButtonStyle.secondary),
            (config.STOP_GAME_EMOJI, "stop", discord.ButtonStyle.danger),
        ]
        for emoji, custom_id, style in buttons:
            button = ui.Button(style=style, emoji=emoji, row=0, custom_id=custom_id)
            button.callback = functools.partial(self._button_callback, custom_id)
            self.add_item(button)

    async def _button_callback(self, custom_id: str, interaction: discord.Interaction):
        if interaction.user.id != self.game_state["starter_id"]:
            return await interaction.response.send_message(
                "You are not the snake player!", ephemeral=True
            )

        await interaction.response.defer()

        if custom_id == "stop":
            self.game_state["game_running"] = False
        else:
            # reject 180° turns into yourself.
            opposites = {"up": "down", "down": "up", "left": "right", "right": "left"}
            if opposites.get(custom_id) != self.game_state["direction"]:
                self.game_state["next_direction"] = custom_id

        await self.on_move_callback(interaction)
        self.stop()  # the next move will mount a fresh view

    async def on_timeout(self):
        if not self.game_state["game_running"]:
            return
        self.game_state["game_running"] = False
        message = self.game_state.get("message")
        if not message:
            return

        embed = message.embeds[0] if message.embeds else discord.Embed()
        embed.title = "⏰ SNAKE GAME TIMED OUT! ⏰"
        embed.description = (
            f"The game ended because {self.game_state['starter_user'].mention} "
            "didn't make a move in time."
        )
        embed.color = discord.Color.red()
        embed.set_footer(text=f"Game started by {self.game_state['starter_user'].display_name}")

        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True
        try:
            await message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass

        parent = self.game_state.get("parent_cog")
        if parent and message.channel.id in parent.active_snake_games:
            del parent.active_snake_games[message.channel.id]


# --- Tic-Tac-Toe ---
class TicTacToeView(ui.View):
    """3x3 button grid. A new view is rebuilt after each move."""
    def __init__(self, game_state: dict, callback, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.game_state = game_state
        self.callback = callback
        self._build_buttons()

    def _build_buttons(self):
        for i in range(3):
            for j in range(3):
                button = ui.Button(
                    style=discord.ButtonStyle.secondary,
                    label=config.TTT_EMPTY,
                    row=i,
                    custom_id=f"{i}{j}",
                )
                button.callback = functools.partial(self._button_callback, button)
                self.add_item(button)

    async def _button_callback(self, button: ui.Button, interaction: discord.Interaction):
        if interaction.user.id != self.game_state["current_player"].id:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)
        row, col = int(button.custom_id[0]), int(button.custom_id[1])
        await self.callback(interaction, row, col)

    async def on_timeout(self):
        if not self.game_state["game_running"]:
            return
        self.game_state["game_running"] = False
        timed_out = self.game_state["current_player"]
        winner = (
            self.game_state["player2"]
            if timed_out.id == self.game_state["player1"].id
            else self.game_state["player1"]
        )

        message = self.game_state["message"]
        embed = message.embeds[0]
        embed.title = "⏰ TIC-TAC-TOE GAME TIMED OUT! ⏰"
        embed.description = (
            f"The game ended because {timed_out.mention} didn't make a move in time.\n"
            f"**{winner.mention} wins by timeout!**"
        )
        embed.color = discord.Color.red()
        embed.set_footer(text=f"Game started by {self.game_state['player1'].display_name}")

        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

        try:
            await message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
        parent = self.game_state["parent_cog"]
        parent.active_tictactoe_games.pop(message.channel.id, None)

class TicTacToeJoinView(ui.View):
    """Initial 'waiting for an opponent' view shown by /games tictactoe."""

    def __init__(self, game_state: dict, on_start):
        super().__init__(timeout=120)
        self.game_state = game_state
        self.on_start = on_start  # async callable: (interaction) -> None
        self.join_button = ui.Button(
            label="Join",
            style=discord.ButtonStyle.success,
            emoji=config.TTT_JOIN_EMOJI,
        )
        self.join_button.callback = self._join_callback
        self.add_item(self.join_button)

    async def _join_callback(self, interaction: discord.Interaction):
        if interaction.user.id == self.game_state["player1"].id:
            return await interaction.response.send_message(
                "You cannot join your own game!", ephemeral=True
            )
        if self.game_state["player2"] is not None:
            return await interaction.response.send_message(
                "Someone else has already joined this game!", ephemeral=True
            )

        self.game_state["player2"] = interaction.user
        self.game_state["game_running"] = True
        self.game_state["current_player"] = self.game_state["player1"]

        await interaction.response.defer()
        self.join_button.disabled = True
        self.stop()
        await self.on_start(interaction)

    async def on_timeout(self):
        if self.game_state["player2"] is not None:
            return
        message = self.game_state["message"]
        embed = message.embeds[0]
        embed.title = "⏰ TIC-TAC-TOE GAME TIMED OUT! ⏰"
        embed.description = (
            f"No one joined the Tic-Tac-Toe game started by "
            f"{self.game_state['player1'].mention} in time."
        )
        embed.color = discord.Color.red()
        embed.set_footer(text="Game not started.")

        for item in self.children:
            if isinstance(item, ui.Button):
                item.disabled = True

        try:
            await message.edit(embed=embed, view=self)
        except discord.HTTPException:
            pass
        parent = self.game_state["parent_cog"]
        parent.active_tictactoe_games.pop(message.channel.id, None)


# --- Dice ---
class CustomDiceModal(ui.Modal, title="Custom Dice"):
    num_faces_input = ui.TextInput(
        label="How many faces should the die have?",
        placeholder="Enter a number (e.g., 100)",
        max_length=7,
        style=discord.TextStyle.short,
        required=True,
    )

    def __init__(self, original_interaction: discord.Interaction, roll_callback):
        super().__init__(timeout=300)
        self.original_interaction = original_interaction
        self.roll_callback = roll_callback  # async (orig_inter, num_faces, interaction_to_defer)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num_faces = int(self.num_faces_input.value)
        except ValueError:
            return await interaction.response.send_message(
                "Invalid input. Please enter an integer.", ephemeral=True
            )
        if not (1 <= num_faces <= 1_000_000):
            return await interaction.response.send_message(
                "The number of faces must be between 1 and 1,000,000.", ephemeral=True
            )

        self.stop()
        await self.roll_callback(self.original_interaction, num_faces, interaction_to_defer=interaction)


class DiceRollView(ui.View):
    """Select menu shown when /games roll is called without a `faces` argument."""

    PRESETS = [4, 6, 8, 10, 12, 20, 100]
    def __init__(self, original_interaction: discord.Interaction, roll_callback):
        super().__init__(timeout=120)
        self.original_interaction = original_interaction
        self.roll_callback = roll_callback

        select = ui.Select(
            placeholder="Choose a die...",
            options=[
                discord.SelectOption(label=f"d{n}", value=str(n), emoji="🎲")
                for n in self.PRESETS
            ]
            + [discord.SelectOption(label="Custom...", value="custom", emoji="✏️")],
        )
        select.callback = self._select_callback
        self.add_item(select)
        self.select = select

    async def _select_callback(self, interaction: discord.Interaction):
        value = self.select.values[0]
        if value == "custom":
            modal = CustomDiceModal(self.original_interaction, self.roll_callback)
            await interaction.response.send_modal(modal)
            self.stop()
            return
        self.stop()
        await self.roll_callback(
            self.original_interaction, int(value), interaction_to_defer=interaction
        )

    async def on_timeout(self):
        try:
            await self.original_interaction.edit_original_response(
                content="🎲 Dice selection timed out.", view=None
            )
        except discord.HTTPException:
            pass
