import logging
import aiohttp
import base58

from bot import config

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.trongrid.io"


def _headers() -> dict:
    h = {"Accept": "application/json", "Content-Type": "application/json"}
    if config.TRONGRID_API_KEY:
        h["TRON-PRO-API-KEY"] = config.TRONGRID_API_KEY
    return h


def _tron_address_to_hex_param(address: str) -> str:
    """Convert a TRON base58check address to a 64-char hex parameter for ABI encoding."""
    decoded = base58.b58decode_check(address)
    # Drop the 0x41 network prefix byte
    addr_bytes = decoded[1:]
    return addr_bytes.hex().zfill(64)


async def fetch_trc20_transactions(
    address: str,
    min_timestamp: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch TRC20 USDT transactions for an address from TronGrid."""
    url = f"{_BASE_URL}/v1/accounts/{address}/transactions/trc20"
    params: dict = {
        "contract_address": config.USDT_CONTRACT,
        "limit": limit,
        "only_confirmed": "true",
        "order_by": "block_timestamp,asc",
    }
    if min_timestamp is not None:
        params["min_timestamp"] = min_timestamp

    all_txs = []
    try:
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.get(url, params=params, headers=_headers()) as resp:
                    if resp.status != 200:
                        logger.error("TronGrid TRC20 API error: %s", resp.status)
                        break
                    data = await resp.json()

                txs = data.get("data", [])
                all_txs.extend(txs)

                # Pagination via fingerprint
                fingerprint = data.get("meta", {}).get("fingerprint")
                if fingerprint and len(txs) == limit:
                    params["fingerprint"] = fingerprint
                else:
                    break
    except Exception as e:
        logger.error("Error fetching TRC20 transactions: %s", e)

    return all_txs


async def fetch_transaction_fee(tx_id: str) -> float | None:
    """Fetch the TRX fee for a transaction by its ID."""
    url = f"{_BASE_URL}/wallet/gettransactioninfobyid"
    payload = {"value": tx_id}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=_headers()) as resp:
                if resp.status != 200:
                    logger.error("TronGrid fee API error: %s", resp.status)
                    return None
                data = await resp.json()
                fee_sun = data.get("fee", 0)
                return fee_sun / 1_000_000  # SUN -> TRX
    except Exception as e:
        logger.error("Error fetching transaction fee: %s", e)
        return None


async def fetch_usdt_balance(address: str) -> float | None:
    """Fetch USDT balance for a TRON address using triggerConstantContract."""
    url = f"{_BASE_URL}/wallet/triggerconstantcontract"

    # balanceOf(address) function selector: 0x70a08231
    param = _tron_address_to_hex_param(address)

    payload = {
        "owner_address": address,
        "contract_address": config.USDT_CONTRACT,
        "function_selector": "balanceOf(address)",
        "parameter": param,
        "visible": True,
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, headers=_headers()) as resp:
                if resp.status != 200:
                    logger.error("TronGrid balance API error: %s", resp.status)
                    return None
                data = await resp.json()

                results = data.get("constant_result", [])
                if not results:
                    logger.error("No constant_result in balance response")
                    return None

                raw = int(results[0], 16)
                return raw / (10 ** config.USDT_DECIMALS)
    except Exception as e:
        logger.error("Error fetching USDT balance: %s", e)
        return None
