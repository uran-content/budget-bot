import logging
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from bot import database
from bot.utils import format_tx_message

logger = logging.getLogger(__name__)


async def notify_all_users(bot: Bot, tx: dict) -> None:
    """Send a transaction notification to all allowed users and admins."""
    users = await database.get_notifiable_users()

    for user in users:
        user_id = user["telegram_id"]

        # Check if notification already sent
        if await database.notification_exists(tx["tx_id"], user_id):
            continue

        text = format_tx_message(tx, include_purpose=True)

        # For outgoing transactions, add the claim button
        reply_markup = None
        if tx["tx_type"] == "out" and not tx.get("completed"):
            reply_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "✋ Я совершил эту транзакцию",
                    callback_data=f"claim:{tx['tx_id']}"
                )]
            ])

        try:
            msg = await bot.send_message(
                chat_id=user_id,
                text=text,
                reply_markup=reply_markup,
            )
            await database.save_notification(
                tx_id=tx["tx_id"],
                user_id=user_id,
                chat_id=user_id,
                message_id=msg.message_id,
            )
            logger.info("Notification sent to user %s for tx %s", user_id, tx["tx_id"][:16])
        except TelegramError as e:
            logger.error("Failed to send notification to user %s: %s", user_id, e)


async def update_all_notifications(bot: Bot, tx: dict) -> None:
    """Update all notification messages for a transaction after purpose is assigned."""
    notifs = await database.get_notifications_for_tx(tx["tx_id"])

    text = format_tx_message(tx, include_purpose=True)

    for notif in notifs:
        try:
            await bot.edit_message_text(
                chat_id=notif["chat_id"],
                message_id=notif["message_id"],
                text=text,
                reply_markup=None,  # Remove inline buttons
            )
        except TelegramError as e:
            logger.warning(
                "Failed to edit notification for user %s, msg %s: %s",
                notif["user_id"],
                notif["message_id"],
                e,
            )
