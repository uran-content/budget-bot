import asyncio
import logging
import time

from telegram.ext import Application

from bot import config, database, trongrid, notifications

logger = logging.getLogger(__name__)


async def monitor_loop(application: Application) -> None:
    """Main polling loop that checks for new USDT TRC20 transactions."""
    logger.info("Transaction monitor started")

    # Wait a bit for the bot to fully initialize
    await asyncio.sleep(3)

    while True:
        try:
            await _poll_once(application)
        except Exception as e:
            logger.error("Monitor poll error: %s", e, exc_info=True)

        await asyncio.sleep(config.POLL_INTERVAL)


async def _poll_once(application: Application) -> None:
    """Single poll iteration."""
    address = await database.get_setting("trc20_address")
    if not address:
        return

    last_ts_str = await database.get_setting("last_poll_timestamp")
    last_ts = int(last_ts_str) if last_ts_str else int(time.time() * 1000)

    # Fetch new transactions since last poll
    # Add +1 to min_timestamp to avoid re-fetching the last known tx
    txs = await trongrid.fetch_trc20_transactions(
        address=address,
        min_timestamp=last_ts + 1,
    )

    if not txs:
        return

    max_ts = last_ts

    for raw_tx in txs:
        tx_id = raw_tx.get("transaction_id")
        if not tx_id:
            continue

        from_addr = raw_tx.get("from", "")
        to_addr = raw_tx.get("to", "")
        raw_amount = int(raw_tx.get("value", "0"))
        amount = raw_amount / (10 ** config.USDT_DECIMALS)
        block_ts = raw_tx.get("block_timestamp", 0)

        # Determine type
        tx_type = "in" if to_addr.lower() == address.lower() else "out"

        # Try to insert (dedup)
        inserted = await database.insert_transaction(
            tx_id=tx_id,
            tx_type=tx_type,
            amount=amount,
            from_addr=from_addr,
            to_addr=to_addr,
            timestamp=block_ts,
        )

        if not inserted:
            # Already processed
            if block_ts > max_ts:
                max_ts = block_ts
            continue

        logger.info(
            "New %s transaction: %s USDT (tx: %s)",
            tx_type,
            amount,
            tx_id[:16],
        )

        # Fetch TRX fee in background
        fee = await trongrid.fetch_transaction_fee(tx_id)
        if fee is not None:
            await database.update_transaction_fee(tx_id, fee)

        # Re-read transaction with fee
        tx = await database.get_transaction(tx_id)
        if tx:
            await notifications.notify_all_users(application.bot, tx)

        if block_ts > max_ts:
            max_ts = block_ts

    # Update last poll timestamp
    if max_ts > last_ts:
        await database.set_setting("last_poll_timestamp", str(max_ts))
