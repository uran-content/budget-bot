import functools
from datetime import datetime, timezone, timedelta
from telegram import Update
from telegram.ext import ContextTypes

from bot import database

# Moscow timezone offset (UTC+3) — adjust if needed
_TZ = timezone(timedelta(hours=3))


def admin_only(func):
    """Decorator: only allow admins to use this handler."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        db_user = await database.get_user(user.id)
        if not db_user or not db_user["is_admin"]:
            await update.message.reply_text("⛔ Доступ запрещён. Только для администраторов.")
            return
        return await func(update, context)

    return wrapper


def allowed_only(func):
    """Decorator: only allow admins or allowed users."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if not user:
            return
        db_user = await database.get_user(user.id)
        if not db_user or (not db_user["is_admin"] and not db_user["is_allowed"]):
            await update.message.reply_text("⛔ У вас нет доступа к этому боту.")
            return
        return await func(update, context)

    return wrapper


def format_address(addr: str) -> str:
    """Shorten a TRON address for display."""
    if len(addr) > 12:
        return f"{addr[:6]}...{addr[-4:]}"
    return addr


def format_amount(amount: float) -> str:
    """Format USDT amount."""
    return f"{amount:,.2f} USDT"


def format_timestamp(ts_ms: int) -> str:
    """Format a millisecond timestamp to human-readable string."""
    dt = datetime.fromtimestamp(ts_ms / 1000, tz=_TZ)
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def format_tx_message(tx: dict, include_purpose: bool = True) -> str:
    """Format a transaction for display in a message."""
    if tx["tx_type"] == "in":
        header = f"📥 Пополнение: +{format_amount(tx['amount'])}"
    else:
        header = f"📤 Списание: -{format_amount(tx['amount'])}"

    lines = [
        header,
        f"От: {format_address(tx['from_addr'])}",
        f"Кому: {format_address(tx['to_addr'])}",
    ]

    if tx.get("trx_fee") is not None:
        lines.append(f"Комиссия: {tx['trx_fee']:.2f} TRX")

    lines.append(f"Дата: {format_timestamp(tx['timestamp'])}")
    lines.append(f"TX: {tx['tx_id'][:16]}...")

    if include_purpose and tx["tx_type"] == "out":
        if tx.get("completed") and tx.get("purpose"):
            lines.append("")
            lines.append(f"✅ Цель: {tx['purpose']}")
            lines.append(f"Назначил: {tx.get('assigned_by_nickname', 'N/A')}")
        elif not tx.get("completed"):
            lines.append("")
            lines.append("⏳ Цель не назначена")

    return "\n".join(lines)
