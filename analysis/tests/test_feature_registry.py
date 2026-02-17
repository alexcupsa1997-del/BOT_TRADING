"""Tests for the FeatureRegistry singleton and validation logic."""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quant.feature_registry import FeatureRegistry, FeatureSpec


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test so tests are independent."""
    FeatureRegistry.reset_instance()
    yield
    FeatureRegistry.reset_instance()


class TestSingleton:
    def test_singleton_identity(self):
        a = FeatureRegistry.get_instance()
        b = FeatureRegistry.get_instance()
        assert a is b


class TestDefaultSchema:
    def test_expected_dim_is_29(self):
        registry = FeatureRegistry.get_instance()
        assert registry.expected_dim == 29

    def test_get_ordered_names_deterministic(self):
        registry = FeatureRegistry.get_instance()
        names1 = registry.get_ordered_names()
        names2 = registry.get_ordered_names()
        assert names1 == names2
        assert len(names1) == 29


class TestValidateParity:
    def test_passes_with_all_features(self):
        registry = FeatureRegistry.get_instance()
        all_names = registry.get_ordered_names()
        assert registry.validate_parity(all_names) is True

    def test_raises_on_missing_required(self):
        registry = FeatureRegistry.get_instance()
        all_names = registry.get_ordered_names()
        incomplete = all_names[:-1]  # drop last feature
        with pytest.raises(ValueError, match="Feature parity violation"):
            registry.validate_parity(incomplete)

    def test_extra_features_do_not_cause_error(self):
        registry = FeatureRegistry.get_instance()
        all_names = registry.get_ordered_names() + ["extra_custom_feature"]
        assert registry.validate_parity(all_names) is True


class TestValidateValues:
    def test_clamps_out_of_range(self):
        registry = FeatureRegistry.get_instance()
        result = registry.validate_values({"ind_rsi": 150.0, "ind_adx": -10.0})
        assert result["ind_rsi"] == 100.0
        assert result["ind_adx"] == 0.0

    def test_passes_through_in_range(self):
        registry = FeatureRegistry.get_instance()
        result = registry.validate_values({"ind_rsi": 55.0})
        assert result["ind_rsi"] == 55.0

    def test_passes_through_unknown_features(self):
        registry = FeatureRegistry.get_instance()
        result = registry.validate_values({"unknown_feat": 999.0})
        assert result["unknown_feat"] == 999.0


class TestCustomRegistration:
    def test_register_custom_feature_extends_schema(self):
        registry = FeatureRegistry.get_instance()
        original_dim = registry.expected_dim
        custom = FeatureSpec("custom_vix", "float32", (0, 100), "macro")
        registry.register(custom)
        assert registry.expected_dim == original_dim + 1
        assert registry.get_spec("custom_vix") is not None
