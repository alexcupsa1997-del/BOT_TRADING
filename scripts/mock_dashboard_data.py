import redis
import json
import time
import random
from datetime import datetime, timedelta
from decimal import Decimal
import psutil

# Configuration
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0

r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

# Persistent state across ticks
equity = Decimal("100000")
daily_pnl = Decimal("0")
trades_today = 0
trade_history: list[dict] = []

SYMBOLS = ["XAUUSD", "BTCUSD", "EURUSD", "GBPUSD"]
STRATEGIES = ["LiT-Transformer-HFT", "JEPA-Momentum", "GNN-MeanReversion"]


def generate_equity_curve() -> list[dict]:
    """Generate a 30-day equity curve."""
    points = []
    eq = Decimal("100000")
    base = datetime.utcnow() - timedelta(days=30)
    for i in range(30):
        daily_return = Decimal(str(random.uniform(-0.02, 0.03)))
        eq = eq * (1 + daily_return)
        dt = base + timedelta(days=i)
        points.append({
            "timestamp": dt.strftime("%Y-%m-%d"),
            "total_equity": str(eq.quantize(Decimal("0.01"))),
            "cash": str((eq * Decimal("0.6")).quantize(Decimal("0.01"))),
        })
    return points


def generate_positions() -> list[dict]:
    """Generate random open positions."""
    positions = []
    count = random.randint(1, 4)
    for _ in range(count):
        symbol = random.choice(SYMBOLS)
        side = random.choice(["LONG", "SHORT"])
        if symbol == "XAUUSD":
            avg = Decimal(str(random.uniform(2600, 2700)))
            current = avg + Decimal(str(random.uniform(-20, 30)))
            qty = Decimal(str(random.choice([0.1, 0.2, 0.3, 0.5, 1.0])))
        elif symbol == "BTCUSD":
            avg = Decimal(str(random.uniform(65000, 70000)))
            current = avg + Decimal(str(random.uniform(-500, 800)))
            qty = Decimal(str(random.choice([0.01, 0.02, 0.05, 0.1])))
        else:
            avg = Decimal(str(random.uniform(1.05, 1.30)))
            current = avg + Decimal(str(random.uniform(-0.005, 0.008)))
            qty = Decimal(str(random.choice([1000, 5000, 10000])))

        diff = (current - avg) * qty
        if side == "SHORT":
            diff = -diff

        positions.append({
            "symbol": symbol,
            "side": side,
            "quantity": str(qty),
            "avg_price": str(avg.quantize(Decimal("0.01"))),
            "current_price": str(current.quantize(Decimal("0.01"))),
            "unrealized_pnl": str(diff.quantize(Decimal("0.01"))),
        })
    return positions


def generate_orders() -> list[dict]:
    """Generate active orders."""
    orders = []
    for _ in range(random.randint(1, 5)):
        symbol = random.choice(SYMBOLS)
        if symbol == "XAUUSD":
            price = random.uniform(2610, 2690)
        elif symbol == "BTCUSD":
            price = random.uniform(65000, 69000)
        else:
            price = random.uniform(1.06, 1.28)

        orders.append({
            "id": f"ORD-{random.randint(1000, 9999)}",
            "symbol": symbol,
            "side": random.choice(["BUY", "SELL"]),
            "price": f"{price:.2f}",
            "status": random.choice(["OPEN", "PENDING"]),
        })
    return orders


def generate_trade_history() -> list[dict]:
    """Generate trade history entries periodically."""
    global trade_history

    if random.random() < 0.15:
        symbol = random.choice(SYMBOLS)
        side = random.choice(["BUY", "SELL"])
        if symbol == "XAUUSD":
            price = random.uniform(2620, 2680)
            qty = random.choice([0.1, 0.2, 0.5])
            pnl = round(random.uniform(-30, 50), 2)
        elif symbol == "BTCUSD":
            price = random.uniform(65500, 69500)
            qty = random.choice([0.01, 0.02, 0.05])
            pnl = round(random.uniform(-25, 40), 2)
        else:
            price = random.uniform(1.06, 1.28)
            qty = random.choice([1000, 5000])
            pnl = round(random.uniform(-10, 20), 2)

        trade = {
            "id": f"TRD-{random.randint(10000, 99999)}",
            "symbol": symbol,
            "side": side,
            "price": f"{price:.2f}",
            "quantity": str(qty),
            "pnl": f"{pnl:+.2f}",
            "time": datetime.utcnow().strftime("%H:%M"),
            "timestamp": datetime.utcnow().isoformat(),
        }
        trade_history.insert(0, trade)
        trade_history = trade_history[:20]

    return trade_history


def generate_system_status() -> dict:
    """System metrics with real psutil data."""
    global daily_pnl, trades_today

    daily_pnl += Decimal(str(random.uniform(-5, 8)))
    trades_today += 1 if random.random() < 0.3 else 0

    cpu = psutil.cpu_percent()
    ram = psutil.virtual_memory()

    return {
        "cpu_percent": cpu,
        "ram_percent": ram.percent,
        "ram_mb": int(ram.used / 1024 / 1024),
        "ram_total_mb": int(ram.total / 1024 / 1024),
        "disk_usage": psutil.disk_usage("/").percent,
        "disk_used_gb": round(psutil.disk_usage("/").used / 1024**3, 1),
        "disk_total_gb": round(psutil.disk_usage("/").total / 1024**3, 1),
        "uptime_seconds": int(time.time() - 1700000000),
        "pg_connections": random.randint(15, 60),
        "pg_max_connections": 100,
        "redis_latency_ms": round(random.uniform(0.5, 5.0), 1),
        "redis_latency_history": [
            [time.time() - i * 3, round(random.uniform(0.5, 8.0), 1)]
            for i in range(30)
        ],
        "daily_pnl": float(daily_pnl.quantize(Decimal("0.01"))),
        "pnl_percent": float((daily_pnl / Decimal("100000") * 100).quantize(Decimal("0.01"))),
        "active_strategy": random.choice(STRATEGIES),
        "open_positions": random.randint(1, 4),
        "trades_count": trades_today,
    }


def generate_trading_data(status: dict) -> dict:
    """Combine trading info for WS broadcast."""
    orders = generate_orders()
    positions = generate_positions()
    equity_curve = generate_equity_curve()

    return {
        "daily_pnl": status["daily_pnl"],
        "pnl_percent": status["pnl_percent"],
        "active_strategy": status["active_strategy"],
        "open_positions": len(positions),
        "trades_count": status["trades_count"],
        "orders": orders,
        "positions": positions,
        "equity_curve": equity_curve,
    }


def generate_logs() -> None:
    """Add variety of log messages."""
    log_types = [
        ("[INFO] Order placed: BUY 0.1 XAUUSD @ 2645.30", 0.15),
        ("[INFO] Position closed: SELL BTCUSD PnL +$12.50", 0.10),
        ("[WARN] High latency detected: {}ms".format(random.randint(50, 200)), 0.08),
        ("[ERROR] Connection timeout to gateway:8080", 0.03),
        ("[INFO] Signal generated: LONG XAUUSD confidence 0.{:02d}".format(random.randint(50, 95)), 0.12),
        ("[WARN] Margin usage at {:d}%".format(random.randint(60, 95)), 0.05),
        ("[INFO] Strategy switch: {} activated".format(random.choice(STRATEGIES)), 0.04),
        ("[DEBUG] Heartbeat OK - all services responsive", 0.20),
        ("[CRITICAL] Max drawdown threshold breached: -{}%".format(round(random.uniform(5, 15), 1)), 0.01),
        ("[INFO] Trade executed: {} {} @ market".format(random.choice(["BUY", "SELL"]), random.choice(SYMBOLS)), 0.10),
    ]

    for msg, prob in log_types:
        if random.random() < prob:
            timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
            r.lpush("goliath:logs:critical", f"{timestamp} {msg}")
            r.ltrim("goliath:logs:critical", 0, 199)


def main():
    print(f"GOLIATH Mock Data Generator v3")
    print(f"Redis: {REDIS_HOST}:{REDIS_PORT}")
    print(f"Press Ctrl+C to stop\n")

    # Seed initial data
    equity_curve = generate_equity_curve()
    r.set("goliath:equity_curve", json.dumps(equity_curve))

    # Seed initial trade history
    for _ in range(5):
        generate_trade_history()
    r.set("goliath:trade_history", json.dumps(trade_history))

    try:
        tick = 0
        while True:
            # System status (every tick)
            status = generate_system_status()
            r.set("goliath:status", json.dumps(status))

            # Trading data (every tick)
            trading = generate_trading_data(status)
            r.set("goliath:orders", json.dumps(trading["orders"]))
            r.set("goliath:positions", json.dumps(trading["positions"]))
            r.set("goliath:trading", json.dumps(trading))

            # Trade history
            history = generate_trade_history()
            r.set("goliath:trade_history", json.dumps(history))

            # Equity curve (every 10 ticks)
            if tick % 10 == 0:
                equity_curve = generate_equity_curve()
                r.set("goliath:equity_curve", json.dumps(equity_curve))

            # Logs
            generate_logs()

            if tick % 5 == 0:
                print(
                    f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
                    f"CPU: {status['cpu_percent']:.0f}% | "
                    f"PnL: ${status['daily_pnl']:.2f} | "
                    f"Positions: {trading['open_positions']} | "
                    f"Orders: {len(trading['orders'])} | "
                    f"Trades: {len(history)}"
                )

            tick += 1
            time.sleep(1)

    except KeyboardInterrupt:
        print("\nStopping generator.")
    except Exception as e:
        print(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()
