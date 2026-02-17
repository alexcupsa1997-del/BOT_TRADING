"""
COPER Experience Bank — Episodic Memory for Trade Decisions

Context-Oriented Personalized Experience Retrieval (AI_BIOPSY.md §8.2).

Stores past trade experiences with market state context and retrieves the
most relevant ones when making new decisions. Supports 4 retrieval strategies:
    1. Semantic (cosine similarity on state vectors)
    2. Hash (exact SHA256[:16] context match)
    3. Hybrid (0.6 × semantic + 0.4 × hash)
    4. Pattern (temporal: day-of-week / session matching)

Includes EMA effectiveness feedback and 90-day stale decay.
"""

import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import numpy as np


@dataclass
class TradeExperience:
    """A single stored trade experience."""
    id: str
    context_hash: str
    market_state: Dict[str, float]
    decision: str                   # "LONG" | "SHORT" | "HOLD"
    entry_price: float
    exit_price: float
    pnl: float
    effectiveness: float            # EMA-smoothed, starts at 0.5
    timestamp: str                  # ISO format string
    symbol: str
    timeframe: str


def _compute_context_hash(market_state: Dict[str, float]) -> str:
    """SHA256[:16] of sorted market state values."""
    canonical = json.dumps(market_state, sort_keys=True)
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _cosine_similarity(a: Dict[str, float], b: Dict[str, float]) -> float:
    """Cosine similarity between two market state dicts."""
    keys = sorted(set(a.keys()) | set(b.keys()))
    va = np.array([a.get(k, 0.0) for k in keys])
    vb = np.array([b.get(k, 0.0) for k in keys])
    norm_a = np.linalg.norm(va)
    norm_b = np.linalg.norm(vb)
    if norm_a < 1e-9 or norm_b < 1e-9:
        return 0.0
    return float(np.dot(va, vb) / (norm_a * norm_b))


class COPERBank:
    """Episodic memory bank for trade experiences."""

    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self._experiences: List[TradeExperience] = []
        self._hash_index: Dict[str, List[int]] = {}  # hash → list of indices

    def store(self, experience: TradeExperience):
        """Add an experience to the bank, pruning oldest if at capacity."""
        if len(self._experiences) >= self.max_size:
            # Remove oldest
            removed = self._experiences.pop(0)
            self._rebuild_hash_index()

        idx = len(self._experiences)
        self._experiences.append(experience)
        self._hash_index.setdefault(experience.context_hash, []).append(idx)

    def retrieve(self, market_state: Dict[str, float], k: int = 5,
                 strategy: str = "hybrid") -> List[TradeExperience]:
        """
        Retrieve top-k similar experiences.

        Args:
            market_state: Current market state dict.
            k: Number of experiences to return.
            strategy: "semantic", "hash", "hybrid", or "pattern".
        """
        if not self._experiences:
            return []

        if strategy == "semantic":
            return self._retrieve_semantic(market_state, k)
        elif strategy == "hash":
            return self._retrieve_hash(market_state, k)
        elif strategy == "pattern":
            return self._retrieve_pattern(market_state, k)
        else:  # hybrid
            return self._retrieve_hybrid(market_state, k)

    def update_effectiveness(self, experience_id: str, outcome_score: float):
        """EMA update: new = 0.7 × old + 0.3 × outcome."""
        for exp in self._experiences:
            if exp.id == experience_id:
                exp.effectiveness = 0.7 * exp.effectiveness + 0.3 * outcome_score
                break

    def apply_stale_decay(self, reference_time: Optional[datetime] = None):
        """Reduce effectiveness for experiences older than 90 days."""
        ref = reference_time or datetime.utcnow()
        for exp in self._experiences:
            exp_time = datetime.fromisoformat(exp.timestamp)
            days_since = (ref - exp_time).days
            if days_since > 90:
                exp.effectiveness *= math.exp(-0.01 * days_since)

    def save(self, filepath: str):
        """Serialize the bank to JSON."""
        data = [asdict(exp) for exp in self._experiences]
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, filepath: str):
        """Deserialize the bank from JSON."""
        with open(filepath, "r") as f:
            data = json.load(f)
        self._experiences = [TradeExperience(**d) for d in data]
        self._rebuild_hash_index()

    def __len__(self) -> int:
        return len(self._experiences)

    # ----- Private retrieval strategies -----

    def _retrieve_semantic(self, market_state: Dict[str, float],
                           k: int) -> List[TradeExperience]:
        scored = []
        for exp in self._experiences:
            sim = _cosine_similarity(market_state, exp.market_state)
            scored.append((sim * exp.effectiveness, exp))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:k]]

    def _retrieve_hash(self, market_state: Dict[str, float],
                       k: int) -> List[TradeExperience]:
        target_hash = _compute_context_hash(market_state)
        indices = self._hash_index.get(target_hash, [])
        results = [self._experiences[i] for i in indices if i < len(self._experiences)]
        return results[:k]

    def _retrieve_hybrid(self, market_state: Dict[str, float],
                         k: int) -> List[TradeExperience]:
        target_hash = _compute_context_hash(market_state)
        scored = []
        for exp in self._experiences:
            semantic = _cosine_similarity(market_state, exp.market_state)
            hash_match = 1.0 if exp.context_hash == target_hash else 0.0
            combined = 0.6 * semantic + 0.4 * hash_match
            scored.append((combined * exp.effectiveness, exp))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [exp for _, exp in scored[:k]]

    def _retrieve_pattern(self, market_state: Dict[str, float],
                          k: int) -> List[TradeExperience]:
        # Filter by same day-of-week if 'day_of_week' in market_state
        dow = market_state.get("day_of_week")
        if dow is not None:
            matching = [
                exp for exp in self._experiences
                if exp.market_state.get("day_of_week") == dow
            ]
        else:
            matching = list(self._experiences)
        matching.sort(key=lambda e: e.effectiveness, reverse=True)
        return matching[:k]

    def _rebuild_hash_index(self):
        self._hash_index = {}
        for i, exp in enumerate(self._experiences):
            self._hash_index.setdefault(exp.context_hash, []).append(i)


def create_experience(market_state: Dict[str, float], decision: str,
                      entry_price: float, exit_price: float,
                      symbol: str, timeframe: str,
                      timestamp: Optional[datetime] = None) -> TradeExperience:
    """Factory helper to create a TradeExperience with computed fields."""
    ts = timestamp or datetime.utcnow()
    pnl = exit_price - entry_price if decision == "LONG" else entry_price - exit_price
    return TradeExperience(
        id=str(uuid.uuid4()),
        context_hash=_compute_context_hash(market_state),
        market_state=market_state,
        decision=decision,
        entry_price=entry_price,
        exit_price=exit_price,
        pnl=pnl,
        effectiveness=0.5,
        timestamp=ts.isoformat(),
        symbol=symbol,
        timeframe=timeframe,
    )
