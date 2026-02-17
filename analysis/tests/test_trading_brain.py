"""Tests for the TradingBrain 4-layer multi-expert model."""

import torch
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.models.trading_brain import (
    TradingBrain, TradingBrainConfig, TradingBrainOutput, TradingBrainLoss,
)


@pytest.fixture
def cfg():
    return TradingBrainConfig(
        n_indicators=9, d_model=64, n_experts=4,
        expert_hidden=32, expert_output=16,
        lstm_hidden=32, lstm_layers=2, attn_heads=4,
    )


@pytest.fixture
def model(cfg):
    return TradingBrain(cfg)


@pytest.fixture
def dummy_inputs(cfg):
    batch, seq = 4, 50
    price = torch.randn(batch, seq, cfg.price_features)
    indicators = torch.randn(batch, seq, cfg.n_indicators)
    vol = torch.randn(batch, seq, cfg.vol_features)
    return price, indicators, vol


class TestForwardPass:
    def test_output_shapes(self, model, cfg, dummy_inputs):
        out = model(*dummy_inputs)
        assert out.direction.shape == (4, cfg.n_classes)
        assert out.value.shape == (4, 1)
        assert out.confidence.shape == (4, 1)
        assert out.gate_weights.shape == (4, cfg.n_experts)

    def test_output_nan_free(self, model, dummy_inputs):
        out = model(*dummy_inputs)
        assert not torch.isnan(out.direction).any()
        assert not torch.isnan(out.value).any()
        assert not torch.isnan(out.confidence).any()
        assert not torch.isnan(out.gate_weights).any()

    def test_batch_size_one(self, cfg):
        model = TradingBrain(cfg)
        price = torch.randn(1, 20, cfg.price_features)
        ind = torch.randn(1, 20, cfg.n_indicators)
        vol = torch.randn(1, 20, cfg.vol_features)
        out = model(price, ind, vol)
        assert out.direction.shape == (1, cfg.n_classes)


class TestOutputProperties:
    def test_gate_weights_sum_to_one(self, model, dummy_inputs):
        out = model(*dummy_inputs)
        sums = out.gate_weights.sum(dim=-1)
        torch.testing.assert_close(sums, torch.ones(4), atol=1e-5, rtol=1e-5)

    def test_confidence_bounded_0_1(self, model, dummy_inputs):
        out = model(*dummy_inputs)
        assert (out.confidence >= 0).all()
        assert (out.confidence <= 1).all()

    def test_sparsity_loss_nonnegative(self, model, dummy_inputs):
        out = model(*dummy_inputs)
        sparsity = out.gate_weights.abs().mean()
        assert sparsity.item() >= 0


class TestGradients:
    def test_gradients_flow_all_params(self, model, dummy_inputs):
        out = model(*dummy_inputs)
        loss = out.direction.sum() + out.value.sum() + out.confidence.sum()
        loss.backward()
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"


class TestContextGating:
    def test_with_context_dim(self):
        cfg = TradingBrainConfig(
            n_indicators=9, d_model=64, n_experts=4,
            expert_hidden=32, expert_output=16,
            lstm_hidden=32, lstm_layers=2, attn_heads=4,
            context_dim=4,
        )
        model = TradingBrain(cfg)
        price = torch.randn(2, 30, cfg.price_features)
        ind = torch.randn(2, 30, cfg.n_indicators)
        vol = torch.randn(2, 30, cfg.vol_features)
        ctx = torch.randn(2, 4)
        out = model(price, ind, vol, context=ctx)
        assert out.direction.shape == (2, cfg.n_classes)
        assert not torch.isnan(out.direction).any()


class TestCompositeLoss:
    def test_returns_scalar(self, model, cfg, dummy_inputs):
        out = model(*dummy_inputs)
        loss_fn = TradingBrainLoss()
        labels = torch.randint(0, cfg.n_classes, (4,))
        returns = torch.randn(4)
        correct = torch.rand(4)
        loss = loss_fn(out, labels, returns, correct)
        assert loss.dim() == 0  # scalar
        assert not torch.isnan(loss)
