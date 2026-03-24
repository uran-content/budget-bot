from telegram import Update
from telegram.ext import ContextTypes

from bot import database, trongrid
from bot.utils import admin_only, format_tx_message, format_amount


@admin_only
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show full statistics: /stats"""
    await update.message.reply_text("⏳ Загрузка статистики...")

    address = await database.get_setting("trc20_address")
    if not address:
        await update.message.reply_text("❌ Адрес для мониторинга не установлен.")
        return

    # Fetch balance
    balance = await trongrid.fetch_usdt_balance(address)
    balance_str = format_amount(balance) if balance is not None else "Ошибка загрузки"

    # Spending stats
    all_time_spending = await database.get_spending_stats()
    month_spending = await database.get_spending_stats(days=30)

    # Recent transactions
    recent_txs = await database.get_recent_transactions(limit=10)

    lines = [
        f"📊 Статистика\n",
        f"💰 Баланс: {balance_str}",
        f"📍 Адрес: {address}\n",
        f"📉 Расходы за всё время: {format_amount(all_time_spending)}",
        f"📉 Расходы за 30 дней: {format_amount(month_spending)}",
    ]

    if recent_txs:
        lines.append(f"\n📋 Последние транзакции ({len(recent_txs)}):\n")
        for tx in recent_txs:
            lines.append(format_tx_message(tx))
            lines.append("─" * 30)
    else:
        lines.append("\nТранзакций пока нет.")

    text = "\n".join(lines)

    # Telegram message limit is 4096 chars
    if len(text) > 4096:
        # Split into chunks
        for i in range(0, len(text), 4096):
            await update.message.reply_text(text[i : i + 4096])
    else:
        await update.message.reply_text(text)
