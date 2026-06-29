"""
    Static configuration: secrets loaded from .env, plus immutable constants (emojis, embed text, yt-dlp options, maze layouts, ...).

    Mutable runtime state (music queues, active polls, active games) is owned by the cogs themselves.
"""
import os
import sys

import yt_dlp
from dotenv import load_dotenv

# --- Secrets ---
load_dotenv()

def _require(name: str) -> str:
    value = os.getenv(name)
    if not value:
        sys.exit(
            f"Error: {name} not found in environment.\n"
            "Copy .env.example to .env and fill it in."
        )
    return value


TOKEN = _require("DISCORD_TOKEN")

# --- MySQL ---
MYSQL_HOST = os.getenv("MYSQL_HOST", "localhost")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = _require("MYSQL_USER")
# MYSQL_PASSWORD may be empty in dev setups, so we don't use _require.
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
MYSQL_DATABASE = _require("MYSQL_DATABASE")

# --- Music (cogs/music.py) ---
YT_DL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "no_color": True,
}

YTDL = yt_dlp.YoutubeDL(YT_DL_OPTIONS)

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

# --- Polls (cogs/poll.py) ---
# The bot currently surfaces up to 5 options, but we support 10 as well if needed (change in cogs/poll.py).
OPTION_EMOJIS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]

# --- Fun (cogs/fun.py) ---
GREETINGS = [
    "Hello there!!",
    "Hey hey!",
    "What's up?",
    "Howdy",
    "Wassup g",
    "HEYYYY!!",
]

ANSWERS = [
    "It is certain.",
    "It is decidedly so.",
    "Without a doubt.",
    "Yes, absolutely.",
    "You may rely on it.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Yes.",
    "Signs point to yes.",
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful.",
    "No.",
]

# --- Help (cogs/utils.py) ---
CATEGORY_EMOJIS = {
    "Fun Commands": "😂",
    "Music Commands": "🎵",
    "Poll Commands": "🗳️",
    "Game Commands": "🎮",
    "Utils Commands": "🔧",
    "Moderation Commands": "🚔",
    "Uncategorized Commands": "❓",
}

# Display-name lists for the /help overview.
COMMAND_CATEGORIES = {
    "Fun Commands": [
        {"name": "fun hello"},
        {"name": "fun say"},
        {"name": "fun 8ball"},
    ],
    "Music Commands": [
        {"name": "music play"},
        {"name": "music pause"},
        {"name": "music resume"},
        {"name": "music queue"},
        {"name": "music skip"},
        {"name": "music join"},
        {"name": "music leave"},
    ],
    "Poll Commands": [
        {"name": "poll yesnopoll"},
        {"name": "poll choicepoll"},
        {"name": "poll close"},
    ],
    "Game Commands": [
        {"name": "games maze"},
        {"name": "games guess"},
        {"name": "games roll"},
        {"name": "games snake"},
        {"name": "games tictactoe"},
    ],
    "Utils Commands": [
        {"name": "utils avatar"},
        {"name": "utils ping"},
        {"name": "utils serverinfo"},
        {"name": "utils userinfo"},
    ],
    "Moderation Commands": [
        {"name": "moderation ban"},
        {"name": "moderation kick"},
        {"name": "moderation mute"},
        {"name": "moderation unmute"},
        {"name": "moderation warn"},
        {"name": "moderation delwarn"},
        {"name": "moderation showwarnings"},
        {"name": "moderation history"},
    ],
    "Uncategorized Commands": [
        {"name": "help"},
    ],
}

# --- Games: shared movement emojis ---
MOVE_UP_EMOJI = "⬆️"
MOVE_DOWN_EMOJI = "⬇️"
MOVE_LEFT_EMOJI = "⬅️"
MOVE_RIGHT_EMOJI = "➡️"
STOP_GAME_EMOJI = "🛑"

MAZE_REACTION_EMOJIS = [
    MOVE_UP_EMOJI,
    MOVE_DOWN_EMOJI,
    MOVE_LEFT_EMOJI,
    MOVE_RIGHT_EMOJI,
    STOP_GAME_EMOJI,
]

SNAKE_MOVE_EMOJIS = [
    MOVE_UP_EMOJI,
    MOVE_DOWN_EMOJI,
    MOVE_LEFT_EMOJI,
    MOVE_RIGHT_EMOJI,
]

# --- Games: maze ---
PLAYER_CHAR = "🟥"
PATH_CHAR = "⬜"
WALL_CHAR = "⬛"
START_CHAR = "🟢"
END_CHAR = "🏁"

ALL_MAZES = [
    {
        "name": "Standard Maze (5x5)",
        "grid": [
            [0, 0, 1, 0, 0],
            [1, 0, 1, 0, 1],
            [1, 0, 0, 0, 1],
            [1, 1, 1, 0, 0],
            [0, 0, 0, 0, 0],
        ],
        "start_pos": [0, 0],
        "end_pos": [4, 4],
    },
    {
        "name": "Corridor Maze (5x5)",
        "grid": [
            [0, 1, 0, 0, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 1, 0, 1, 0],
            [0, 0, 0, 1, 0],
        ],
        "start_pos": [0, 0],
        "end_pos": [4, 4],
    },
    {
        "name": "Zigzag Maze (6x6)",
        "grid": [
            [0, 0, 1, 0, 0, 0],
            [1, 0, 1, 0, 1, 0],
            [0, 0, 0, 0, 1, 0],
            [0, 1, 0, 1, 0, 0],
            [0, 1, 0, 1, 0, 1],
            [0, 0, 0, 0, 0, 0],
        ],
        "start_pos": [0, 0],
        "end_pos": [5, 5],
    },
    {
        "name": "Wall-heavy Maze (6x6)",
        "grid": [
            [0, 1, 0, 1, 0, 0],
            [0, 1, 0, 1, 1, 0],
            [0, 0, 0, 0, 0, 0],
            [1, 1, 0, 1, 1, 0],
            [0, 1, 0, 0, 0, 0],
            [0, 1, 1, 1, 1, 0],
        ],
        "start_pos": [0, 0],
        "end_pos": [5, 5],
    },
]

# --- Games: tic-tac-toe ---
TTT_EMPTY = "⬜"
TTT_PLAYER_X = "❌"
TTT_PLAYER_O = "⭕"
TTT_JOIN_EMOJI = "➡️"

# --- Games: snake ---
SNAKE_BOARD_SIZE = 12
SNAKE_HEAD_EMOJI = "🟢"
SNAKE_BODY_EMOJI = "🟩"
SNAKE_FOOD_EMOJI = "🍎"
SNAKE_EMPTY_EMOJI = "⬜"

# Seconds between auto-moves. 
# Faster than this and Discord rate-limits message edits.
SNAKE_AUTO_MOVE_DELAY = 1.0
