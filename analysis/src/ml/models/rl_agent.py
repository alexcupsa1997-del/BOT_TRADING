"""
RL Agent — DQN Ensemble for Trading

Three DQN variants:
1. DQN (vanilla): Q-learning with target network
2. Double DQN: decoupled action selection / value estimation
3. Dueling DQN: separate value + advantage streams

Ensemble uses majority vote weighted by Q-value confidence.

All agents implement BasePredictor for consistent integration.

Ref: FUSION_PLAN Fase 3, item 3.11
"""

from __future__ import annotations

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from collections import deque
from dataclasses import dataclass
from typing import Tuple, Optional, Dict, Any, List
from loguru import logger

from src.ml.models.model_zoo.base_predictor import BasePredictor


# =============================================================================
# REPLAY BUFFER
# =============================================================================

class ReplayBuffer:
    """Circular experience replay buffer."""

    def __init__(self, capacity: int = 100_000):
        self.buffer = deque(maxlen=capacity)

    def push(self, state, action, reward, next_state, done):
        self.buffer.append((state, action, reward, next_state, done))

    def sample(self, batch_size: int):
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        batch = [self.buffer[i] for i in indices]
        states, actions, rewards, next_states, dones = zip(*batch)
        return (
            np.array(states, dtype=np.float32),
            np.array(actions, dtype=np.int64),
            np.array(rewards, dtype=np.float32),
            np.array(next_states, dtype=np.float32),
            np.array(dones, dtype=np.float32),
        )

    def __len__(self):
        return len(self.buffer)


# =============================================================================
# DQN NETWORKS
# =============================================================================

class _DQNNet(nn.Module):
    """Standard DQN network."""
    def __init__(self, state_dim: int, n_actions: int = 3, hidden: int = 256):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class _DuelingNet(nn.Module):
    """Dueling DQN: separate value + advantage streams."""
    def __init__(self, state_dim: int, n_actions: int = 3, hidden: int = 256):
        super().__init__()
        self.feature = nn.Sequential(
            nn.Linear(state_dim, hidden),
            nn.ReLU(),
        )
        self.value_stream = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, 1),
        )
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden, hidden // 2),
            nn.ReLU(),
            nn.Linear(hidden // 2, n_actions),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        feat = self.feature(x)
        value = self.value_stream(feat)
        advantage = self.advantage_stream(feat)
        # Q(s,a) = V(s) + A(s,a) - mean(A(s,:))
        return value + advantage - advantage.mean(dim=-1, keepdim=True)


# =============================================================================
# DQN AGENT
# =============================================================================

@dataclass
class DQNConfig:
    gamma: float = 0.99
    lr: float = 1e-3
    batch_size: int = 64
    buffer_size: int = 100_000
    target_update_freq: int = 1000
    epsilon_start: float = 1.0
    epsilon_end: float = 0.01
    epsilon_decay_steps: int = 100_000
    hidden_dim: int = 256
    n_actions: int = 3  # HOLD, LONG, SHORT
    seed: int = 42
    variant: str = "dqn"  # "dqn", "double", "dueling"


class DQNAgent(BasePredictor):
    """
    Deep Q-Network agent for trading.

    Supports three variants:
    - "dqn": Standard DQN
    - "double": Double DQN (reduced overestimation)
    - "dueling": Dueling DQN (value + advantage decomposition)
    """

    def __init__(self, config: DQNConfig | None = None, **kwargs):
        self.config = config or DQNConfig(**kwargs)
        self._online_net = None
        self._target_net = None
        self._optimizer = None
        self._buffer = ReplayBuffer(self.config.buffer_size)
        self._step_count = 0
        self._state_dim = None

    @property
    def name(self) -> str:
        return f"dqn_{self.config.variant}"

    @property
    def is_sequence_model(self) -> bool:
        return False

    def _build_nets(self, state_dim: int):
        """Initialize networks for given state dimension."""
        self._state_dim = state_dim
        NetClass = _DuelingNet if self.config.variant == "dueling" else _DQNNet

        self._online_net = NetClass(state_dim, self.config.n_actions, self.config.hidden_dim).to(self.device)
        self._target_net = NetClass(state_dim, self.config.n_actions, self.config.hidden_dim).to(self.device)
        self._target_net.load_state_dict(self._online_net.state_dict())
        self._target_net.eval()

        self._optimizer = torch.optim.Adam(self._online_net.parameters(), lr=self.config.lr)

    def _get_epsilon(self) -> float:
        """Linearly decay epsilon."""
        progress = min(self._step_count / max(self.config.epsilon_decay_steps, 1), 1.0)
        return self.config.epsilon_start + (self.config.epsilon_end - self.config.epsilon_start) * progress

    def select_action(self, state: np.ndarray) -> int:
        """Epsilon-greedy action selection."""
        if np.random.random() < self._get_epsilon():
            return np.random.randint(self.config.n_actions)
        state_t = torch.FloatTensor(state).unsqueeze(0).to(self.device)
        with torch.no_grad():
            q_values = self._online_net(state_t)
        return q_values.argmax(dim=-1).item()

    def _update(self):
        """Single gradient step on replay buffer batch."""
        if len(self._buffer) < self.config.batch_size:
            return 0.0

        states, actions, rewards, next_states, dones = self._buffer.sample(self.config.batch_size)

        s = torch.FloatTensor(states).to(self.device)
        a = torch.LongTensor(actions).to(self.device)
        r = torch.FloatTensor(rewards).to(self.device)
        s_next = torch.FloatTensor(next_states).to(self.device)
        d = torch.FloatTensor(dones).to(self.device)

        q_values = self._online_net(s).gather(1, a.unsqueeze(1)).squeeze(1)

        with torch.no_grad():
            if self.config.variant == "double":
                # Double DQN: select action with online, evaluate with target
                next_actions = self._online_net(s_next).argmax(dim=-1, keepdim=True)
                next_q = self._target_net(s_next).gather(1, next_actions).squeeze(1)
            else:
                next_q = self._target_net(s_next).max(dim=-1).values

        target = r + self.config.gamma * next_q * (1 - d)
        loss = F.mse_loss(q_values, target)

        self._optimizer.zero_grad()
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self._online_net.parameters(), 1.0)
        self._optimizer.step()

        # Target network sync
        self._step_count += 1
        if self._step_count % self.config.target_update_freq == 0:
            self._target_net.load_state_dict(self._online_net.state_dict())

        return loss.item()

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        """
        Train using supervised episodes from historical data.

        Each sample is treated as a transition:
        state=X[i], action=y[i], reward=sign(return), next_state=X[i+1].
        """
        torch.manual_seed(self.config.seed)
        np.random.seed(self.config.seed)

        # Flatten if sequence
        if X_train.ndim == 3:
            X_flat = X_train.reshape(X_train.shape[0], -1)
        else:
            X_flat = X_train

        state_dim = X_flat.shape[1]
        self._build_nets(state_dim)

        # Generate transitions from labeled data
        n_episodes = kwargs.get("n_episodes", 3)
        total_loss = 0.0
        n_updates = 0

        for episode in range(n_episodes):
            for i in range(len(X_flat) - 1):
                state = X_flat[i]
                action = int(y_train[i])
                # Reward: +1 for correct direction, -1 otherwise
                next_action = int(y_train[i + 1]) if i + 1 < len(y_train) else 0
                reward = 1.0 if action == next_action else -0.5
                if action == 0:
                    reward = 0.0  # HOLD is neutral
                next_state = X_flat[i + 1]
                done = (i == len(X_flat) - 2)

                self._buffer.push(state, action, reward, next_state, done)
                loss = self._update()
                if loss > 0:
                    total_loss += loss
                    n_updates += 1

        avg_loss = total_loss / max(n_updates, 1)
        logger.info(f"DQN ({self.config.variant}) trained: {n_updates} updates, avg_loss={avg_loss:.4f}")
        return {"loss": avg_loss, "steps": self._step_count}

    def predict(self, X) -> Tuple[np.ndarray, np.ndarray]:
        if X.ndim == 3:
            X_flat = X.reshape(X.shape[0], -1)
        else:
            X_flat = X

        self._online_net.eval()
        X_t = torch.FloatTensor(X_flat).to(self.device)
        with torch.no_grad():
            q_values = self._online_net(X_t)
            probs = F.softmax(q_values, dim=-1)
            preds = probs.argmax(dim=-1).cpu().numpy()
            confs = probs.max(dim=-1).values.cpu().numpy()
        return preds, confs

    def save(self, filepath: str):
        torch.save({
            "online": self._online_net.state_dict(),
            "target": self._target_net.state_dict(),
            "config": self.config,
            "state_dim": self._state_dim,
        }, filepath)

    def load(self, filepath: str):
        data = torch.load(filepath, map_location=self.device, weights_only=False)
        self.config = data["config"]
        self._build_nets(data["state_dim"])
        self._online_net.load_state_dict(data["online"])
        self._target_net.load_state_dict(data["target"])

    def get_params(self) -> Dict[str, Any]:
        return {
            "variant": self.config.variant,
            "hidden_dim": self.config.hidden_dim,
            "lr": self.config.lr,
            "gamma": self.config.gamma,
        }


# =============================================================================
# RL ENSEMBLE — 3 DQN Variants voting
# =============================================================================

class RLEnsemble(BasePredictor):
    """
    Ensemble of 3 DQN variants with majority vote.

    Agents: DQN + DoubleDQN + DuelingDQN
    Decision: Weighted majority vote. No consensus → HOLD.
    """

    def __init__(self, seed: int = 42, n_actions: int = 3, **kwargs):
        self.seed = seed
        self.n_actions = n_actions
        self.agents = [
            DQNAgent(DQNConfig(variant="dqn", seed=seed, **kwargs)),
            DQNAgent(DQNConfig(variant="double", seed=seed + 1, **kwargs)),
            DQNAgent(DQNConfig(variant="dueling", seed=seed + 2, **kwargs)),
        ]

    @property
    def name(self) -> str:
        return "rl_ensemble"

    @property
    def is_sequence_model(self) -> bool:
        return False

    def fit(self, X_train, y_train, X_val=None, y_val=None, **kwargs):
        results = {}
        for agent in self.agents:
            r = agent.fit(X_train, y_train, X_val, y_val, **kwargs)
            results[agent.name] = r
        return results

    def predict(self, X) -> Tuple[np.ndarray, np.ndarray]:
        n = X.shape[0]
        votes = np.zeros((n, self.n_actions))

        for agent in self.agents:
            preds, confs = agent.predict(X)
            for i in range(n):
                votes[i, int(preds[i])] += confs[i]

        preds = votes.argmax(axis=1)
        total = votes.sum(axis=1)
        confs = votes.max(axis=1) / np.where(total > 0, total, 1.0)

        # No consensus check: if max votes < 50% of total, default to HOLD
        for i in range(n):
            if total[i] > 0 and votes[i].max() / total[i] < 0.4:
                preds[i] = 0  # HOLD
                confs[i] = 0.3

        return preds.astype(int), confs.astype(float)

    def save(self, filepath: str):
        for i, agent in enumerate(self.agents):
            agent.save(f"{filepath}_agent{i}")

    def load(self, filepath: str):
        for i, agent in enumerate(self.agents):
            agent.load(f"{filepath}_agent{i}")

    def get_params(self) -> Dict[str, Any]:
        return {"agents": [a.name for a in self.agents]}


__all__ = ["DQNConfig", "DQNAgent", "RLEnsemble", "ReplayBuffer"]
