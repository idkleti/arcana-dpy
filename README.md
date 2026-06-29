# Discord bot

A slash-command Discord bot with music playback, polls, a few mini-games, server utilities, and a small moderation toolkit. Built with discord.py 2.x. Warnings are persisted to MySQL; everything else is in-memory.

Commands are organized into groups (`/fun`, `/music`, `/poll`, `/games`, `/utils`, `/moderation`), plus a top-level `/help` that lists everything.

## Commands at a glance

| Group | Commands |
| --- | --- |
| `/fun` | `hello`, `say`, `8ball` |
| `/music` | `play`, `pause`, `resume`, `skip`, `queue`, `join`, `leave` |
| `/poll` | `yesnopoll`, `choicepoll`, `close` |
| `/games` | `guess`, `maze`, `roll`, `snake`, `tictactoe` |
| `/utils` | `ping`, `serverinfo`, `userinfo`, `avatar` |
| `/moderation` | `warn`, `showwarnings`, `delwarn`, `ban`, `kick`, `mute`, `unmute`, `history` |

Run `/help <command>` for details on any of them.

## Setup

You'll need Python 3.10 or later, ffmpeg on your PATH (the music commands shell out to it), a MySQL server, and a Discord bot token.

1. **Install dependencies.**

   ```bash
   python -m venv .venv
   source .venv/bin/activate          # Windows: .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. **Install ffmpeg** if it isn't already.

   - Windows: `winget install Gyan.FFmpeg` (restart your shell afterwards)
   - macOS: `brew install ffmpeg`
   - Linux (Debian/Ubuntu): `sudo apt install ffmpeg`

3. **Create the MySQL database.** Anything works for the user and password, as long as the bot can connect:

   ```sql
   CREATE DATABASE discord_bot CHARACTER SET utf8mb4;
   CREATE USER 'botuser'@'localhost' IDENTIFIED BY 'something';
   GRANT ALL PRIVILEGES ON discord_bot.* TO 'botuser'@'localhost';
   ```

   You only need the database to exist. The bot creates its own tables on startup.

4. **Fill in `.env`.** Copy `.env.example` to `.env` and drop in your bot token and MySQL credentials. The `.env` file is gitignored.

5. **Run it:** `python main.py`

A couple of Discord-side details to get right the first time:

- On the Developer Portal, the bot needs the **Server Members** and **Message Content** privileged intents. Enable them on the application's Bot page.
- When generating an invite URL, give it the `bot` and `applications.commands` scopes. The permissions it actually uses are Send Messages, Embed Links, Add Reactions, Connect, Speak, Manage Messages, Kick Members, Ban Members, and Moderate Members.

On startup the bot syncs its slash command tree with Discord. The first time, give the client a minute or two to surface the new commands.

## Project layout

```
main.py            # entry point: subclasses discord.Client, loads cogs in setup_hook
config.py          # static constants and .env loading (token, MySQL credentials)
db.py              # aiomysql pool, schema bootstrap, helpers
cogs/
  fun.py
  music.py         # owns its per-guild queues
  poll.py          # owns the active-polls dicts
  moderation.py    # reads and writes warnings through db.py
  utils.py         # also registers /help; loaded last so it can index the tree
  games/
    __init__.py    # the /games group itself, holds each game's runtime state
    views.py       # buttons, select menus, modals shared across games
    guess.py
    maze.py
    tictactoe.py
    snake.py
    roll.py
```

Every cog module exposes `async def setup(client, tree)`, which builds an `app_commands.Group` and attaches it to the tree. The order of the `COGS` list in `main.py` matters: `utils` is loaded last because its `setup()` walks the already-populated tree to build the `/help` index.

`/games` is composed slightly differently. There's one `Games` group that owns the dictionaries tracking active games, and each game file (`maze.py`, `snake.py`, and so on) exposes a `register(group, client)` function that attaches its subcommand to that shared group. The result is one tidy `/games <name>` namespace in Discord while each game's code stays in its own file.

Runtime state (music queues, open polls, ongoing games) lives on the cog instances rather than in module-level globals. Reloading a cog drops its state cleanly.

## Database

The bot owns one table for now:

```sql
CREATE TABLE moderation_log (
    id               BIGINT      AUTO_INCREMENT PRIMARY KEY,
    guild_id         BIGINT      NOT NULL,
    user_id          BIGINT      NOT NULL,
    moderator        BIGINT      NOT NULL,
    action           VARCHAR(16) NOT NULL,
    reason           TEXT        NOT NULL,
    duration_minutes INT         NULL,
    created_at       DATETIME(0) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_guild_user (guild_id, user_id),
    INDEX idx_guild_user_action (guild_id, user_id, action)
);
```

Every moderation command writes a row here. `action` is one of `warn`, `ban`, `kick`, `mute`, `unmute`; `duration_minutes` is only populated for mutes. Action IDs come straight from the `AUTO_INCREMENT` column, so they're global rather than per-user. `/moderation showwarnings` prints each warn's ID, and `/moderation delwarn` takes it.

`/moderation history` reads the same table without filtering and shows the full timeline for a user, plus a quick `warn / ban / kick / mute / unmute` count summary. Handy for spotting repeat offenders that have already been kicked or unmuted off the warning list.

`/moderation delwarn` only removes rows whose action is `warn` - ban/kick/mute records are factual events and stay in the log even if the underlying state is later reversed (e.g. an unmute creates a new row, it doesn't delete the mute).

If you add more tables later, drop a `CREATE TABLE IF NOT EXISTS ...` statement into `SCHEMA_STATEMENTS` in `db.py`. The bot runs every statement on startup, so the schema catches up the next time it boots.

## Caveats

- Music tracks aren't cached. Every queue entry triggers a fresh yt-dlp lookup, which makes `/music queue` feel slow on long queues.
- Polls only count reactions that are still on the message when `/poll close` runs. The Discord API doesn't expose historical reactions, so removed votes vanish from the tally.
- The maze uses message reactions rather than buttons. It's a bit dated stylistically, but it works well on mobile.
- If MySQL is unreachable at startup the bot exits rather than running in a degraded state. Run it under a supervisor (systemd, Docker, whatever you prefer) so it restarts automatically.
