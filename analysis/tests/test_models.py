"""Forward pass shape tests for ML models (LiT + GoliathTransformer)."""

import torch
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.ml.models.lit import LiTModel
from src.ml.models.goliath_transformer import (
    GoliathConfig, GoliathTransformer, PositionalEncoding,
)


# =============================================================================
# PositionalEncoding
# =============================================================================

class TestPositionalEncoding:
    def test_output_shape(self):
        pe = PositionalEncoding(d_model=64, max_len=100, dropout=0.0)
        x = torch.randn(10, 2, 64)  # (Seq, Batch, d_model)
        out = pe(x)
        assert out.shape == (10, 2, 64)

    def test_different_positions_get_different_encodings(self):
        pe = PositionalEncoding(d_model=64, max_len=100, dropout=0.0)
        x = torch.zeros(10, 1, 64)
        out = pe(x)
        assert not torch.allclose(out[0], out[1])

    def test_deterministic_without_dropout(self):
        pe = PositionalEncoding(d_model=64, max_len=100, dropout=0.0)
        pe.eval()
        x = torch.randn(5, 2, 64)
        out1 = pe(x)
        out2 = pe(x)
        torch.testing.assert_close(out1, out2)


# =============================================================================
# GoliathTransformer
# =============================================================================

class TestGoliathTransformer:
    @pytest.fixture
    def config(self):
        return GoliathConfig(input_dim=10, d_model=64, nhead=2, num_layers=2)

    @pytest.fixture
    def model(self, config):
        return GoliathTransformer(config)

    def test_output_shape(self, model, config):
        x = torch.randn(4, 50, config.input_dim)
        out = model(x)
        assert out.shape == (4, config.output_dim)

    def test_output_3_classes(self, model, config):
        x = torch.randn(2, 30, config.input_dim)
        out = model(x)
        assert out.shape[1] == 3  # Buy/Hold/Sell

    def test_no_nans(self, model, config):
        x = torch.randn(2, 64, config.input_dim)
        out = model(x)
        assert not torch.isnan(out).any()

    def test_with_context(self):
        cfg = GoliathConfig(input_dim=10, d_model=64, nhead=2, num_layers=2, context_dim=5)
        model = GoliathTransformer(cfg)
        x = torch.randn(2, 50, 10)
        ctx = torch.randn(2, 5)
        out = model(x, global_context=ctx)
        assert out.shape == (2, 3)

    def test_batch_size_one(self, model, config):
        x = torch.randn(1, 20, config.input_dim)
        out = model(x)
        assert out.shape == (1, config.output_dim)

    def test_gradients_flow(self, model, config):
        x = torch.randn(2, 30, config.input_dim)
        out = model(x)
        loss = out.sum()
        loss.backward()
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"


# =============================================================================
# LiT Model
# =============================================================================

class TestLiTModel:
    @pytest.fixture
    def model(self):
        return LiTModel(input_dim=10, d_model=64, nhead=4, output_dim=1)

    def test_output_shape(self, model):
        x = torch.randn(4, 50, 10)
        out = model(x)
        assert out.shape == (4, 1)

    def test_no_nans(self, model):
        x = torch.randn(2, 30, 10)
        out = model(x)
        assert not torch.isnan(out).any()

    def test_multi_class_output(self):
        model = LiTModel(input_dim=10, d_model=64, nhead=4, output_dim=3)
        x = torch.randn(2, 20, 10)
        out = model(x)
        assert out.shape == (2, 3)

    def test_gradients_flow(self, model):
        x = torch.randn(2, 30, 10)
        out = model(x)
        loss = out.sum()
        loss.backward()
        for name, param in model.named_parameters():
            if param.requires_grad:
                assert param.grad is not None, f"No gradient for {name}"
