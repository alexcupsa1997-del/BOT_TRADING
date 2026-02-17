import redis
import json
import config

class DataService:
    def __init__(self):
        self.redis_client = redis.Redis(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            db=config.REDIS_DB,
            decode_responses=False # Keep bytes for safety, decode manually
        )

    def get_system_status(self):
        """Fetch system status (CPU, RAM, Latency)"""
        try:
            raw = self.redis_client.get(config.KEY_STATUS)
            if raw:
                return json.loads(raw)
        except Exception as e:
            print(f"Error fetching status: {e}")
        return None

    def get_active_orders(self):
        """Fetch list of active orders"""
        try:
            raw = self.redis_client.get(config.KEY_ORDERS)
            if raw:
                return json.loads(raw)
        except Exception as e:
            print(f"Error fetching orders: {e}")
        return []

    def get_logs(self, limit=10):
        """Fetch recent critical logs"""
        try:
            raw_logs = self.redis_client.lrange(config.KEY_LOGS, 0, limit - 1)
            return [log.decode('utf-8') for log in raw_logs]
        except Exception as e:
            print(f"Error fetching logs: {e}")
            return []
