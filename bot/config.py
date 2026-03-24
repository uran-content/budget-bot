import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN: str = os.environ["BOT_TOKEN"]

ADMIN_IDS: set[int] = {
    int(uid.strip())
    for uid in os.environ.get("ADMIN_IDS", "").split(",")
    if uid.strip()
}

TRC20_ADDRESS: str = os.environ.get("TRC20_ADDRESS", "")

TRONGRID_API_KEY: str = os.environ.get("TRONGRID_API_KEY", "")

POLL_INTERVAL: int = int(os.environ.get("POLL_INTERVAL", "15"))

USDT_CONTRACT: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
USDT_DECIMALS: int = 6

DB_PATH: str = os.environ.get("DB_PATH", "data/budget_bot.db")
