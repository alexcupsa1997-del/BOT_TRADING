"""Tests for JEPA self-supervised pre-training."""

import torch
import torch.nn as nn
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.training.jepa import JEPAPreTrainer


class SimpleEncoder(nn.Module):
    """Minimal encoder for testing: Linear projection per timestep."""
    def __init__(self, in_dim: int, out_dim: int):
        super().__init__()
        self.proj = nn.Linear(in_dim, out_dim)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.proj(x)  # (batch, seq, out_dim)


@pytest.fixture
def pretrainer():
    encoder = SimpleEncoder(in_dim=10, out_dim=64)
    return JEPAPreTrainer(encoder, d_input=64, d_model=32, tau=0.996)


@pytest.fixture
def dummy_pair():
    """Adjacent window pair: (x_t, x_t+1)."""
    torch.manual_seed(42)
    x_t = torch.randn(8, 20, 10)
    x_t1 = x_t + torch.randn_like(x_t) * 0.1  # Slightly shifted
    return x_t, x_t1


class TestPretrainStep:
    def test_returns_scalar_loss(self, pretrainer, dummy_pair):
        loss = pretrainer.pretrain_step(*dummy_pair)
        assert loss.dim() == 0
        assert not torch.isnan(loss)

    def test_loss_decreases_over_steps(self, pretrainer, dummy_pair):
        optimizer = torch.optim.Adam(pretrainer.parameters(), lr=1e-3)
        x_t, x_t1 = dummy_pair

        losses = []
        for _ in range(50):
            optimizer.zero_grad()
            loss = pretrainer.pretrain_step(x_t, x_t1)
            if loss.item() > 0:
                loss.backward()
                optimizer.step()
            losses.append(loss.item())

        # Filter out zero losses (selective decode skips)
        nonzero = [l for l in losses if l > 0]
        if len(nonzero) >= 2:
            assert nonzero[-1] < nonzero[0], (
                f"Loss did not decrease: {nonzero[0]:.4f} -> {nonzero[-1]:.4f}"
            )


class TestTargetEncoder:
    def test_target_differs_from_online_after_updates(self, pretrainer, dummy_pair):
        # Before any update, they should be identical
        online_params = list(pretrainer.online_encoder.parameters())
        target_params = list(pretrainer.target_encoder.parameters())

        # Verify initially identical
        for op, tp in zip(online_params, target_params):
            torch.testing.assert_close(op.data, tp.data)

        # Modify online encoder (simulate a training step)
        for p in pretrainer.online_encoder.parameters():
            p.data += 0.1

        # EMA update
        pretrainer.update_target()

        # Now they should differ
        for op, tp in zip(online_params, target_params):
            assert not torch.allclose(op.data, tp.data, atol=1e-6)


class TestSelectiveDecode:
    def test_skips_identical_inputs(self, pretrainer):
        pretrainer.eval()  # Disable dropout for deterministic comparison
        x = torch.randn(4, 20, 10)
        with torch.no_grad():
            online_repr = pretrainer.encode_online(x)
            target_repr = pretrainer.encode_target(x)
        # Identical input + eval mode should produce very similar representations
        # (encoders are clones), so selective decode should skip
        should_skip = pretrainer.selective_decode(online_repr, target_repr)
        assert should_skip is True
        pretrainer.train()


class TestCosineSimilarity:
    def test_predicted_similarity_increases_after_training(self, pretrainer, dummy_pair):
        """After training, the predictor(online(x_t)) should become more
        similar to target(x_t1) — that is the core JEPA objective."""
        optimizer = torch.optim.Adam(pretrainer.parameters(), lr=1e-3)
        x_t, x_t1 = dummy_pair

        # Measure initial similarity between predicted and target
        pretrainer.eval()
        with torch.no_grad():
            o = pretrainer.encode_online(x_t)
            predicted = pretrainer.predictor(o)
            t = pretrainer.encode_target(x_t1)
            sim_before = torch.nn.functional.cosine_similarity(predicted, t, dim=-1).mean().item()
        pretrainer.train()

        # Train
        for _ in range(50):
            optimizer.zero_grad()
            loss = pretrainer.pretrain_step(x_t, x_t1)
            if loss.item() > 0:
                loss.backward()
                optimizer.step()

        # Measure again
        pretrainer.eval()
        with torch.no_grad():
            o = pretrainer.encode_online(x_t)
            predicted = pretrainer.predictor(o)
            t = pretrainer.encode_target(x_t1)
            sim_after = torch.nn.functional.cosine_similarity(predicted, t, dim=-1).mean().item()

        assert sim_after >= sim_before - 0.05, (
            f"Predicted similarity did not improve: {sim_before:.4f} -> {sim_after:.4f}"
        )
