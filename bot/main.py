import asyncio
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

from bot import config, database, monitor
from bot.handlers.start import start_handler, help_handler
from bot.handlers.admin import (
    adduser_handler,
    removeuser_handler,
    setaddress_handler,
    users_handler,
)
from bot.handlers.stats import stats_handler
from bot.handlers.purpose import claim_handler, unclaim_handler, purpose_text_handler

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    await database.init_db()
    logger.info("Database initialized")


def main() -> None:
    app = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .build()
    )

    # Command handlers
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("stats", stats_handler))
    app.add_handler(CommandHandler("adduser", adduser_handler))
    app.add_handler(CommandHandler("removeuser", removeuser_handler))
    app.add_handler(CommandHandler("setaddress", setaddress_handler))
    app.add_handler(CommandHandler("users", users_handler))

    # Callback query handlers for purpose assignment
    app.add_handler(CallbackQueryHandler(claim_handler, pattern=r"^claim:"))
    app.add_handler(CallbackQueryHandler(unclaim_handler, pattern=r"^unclaim:"))

    # Text handler for purpose input (must be last)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, purpose_text_handler))

    logger.info("Bot starting...")

    # Run polling with a custom asyncio wrapper that also starts the monitor
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _run() -> None:
        async with app:
            await app.start()
            # Now the app is running, create_task is safe
            monitor_task = asyncio.create_task(monitor.monitor_loop(app))
            logger.info("Monitor loop started")
            await app.updater.start_polling()
            logger.info("Polling started. Bot is running.")

            # Block until stopped (Ctrl+C / SIGTERM)
            stop_event = asyncio.Event()

            import signal
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, stop_event.set)

            await stop_event.wait()

            logger.info("Shutting down...")
            monitor_task.cancel()
            await app.updater.stop()
            await app.stop()

    loop.run_until_complete(_run())


if __name__ == "__main__":
    main()
