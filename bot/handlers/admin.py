from telegram import Update
from telegram.ext import ContextTypes

from bot import database
from bot.utils import admin_only


@admin_only
async def adduser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add an allowed user: /adduser <telegram_id> <nickname>"""
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Использование: /adduser <telegram_id> <никнейм>\n"
            "Пример: /adduser 123456789 Иван"
        )
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Telegram ID должен быть числом.")
        return

    nickname = " ".join(context.args[1:])

    await database.upsert_user(
        telegram_id=telegram_id,
        nickname=nickname,
        is_allowed=True,
    )

    await update.message.reply_text(
        f"✅ Пользователь добавлен:\n"
        f"ID: {telegram_id}\n"
        f"Никнейм: {nickname}"
    )


@admin_only
async def removeuser_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove an allowed user: /removeuser <telegram_id>"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Использование: /removeuser <telegram_id>")
        return

    try:
        telegram_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ Telegram ID должен быть числом.")
        return

    removed = await database.remove_user(telegram_id)
    if removed:
        await update.message.reply_text(f"✅ Пользователь {telegram_id} удалён из списка доступа.")
    else:
        await update.message.reply_text(
            f"❌ Пользователь {telegram_id} не найден или является администратором."
        )


@admin_only
async def setaddress_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Change the monitored TRC20 address: /setaddress <address>"""
    if not context.args or len(context.args) < 1:
        await update.message.reply_text("Использование: /setaddress <TRC20_адрес>")
        return

    address = context.args[0].strip()

    if not address.startswith("T") or len(address) != 34:
        await update.message.reply_text("❌ Неверный формат TRC20 адреса. Адрес должен начинаться с T и содержать 34 символа.")
        return

    await database.set_setting("trc20_address", address)

    # Reset poll timestamp to now so we don't process old txs for the new address
    import time
    await database.set_setting("last_poll_timestamp", str(int(time.time() * 1000)))

    await update.message.reply_text(f"✅ Адрес для мониторинга изменён:\n{address}")


@admin_only
async def users_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all users: /users"""
    users = await database.get_all_users()

    if not users:
        await update.message.reply_text("Пользователи не найдены.")
        return

    lines = ["👥 Список пользователей:\n"]
    for u in users:
        role = "👑 Админ" if u["is_admin"] else "👤 Пользователь"
        status = "✅" if u["started"] else "⏳ не запустил бота"
        nickname = u.get("nickname") or "—"
        lines.append(f"{role} | ID: {u['telegram_id']} | {nickname} | {status}")

    await update.message.reply_text("\n".join(lines))
