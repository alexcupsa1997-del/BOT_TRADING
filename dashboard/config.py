import os

# Redis Configuration
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))

# Key Names
KEY_STATUS = "goliath:status"
KEY_ORDERS = "goliath:orders"
KEY_LOGS = "goliath:logs:critical"

# Dashboard Refresh Rate (seconds)
REFRESH_RATE = 1
