import logging
import os
import time
import aiosqlite
from bot import config

logger = logging.getLogger(__name__)

_db_path = config.DB_PATH


async def _get_db() -> aiosqlite.Connection:
    os.makedirs(os.path.dirname(_db_path), exist_ok=True)
    db = await aiosqlite.connect(_db_path)
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    return db


async def init_db() -> None:
    db = await _get_db()
    try:
        await db.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tx_id TEXT UNIQUE NOT NULL,
                tx_type TEXT NOT NULL,
                amount REAL NOT NULL,
                from_addr TEXT NOT NULL,
                to_addr TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                trx_fee REAL,
                purpose TEXT,
                assigned_by INTEGER,
                assigned_by_nickname TEXT,
                completed INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS users (
                telegram_id INTEGER PRIMARY KEY,
                nickname TEXT,
                is_admin INTEGER DEFAULT 0,
                is_allowed INTEGER DEFAULT 0,
                started INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS notifications (
                tx_id TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                PRIMARY KEY (tx_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)

        # Migration: if old transactions table lacks 'id' column, recreate it
        cursor = await db.execute("PRAGMA table_info(transactions)")
        columns = {row[1] for row in await cursor.fetchall()}
        if "id" not in columns:
            logger.info("Migrating transactions table: adding 'id' column...")
            await db.executescript("""
                ALTER TABLE transactions RENAME TO _transactions_old;
                CREATE TABLE transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tx_id TEXT UNIQUE NOT NULL,
                    tx_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    from_addr TEXT NOT NULL,
                    to_addr TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    trx_fee REAL,
                    purpose TEXT,
                    assigned_by INTEGER,
                    assigned_by_nickname TEXT,
                    completed INTEGER DEFAULT 0
                );
                INSERT INTO transactions (tx_id, tx_type, amount, from_addr, to_addr, timestamp, trx_fee, purpose, assigned_by, assigned_by_nickname, completed)
                    SELECT tx_id, tx_type, amount, from_addr, to_addr, timestamp, trx_fee, purpose, assigned_by, assigned_by_nickname, completed
                    FROM _transactions_old;
                DROP TABLE _transactions_old;
            """)

        # Seed admins
        for admin_id in config.ADMIN_IDS:
            await db.execute(
                """INSERT INTO users (telegram_id, is_admin, is_allowed)
                   VALUES (?, 1, 1)
                   ON CONFLICT(telegram_id) DO UPDATE SET is_admin=1, is_allowed=1""",
                (admin_id,),
            )

        # Seed TRC20 address
        if config.TRC20_ADDRESS:
            await db.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES ('trc20_address', ?)",
                (config.TRC20_ADDRESS,),
            )

        # Seed last_poll_timestamp to now if not exists
        await db.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('last_poll_timestamp', ?)",
            (str(int(time.time() * 1000)),),
        )

        await db.commit()
    finally:
        await db.close()


# --- Settings ---

async def get_setting(key: str) -> str | None:
    db = await _get_db()
    try:
        cursor = await db.execute("SELECT value FROM settings WHERE key=?", (key,))
        row = await cursor.fetchone()
        return row["value"] if row else None
    finally:
        await db.close()


async def set_setting(key: str, value: str) -> None:
    db = await _get_db()
    try:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value=?",
            (key, value, value),
        )
        await db.commit()
    finally:
        await db.close()


# --- Users ---

async def upsert_user(
    telegram_id: int,
    nickname: str | None = None,
    is_admin: bool | None = None,
    is_allowed: bool | None = None,
    started: bool | None = None,
) -> None:
    db = await _get_db()
    try:
        # Get current values
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        )
        existing = await cursor.fetchone()

        if existing:
            updates = []
            params = []
            if nickname is not None:
                updates.append("nickname=?")
                params.append(nickname)
            if is_admin is not None:
                updates.append("is_admin=?")
                params.append(int(is_admin))
            if is_allowed is not None:
                updates.append("is_allowed=?")
                params.append(int(is_allowed))
            if started is not None:
                updates.append("started=?")
                params.append(int(started))
            if updates:
                params.append(telegram_id)
                await db.execute(
                    f"UPDATE users SET {', '.join(updates)} WHERE telegram_id=?",
                    params,
                )
        else:
            await db.execute(
                "INSERT INTO users (telegram_id, nickname, is_admin, is_allowed, started) VALUES (?, ?, ?, ?, ?)",
                (
                    telegram_id,
                    nickname,
                    int(is_admin) if is_admin is not None else 0,
                    int(is_allowed) if is_allowed is not None else 0,
                    int(started) if started is not None else 0,
                ),
            )
        await db.commit()
    finally:
        await db.close()


async def get_user(telegram_id: int) -> dict | None:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE telegram_id=?", (telegram_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_notifiable_users() -> list[dict]:
    """Get all users who should receive notifications (allowed or admin, and have started the bot)."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE (is_allowed=1 OR is_admin=1) AND started=1"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_all_users() -> list[dict]:
    """Get all allowed and admin users."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM users WHERE is_allowed=1 OR is_admin=1"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def remove_user(telegram_id: int) -> bool:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "UPDATE users SET is_allowed=0 WHERE telegram_id=? AND is_admin=0",
            (telegram_id,),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


# --- Transactions ---

async def insert_transaction(
    tx_id: str,
    tx_type: str,
    amount: float,
    from_addr: str,
    to_addr: str,
    timestamp: int,
    trx_fee: float | None = None,
) -> bool:
    """Insert a new transaction. Returns True if inserted, False if already exists."""
    db = await _get_db()
    try:
        try:
            await db.execute(
                """INSERT INTO transactions (tx_id, tx_type, amount, from_addr, to_addr, timestamp, trx_fee)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (tx_id, tx_type, amount, from_addr, to_addr, timestamp, trx_fee),
            )
            await db.commit()
            return True
        except aiosqlite.IntegrityError:
            return False
    finally:
        await db.close()


async def update_transaction_fee(tx_id: str, trx_fee: float) -> None:
    db = await _get_db()
    try:
        await db.execute(
            "UPDATE transactions SET trx_fee=? WHERE tx_id=?", (trx_fee, tx_id)
        )
        await db.commit()
    finally:
        await db.close()


async def get_transaction(tx_id: str) -> dict | None:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE tx_id=?", (tx_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def get_transaction_by_id(row_id: int) -> dict | None:
    """Get a transaction by its integer auto-increment id."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM transactions WHERE id=?", (row_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None
    finally:
        await db.close()


async def set_purpose(
    tx_id: str, purpose: str, assigned_by: int, assigned_by_nickname: str
) -> bool:
    """Set purpose for a transaction. Returns True if successful (was not yet completed)."""
    db = await _get_db()
    try:
        cursor = await db.execute(
            """UPDATE transactions
               SET purpose=?, assigned_by=?, assigned_by_nickname=?, completed=1
               WHERE tx_id=? AND completed=0""",
            (purpose, assigned_by, assigned_by_nickname, tx_id),
        )
        await db.commit()
        return cursor.rowcount > 0
    finally:
        await db.close()


async def get_recent_transactions(limit: int = 10) -> list[dict]:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM transactions ORDER BY timestamp DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def get_spending_stats(days: int | None = None) -> float:
    """Get total outgoing amount. If days is set, only count last N days."""
    db = await _get_db()
    try:
        if days is not None:
            min_ts = int((time.time() - days * 86400) * 1000)
            cursor = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE tx_type='out' AND timestamp >= ?",
                (min_ts,),
            )
        else:
            cursor = await db.execute(
                "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE tx_type='out'"
            )
        row = await cursor.fetchone()
        return row["total"]
    finally:
        await db.close()


# --- Notifications ---

async def save_notification(
    tx_id: str, user_id: int, chat_id: int, message_id: int
) -> None:
    db = await _get_db()
    try:
        await db.execute(
            """INSERT OR REPLACE INTO notifications (tx_id, user_id, chat_id, message_id)
               VALUES (?, ?, ?, ?)""",
            (tx_id, user_id, chat_id, message_id),
        )
        await db.commit()
    finally:
        await db.close()


async def get_notifications_for_tx(tx_id: str) -> list[dict]:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT * FROM notifications WHERE tx_id=?", (tx_id,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]
    finally:
        await db.close()


async def notification_exists(tx_id: str, user_id: int) -> bool:
    db = await _get_db()
    try:
        cursor = await db.execute(
            "SELECT 1 FROM notifications WHERE tx_id=? AND user_id=?",
            (tx_id, user_id),
        )
        return await cursor.fetchone() is not None
    finally:
        await db.close()
