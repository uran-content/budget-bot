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

    is_admin = db_user["is_admin"]

    # --- Build the message ---

    greeting = f"Привет, {nickname} 👋"

    about = (
        "Я слежу за USDT-кошельком и мгновенно сообщаю "
        "обо всех входящих и исходящих переводах."
    )

    how_it_works_lines = [
        "💰 Пополнение — вы получите уведомление с суммой и деталями.",
        "",
        "💸 Списание — вы получите уведомление с кнопкой «Я совершил эту транзакцию».",
        "Нажмите её, опишите цель перевода — и транзакция будет закрыта.",
    ]
    how_it_works = "\n".join(how_it_works_lines)

    commands_lines = ["/help — показать эту справку"]
    if is_admin:
        commands_lines = [
            "/stats — баланс, траты и последние транзакции",
            "/users — список пользователей бота",
            "/adduser <id> <ник> — добавить пользователя",
            "/removeuser <id> — удалить пользователя",
            "/setaddress <адрес> — сменить отслеживаемый кошелёк",
            "/help — показать эту справку",
        ]
    commands = "\n".join(commands_lines)

    parts = [
        greeting,
        about,
        f"⚙️ Как это работает\n\n{how_it_works}",
    ]

    if is_admin:
        parts.append(f"🛠 Команды администратора\n\n{commands}")
    else:
        parts.append(f"📋 Команды\n\n{commands}")

    await update.message.reply_text("\n\n".join(parts))


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await start_handler(update, context)
