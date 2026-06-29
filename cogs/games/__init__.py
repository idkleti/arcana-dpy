"""Games cog: defines the /games command group and wires up each game module."""
import discord
from discord import app_commands
from . import guess, maze, roll, snake, tictactoe

class Games(app_commands.Group):
    """The /games command group. 
    State for each game lives on the instance so that reloading the cog cleanly drops it."""

    def __init__(self, client: discord.Client):
        super().__init__(name="games", description="Game commands.")
        self.client = client
        self.active_guess_games: dict = {}
        self.active_maze_games: dict = {}
        self.active_tictactoe_games: dict = {}
        self.active_snake_games: dict = {}

async def setup(client: discord.Client, tree: app_commands.CommandTree):
    group = Games(client)
    # each module registers its subcommand on the group instance.
    for module in (guess, maze, tictactoe, snake, roll):
        module.register(group, client)
    tree.add_command(group)
