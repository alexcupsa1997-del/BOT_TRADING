import redis
import json
import time
import random
import psutil

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

def generate_system_status():
    """Simulate system health metrics"""
    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory().percent
    
    return {
        "cpu_percent": cpu,
        "ram_percent": ram,
        "ram_mb": int(psutil.virtual_memory().used / 1024 / 1024),
        "disk_usage": psutil.disk_usage('/').percent,
        "uptime_seconds": int(time.time() - 1700000000), # Mock start time
        "pg_connections": random.randint(20, 80),
        "pg_max_connections": 100,
        "redis_latency_history": [
            [time.time() - i, random.randint(1, 15)] for i in range(20)
        ],
        "daily_pnl": random.uniform(-50, 200),
        "pnl_percent": random.uniform(-1.5, 3.0),
        "active_strategy": "LiT-Transformer-HFT",
        "open_positions": random.randint(0, 5),
        "trades_count": random.randint(10, 50)
    }

def generate_orders():
    """Simulate active orders"""
    orders = []
    for i in range(random.randint(0, 5)):
        orders.append({
            "id": f"ORD-{random.randint(1000, 9999)}",
            "symbol": "BTC/USDT",
            "side": random.choice(["BUY", "SELL"]),
            "price": random.uniform(60000, 62000),
            "status": "OPEN"
        })
    return orders

def main():
    print(f"Starting Mock Data Generator on {REDIS_HOST}:{REDIS_PORT}...")
    try:
        while True:
            # 1. System Status
            status = generate_system_status()
            r.set("goliath:status", json.dumps(status))
            
            # 2. Active Orders
            orders = generate_orders()
            r.set("goliath:orders", json.dumps(orders))
            
            # 3. Logs (Randomly add one)
            if random.random() < 0.1:
                log_msg = f"[WARN] High latency detected: {random.randint(50, 100)}ms"
                r.lpush("goliath:logs:critical", log_msg)
                r.ltrim("goliath:logs:critical", 0, 99)
                
            print(f"Updated status. CPU: {status['cpu_percent']}%")
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("Stopping generator.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
