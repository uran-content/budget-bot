import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from bot import database
from bot.utils import format_tx_message
from bot import notifications

logger = logging.getLogger(__name__)


async def claim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'I made this transaction' button press."""
    query = update.callback_query
    await query.answer()

    tx_id = query.data.replace("claim:", "")
    user = query.from_user

    # Check if already completed
    tx = await database.get_transaction(tx_id)
    if not tx:
        await query.answer("❌ Транзакция не найдена.", show_alert=True)
        return

    if tx["completed"]:
        await query.answer("Цель уже назначена.", show_alert=True)
        return

    # Store awaiting state
    context.user_data["awaiting_purpose_tx_id"] = tx_id

    # Edit this user's message to ask for purpose
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Я не совершал эту транзакцию", callback_data=f"unclaim:{tx_id}")]
    ])

    text = (
        f"{format_tx_message(tx, include_purpose=False)}\n\n"
        "✏️ Опишите цель этой транзакции.\n"
        "Отправьте текстовое сообщение с описанием."
    )

    await query.edit_message_text(text=text, reply_markup=keyboard)


async def unclaim_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle 'I didn't make this transaction' button press."""
    query = update.callback_query
    await query.answer()

    tx_id = query.data.replace("unclaim:", "")

    # Clear awaiting state
    context.user_data.pop("awaiting_purpose_tx_id", None)

    # Restore original spending notification
    tx = await database.get_transaction(tx_id)
    if not tx:
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✋ Я совершил эту транзакцию", callback_data=f"claim:{tx_id}")]
    ])

    text = format_tx_message(tx, include_purpose=True)
    await query.edit_message_text(text=text, reply_markup=keyboard)


async def purpose_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle text message when user is assigning a purpose."""
    tx_id = context.user_data.get("awaiting_purpose_tx_id")
    if not tx_id:
        return  # Not in purpose assignment mode, ignore

    user = update.effective_user
    purpose_text = update.message.text.strip()

    if not purpose_text:
        await update.message.reply_text("❌ Пожалуйста, напишите описание цели транзакции.")
        return

    # Get user nickname
    db_user = await database.get_user(user.id)
    nickname = (db_user.get("nickname") if db_user else None) or user.first_name or str(user.id)

    # Try to set purpose (atomic check for completed=0)
    success = await database.set_purpose(tx_id, purpose_text, user.id, nickname)

    # Clear state
    context.user_data.pop("awaiting_purpose_tx_id", None)

    if not success:
        await update.message.reply_text("❌ Цель уже была назначена другим пользователем.")
        return

    await update.message.reply_text(f"✅ Цель транзакции записана: {purpose_text}")

    # Update all notification messages across all chats
    tx = await database.get_transaction(tx_id)
    if tx:
        await notifications.update_all_notifications(context.bot, tx)
