"""
Notifier — Multi-channel notification system.

Sends alerts on trade events, errors, daily reports, and model retraining
across multiple channels (Console, Telegram, Discord).

Ref: FUSION_PLAN Fase 5, item 5.2
"""

from __future__ import annotations

import os
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from loguru import logger


class NotifyLevel(Enum):
    """Notification severity / category."""
    TRADE_OPEN = "TRADE_OPEN"
    TRADE_CLOSE = "TRADE_CLOSE"
    DAILY_REPORT = "DAILY_REPORT"
    ERROR = "ERROR"
    ALERT = "ALERT"
    MODEL_RETRAIN = "MODEL_RETRAIN"


# Emoji prefixes for console formatting (loguru)
_LEVEL_PREFIX = {
    NotifyLevel.TRADE_OPEN: "[OPEN]",
    NotifyLevel.TRADE_CLOSE: "[CLOSE]",
    NotifyLevel.DAILY_REPORT: "[REPORT]",
    NotifyLevel.ERROR: "[ERROR]",
    NotifyLevel.ALERT: "[ALERT]",
    NotifyLevel.MODEL_RETRAIN: "[RETRAIN]",
}


@dataclass
class NotifierConfig:
    """Configuration for the Notifier."""
    # Telegram
    telegram_token: str = ""
    telegram_chat_id: str = ""
    enable_telegram: bool = False

    # Discord
    discord_webhook_url: str = ""
    enable_discord: bool = False

    # Console (always available)
    enable_console: bool = True

    # Dry-run mode — logs messages without sending
    dry_run: bool = False

    # History buffer size
    history_size: int = 100

    @classmethod
    def from_env(cls) -> NotifierConfig:
        """Create config from environment variables."""
        return cls(
            telegram_token=os.environ.get("TELEGRAM_BOT_TOKEN", ""),
            telegram_chat_id=os.environ.get("TELEGRAM_CHAT_ID", ""),
            enable_telegram=bool(os.environ.get("ENABLE_TELEGRAM", "")),
            discord_webhook_url=os.environ.get("DISCORD_WEBHOOK_URL", ""),
            enable_discord=bool(os.environ.get("ENABLE_DISCORD", "")),
            enable_console=True,
            dry_run=bool(os.environ.get("NOTIFIER_DRY_RUN", "")),
        )


@dataclass
class NotificationRecord:
    """A record of a sent notification."""
    timestamp: str
    level: NotifyLevel
    message: str
    data: Dict[str, Any]
    channels_sent: List[str]


class Notifier:
    """
    Multi-channel notification system.

    Sends messages to configured channels (Console, Telegram, Discord).
    In dry_run mode, messages are logged but not actually sent to external
    services — useful for testing.

    Usage:
        notifier = Notifier(NotifierConfig(enable_console=True))
        notifier.notify(NotifyLevel.TRADE_OPEN,
                        "LONG XAUUSD @ 1920.50 | SL: 1915 | TP: 1935")
    """

    def __init__(self, config: Optional[NotifierConfig] = None):
        self.config = config or NotifierConfig()
        self._history: deque[NotificationRecord] = deque(
            maxlen=self.config.history_size
        )

    def notify(self, level: NotifyLevel, message: str,
               data: Optional[Dict[str, Any]] = None) -> NotificationRecord:
        """
        Send a notification to all enabled channels.

        Args:
            level: Notification category (TRADE_OPEN, ERROR, etc.).
            message: Human-readable message text.
            data: Optional structured data to attach.

        Returns:
            NotificationRecord with channels that were notified.
        """
        data = data or {}
        channels_sent: List[str] = []
        prefix = _LEVEL_PREFIX.get(level, "[INFO]")
        formatted = f"{prefix} {message}"

        if self.config.dry_run:
            logger.debug(f"[DRY_RUN] {formatted}")
            channels_sent.append("dry_run")
        else:
            # Console — always first (fast, no network)
            if self.config.enable_console:
                self._send_console(level, formatted)
                channels_sent.append("console")

            # Telegram
            if self.config.enable_telegram:
                success = self._send_telegram(formatted)
                if success:
                    channels_sent.append("telegram")

            # Discord
            if self.config.enable_discord:
                success = self._send_discord(formatted)
                if success:
                    channels_sent.append("discord")

        record = NotificationRecord(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level,
            message=message,
            data=data,
            channels_sent=channels_sent,
        )
        self._history.append(record)
        return record

    @property
    def history(self) -> List[NotificationRecord]:
        """Return notification history (most recent last)."""
        return list(self._history)

    def clear_history(self) -> None:
        """Clear the notification history buffer."""
        self._history.clear()

    # ------------------------------------------------------------------
    # Channel implementations
    # ------------------------------------------------------------------

    def _send_console(self, level: NotifyLevel, formatted: str) -> None:
        """Send to console via loguru."""
        if level == NotifyLevel.ERROR:
            logger.error(formatted)
        elif level == NotifyLevel.ALERT:
            logger.warning(formatted)
        else:
            logger.info(formatted)

    def _send_telegram(self, text: str) -> bool:
        """Send message via Telegram Bot API."""
        token = self.config.telegram_token
        chat_id = self.config.telegram_chat_id

        if not token or not chat_id:
            logger.warning("Telegram not configured (missing token/chat_id)")
            return False

        try:
            import requests

            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
            }
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                return True
            else:
                logger.warning(f"Telegram API returned {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def _send_discord(self, text: str) -> bool:
        """Send message via Discord webhook."""
        webhook_url = self.config.discord_webhook_url

        if not webhook_url:
            logger.warning("Discord not configured (missing webhook_url)")
            return False

        try:
            import requests

            payload = {"content": text}
            resp = requests.post(webhook_url, json=payload, timeout=10)
            if resp.status_code in (200, 204):
                return True
            else:
                logger.warning(f"Discord webhook returned {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Discord send failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Convenience methods
    # ------------------------------------------------------------------

    def trade_opened(self, direction: str, symbol: str, price: float,
                     sl: Optional[float] = None,
                     tp: Optional[float] = None) -> NotificationRecord:
        """Shortcut for TRADE_OPEN notification."""
        parts = [f"{direction} {symbol} @ {price:.2f}"]
        if sl is not None:
            parts.append(f"SL: {sl:.2f}")
        if tp is not None:
            parts.append(f"TP: {tp:.2f}")
        msg = " | ".join(parts)
        return self.notify(NotifyLevel.TRADE_OPEN, msg, {
            "direction": direction, "symbol": symbol,
            "price": price, "sl": sl, "tp": tp,
        })

    def trade_closed(self, direction: str, symbol: str, price: float,
                     pnl: float) -> NotificationRecord:
        """Shortcut for TRADE_CLOSE notification."""
        sign = "+" if pnl >= 0 else ""
        msg = f"CLOSED {direction} {symbol} @ {price:.2f} | PnL: {sign}${pnl:.2f}"
        return self.notify(NotifyLevel.TRADE_CLOSE, msg, {
            "direction": direction, "symbol": symbol,
            "price": price, "pnl": pnl,
        })

    def daily_report(self, pnl: float, win_rate: float,
                     n_trades: int) -> NotificationRecord:
        """Shortcut for DAILY_REPORT notification."""
        sign = "+" if pnl >= 0 else ""
        msg = (f"Day P&L: {sign}${pnl:.2f} | "
               f"Win Rate: {win_rate:.0%} | Trades: {n_trades}")
        return self.notify(NotifyLevel.DAILY_REPORT, msg, {
            "pnl": pnl, "win_rate": win_rate, "n_trades": n_trades,
        })

    def error(self, message: str) -> NotificationRecord:
        """Shortcut for ERROR notification."""
        return self.notify(NotifyLevel.ERROR, message)

    def alert(self, message: str) -> NotificationRecord:
        """Shortcut for ALERT notification."""
        return self.notify(NotifyLevel.ALERT, message)

    def model_retrained(self, model_name: str,
                        metrics: Optional[Dict[str, float]] = None
                        ) -> NotificationRecord:
        """Shortcut for MODEL_RETRAIN notification."""
        metrics = metrics or {}
        parts = [f"Model retrained: {model_name}"]
        for k, v in metrics.items():
            parts.append(f"{k}: {v:.4f}")
        msg = " | ".join(parts)
        return self.notify(NotifyLevel.MODEL_RETRAIN, msg, {
            "model_name": model_name, **metrics,
        })
