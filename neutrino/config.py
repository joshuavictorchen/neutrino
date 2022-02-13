import os
from pathlib import Path

root_dir = Path(
    os.path.abspath(os.path.join(os.path.join(__file__, os.pardir), os.pardir))
)

db_path = root_dir / "database"

# cbpro websocket feed endpoint URL
stream_url = "wss://ws-feed.pro.coinbase.com"

# cbpro API URL
api_url = "https://api.pro.coinbase.com"

# cbpro API response keys
api_response_keys = {
    "accounts": "id",
    "ledger": "id",
    "transfers": "id",
    "orders": "id",
}

DIVIDER = (
    "\n -------------------------------------------------------------------------------"
)

MAX_CANDLE_REQUEST = 300
TIME_FORMAT = "%Y-%m-%d %H:%M"