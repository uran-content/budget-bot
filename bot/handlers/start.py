from telegram import Update
from telegram.ext import ContextTypes

from bot import database


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    db_user = await database.get_user(user.id)

    if not db_user or (not db_user["is_admin"] and not db_user["is_allowed"]):
        await update.message.reply_text(
            "⛔ У вас нет доступа к этому боту.\n"
            "Обратитесь к администратору для получения доступа."
        )
        return

    # Mark user as started and update admin nickname from Telegram display name
    nickname = db_user.get("nickname")
    if db_user["is_admin"]:
        nickname = user.first_name or user.username or str(user.id)

    await database.upsert_user(
        telegram_id=user.id,
        nickname=nickname,
        started=True,
    )

    await update.message.reply_text(
        f"👋 Добро пожаловать, {nickname}!\n\n"
        "Я буду уведомлять вас о транзакциях USDT на отслеживаемом адресе.\n\n"
        "Доступные команды:\n"
        "/stats — статистика (только для админов)\n"
        "/users — список пользователей (только для админов)\n"
        "/adduser — добавить пользователя (только для админов)\n"
        "/removeuser — удалить пользователя (только для админов)\n"
        "/setaddress — сменить адрес (только для админов)\n"
        "/help — показать это сообщение"
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_handler(update, context)
