"""Tests for the COPER episodic memory bank."""

import json
import pytest
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.memory.coper import (
    COPERBank, TradeExperience, create_experience, _compute_context_hash,
)


def _make_experience(rsi=50.0, adx=25.0, decision="LONG",
                     effectiveness=0.5, days_ago=0, symbol="XAUUSD"):
    """Helper to create a test experience."""
    ts = datetime.utcnow() - timedelta(days=days_ago)
    state = {"rsi": rsi, "adx": adx, "volatility": 0.02}
    return create_experience(
        market_state=state,
        decision=decision,
        entry_price=1800.0,
        exit_price=1810.0 if decision == "LONG" else 1790.0,
        symbol=symbol,
        timeframe="H1",
        timestamp=ts,
    )


class TestStoreAndRetrieve:
    def test_store_and_retrieve(self):
        bank = COPERBank(max_size=100)
        exp = _make_experience(rsi=30.0, adx=40.0)
        bank.store(exp)
        results = bank.retrieve({"rsi": 30.0, "adx": 40.0, "volatility": 0.02}, k=1)
        assert len(results) == 1
        assert results[0].id == exp.id

    def test_retrieve_ordering_by_similarity(self):
        bank = COPERBank(max_size=100)
        # Store 3 experiences with different RSI values
        far = _make_experience(rsi=80.0, adx=10.0)
        mid = _make_experience(rsi=50.0, adx=25.0)
        close = _make_experience(rsi=32.0, adx=38.0)
        bank.store(far)
        bank.store(mid)
        bank.store(close)
        # Query something close to "close"
        results = bank.retrieve({"rsi": 30.0, "adx": 40.0, "volatility": 0.02}, k=3)
        assert results[0].id == close.id

    def test_empty_bank_returns_empty_list(self):
        bank = COPERBank()
        results = bank.retrieve({"rsi": 50.0}, k=5)
        assert results == []


class TestHashRetrieval:
    def test_hash_exact_match(self):
        bank = COPERBank()
        state = {"rsi": 45.0, "adx": 30.0, "volatility": 0.015}
        exp = create_experience(state, "LONG", 1800, 1810, "XAUUSD", "H1")
        bank.store(exp)
        results = bank.retrieve(state, k=1, strategy="hash")
        assert len(results) == 1
        assert results[0].context_hash == _compute_context_hash(state)


class TestEffectiveness:
    def test_ema_update_increases(self):
        bank = COPERBank()
        exp = _make_experience(effectiveness=0.5)
        bank.store(exp)
        bank.update_effectiveness(exp.id, outcome_score=1.0)
        updated = bank._experiences[0]
        assert updated.effectiveness == pytest.approx(0.7 * 0.5 + 0.3 * 1.0)

    def test_stale_decay_reduces_effectiveness(self):
        bank = COPERBank()
        exp = _make_experience(days_ago=120)
        exp.effectiveness = 0.8
        bank.store(exp)
        bank.apply_stale_decay()
        assert bank._experiences[0].effectiveness < 0.8


class TestMaxSize:
    def test_pruning_at_capacity(self):
        bank = COPERBank(max_size=5)
        for i in range(7):
            bank.store(_make_experience(rsi=float(i * 10)))
        assert len(bank) == 5


class TestPersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        bank = COPERBank()
        exp = _make_experience(rsi=55.0, adx=35.0)
        bank.store(exp)

        filepath = str(tmp_path / "coper_bank.json")
        bank.save(filepath)

        bank2 = COPERBank()
        bank2.load(filepath)
        assert len(bank2) == 1
        assert bank2._experiences[0].id == exp.id
        assert bank2._experiences[0].market_state == exp.market_state
