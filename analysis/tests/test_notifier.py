"""Tests for Notifier multi-channel system (Fase 5)."""

import pytest

from src.integration.notifier import (
    Notifier, NotifierConfig, NotifyLevel, NotificationRecord,
)


class TestNotifierDryRun:
    def test_dry_run_logs_message(self):
        cfg = NotifierConfig(dry_run=True, enable_console=False)
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.TRADE_OPEN, "LONG XAUUSD @ 1920.50")
        assert "dry_run" in record.channels_sent
        assert record.message == "LONG XAUUSD @ 1920.50"

    def test_dry_run_does_not_send_external(self):
        cfg = NotifierConfig(
            dry_run=True,
            enable_telegram=True,
            telegram_token="fake",
            telegram_chat_id="123",
            enable_discord=True,
            discord_webhook_url="https://fake.url",
        )
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.ERROR, "test error")
        # In dry_run, should NOT attempt external sends
        assert "telegram" not in record.channels_sent
        assert "discord" not in record.channels_sent
        assert "dry_run" in record.channels_sent


class TestNotifyLevels:
    def test_all_levels_accepted(self):
        n = Notifier(NotifierConfig(dry_run=True))
        for level in NotifyLevel:
            record = n.notify(level, f"Test {level.value}")
            assert record.level == level

    def test_level_values(self):
        assert NotifyLevel.TRADE_OPEN.value == "TRADE_OPEN"
        assert NotifyLevel.TRADE_CLOSE.value == "TRADE_CLOSE"
        assert NotifyLevel.DAILY_REPORT.value == "DAILY_REPORT"
        assert NotifyLevel.ERROR.value == "ERROR"
        assert NotifyLevel.ALERT.value == "ALERT"
        assert NotifyLevel.MODEL_RETRAIN.value == "MODEL_RETRAIN"


class TestConsoleOutput:
    def test_console_mode_produces_output(self):
        cfg = NotifierConfig(enable_console=True, dry_run=False)
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.ALERT, "Circuit breaker triggered")
        assert "console" in record.channels_sent

    def test_error_level_uses_logger_error(self):
        cfg = NotifierConfig(enable_console=True)
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.ERROR, "Connection lost")
        assert "console" in record.channels_sent


class TestTelegramDisabled:
    def test_telegram_disabled_by_default(self):
        n = Notifier(NotifierConfig())
        assert not n.config.enable_telegram

    def test_telegram_no_send_without_token(self):
        cfg = NotifierConfig(enable_telegram=True)  # no token/chat_id
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.TRADE_OPEN, "test")
        assert "telegram" not in record.channels_sent


class TestDiscordDisabled:
    def test_discord_disabled_by_default(self):
        n = Notifier(NotifierConfig())
        assert not n.config.enable_discord

    def test_discord_no_send_without_webhook(self):
        cfg = NotifierConfig(enable_discord=True)  # no webhook url
        n = Notifier(cfg)
        record = n.notify(NotifyLevel.TRADE_OPEN, "test")
        assert "discord" not in record.channels_sent


class TestNotifyHistory:
    def test_history_maintains_records(self):
        n = Notifier(NotifierConfig(dry_run=True))
        n.notify(NotifyLevel.TRADE_OPEN, "msg1")
        n.notify(NotifyLevel.TRADE_CLOSE, "msg2")
        n.notify(NotifyLevel.ERROR, "msg3")
        assert len(n.history) == 3
        assert n.history[0].message == "msg1"
        assert n.history[2].message == "msg3"

    def test_history_circular_buffer(self):
        cfg = NotifierConfig(dry_run=True, history_size=3)
        n = Notifier(cfg)
        for i in range(5):
            n.notify(NotifyLevel.ALERT, f"msg{i}")
        assert len(n.history) == 3
        assert n.history[0].message == "msg2"  # oldest kept
        assert n.history[2].message == "msg4"  # newest

    def test_clear_history(self):
        n = Notifier(NotifierConfig(dry_run=True))
        n.notify(NotifyLevel.ALERT, "test")
        assert len(n.history) == 1
        n.clear_history()
        assert len(n.history) == 0


class TestConvenienceMethods:
    def test_trade_opened(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.trade_opened("LONG", "XAUUSD", 1920.50, sl=1915.0, tp=1935.0)
        assert "LONG" in record.message
        assert "XAUUSD" in record.message
        assert "1920.50" in record.message
        assert record.data["direction"] == "LONG"

    def test_trade_closed(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.trade_closed("LONG", "XAUUSD", 1932.00, pnl=115.0)
        assert "CLOSED" in record.message
        assert "+$115.00" in record.message

    def test_trade_closed_negative(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.trade_closed("SHORT", "EURUSD", 1.0850, pnl=-50.0)
        assert "$-50.00" in record.message

    def test_daily_report(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.daily_report(pnl=342.0, win_rate=0.65, n_trades=8)
        assert "342.00" in record.message
        assert "65%" in record.message
        assert record.data["n_trades"] == 8

    def test_error_method(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.error("Exchange connection lost")
        assert record.level == NotifyLevel.ERROR

    def test_alert_method(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.alert("Circuit breaker triggered")
        assert record.level == NotifyLevel.ALERT

    def test_model_retrained(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.model_retrained("TradingBrain", {"sharpe": 1.85})
        assert "TradingBrain" in record.message
        assert "1.8500" in record.message
        assert record.data["model_name"] == "TradingBrain"


class TestNotifierConfig:
    def test_defaults(self):
        cfg = NotifierConfig()
        assert cfg.enable_console is True
        assert cfg.enable_telegram is False
        assert cfg.enable_discord is False
        assert cfg.dry_run is False
        assert cfg.history_size == 100

    def test_notification_record_has_timestamp(self):
        n = Notifier(NotifierConfig(dry_run=True))
        record = n.notify(NotifyLevel.ALERT, "test")
        assert record.timestamp  # non-empty ISO string
        assert "T" in record.timestamp  # ISO format
