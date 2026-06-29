"""
    Cogs that need the database call `pool()` to acquire connections.
"""
import logging
import aiomysql
import config

log = logging.getLogger(__name__)

_pool: aiomysql.Pool | None = None

# Tables the bot owns, idempotent.
SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS moderation_log (
        id               BIGINT       AUTO_INCREMENT PRIMARY KEY,
        guild_id         BIGINT       NOT NULL,
        user_id          BIGINT       NOT NULL,
        moderator        BIGINT       NOT NULL,
        action           VARCHAR(16)  NOT NULL,
        reason           TEXT         NOT NULL,
        duration_minutes INT          NULL,
        created_at       DATETIME(0)  NOT NULL DEFAULT CURRENT_TIMESTAMP,
        INDEX idx_guild_user (guild_id, user_id),
        INDEX idx_guild_user_action (guild_id, user_id, action)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """,
]


async def init() -> None:
    """Open the connection pool and ensure the schema exists. Idempotent."""
    global _pool
    if _pool is not None:
        return

    _pool = await aiomysql.create_pool(
        host=config.MYSQL_HOST,
        port=config.MYSQL_PORT,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        db=config.MYSQL_DATABASE,
        autocommit=True,
        minsize=1,
        maxsize=5,
        charset="utf8mb4",
    )

    async with _pool.acquire() as conn:
        async with conn.cursor() as cur:
            for statement in SCHEMA_STATEMENTS:
                await cur.execute(statement)

    log.info("MySQL pool ready (host=%s db=%s)", config.MYSQL_HOST, config.MYSQL_DATABASE)


async def close() -> None:
    """Close the pool."""
    global _pool
    if _pool is None:
        return
    _pool.close()
    await _pool.wait_closed()
    _pool = None
    log.info("MySQL pool closed.")


def pool() -> aiomysql.Pool:
    """
        Return the live pool. 
        Raises if init() was never called.
    """
    if _pool is None:
        raise RuntimeError("db.init() has not been called yet.")
    return _pool
