"""
Model Zoo — Collection of ML models behind a uniform BasePredictor interface.

Usage:
    from src.ml.models.model_zoo import MODEL_REGISTRY, get_model
    model = get_model("bilstm", hidden_dim=128)
    model.fit(X_train, y_train)
    preds, confs = model.predict(X_test)

Ref: FUSION_PLAN Fase 3
"""

from typing import Dict, Type, Any

from .base_predictor import BasePredictor
from .bilstm import BiLSTMPredictor
from .attention_seq2seq import AttentionSeq2SeqPredictor
from .dilated_cnn import DilatedCNNPredictor
from .lstm_attention import LSTMAttentionPredictor
from .lightgbm_clf import LightGBMPredictor
from .xgboost_clf import XGBoostPredictor


MODEL_REGISTRY: Dict[str, Type[BasePredictor]] = {
    "bilstm": BiLSTMPredictor,
    "attention_seq2seq": AttentionSeq2SeqPredictor,
    "dilated_cnn": DilatedCNNPredictor,
    "lstm_attention": LSTMAttentionPredictor,
    "lightgbm": LightGBMPredictor,
    "xgboost": XGBoostPredictor,
}


def get_model(name: str, **kwargs: Any) -> BasePredictor:
    """Instantiate a model by name with optional overrides."""
    if name not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model '{name}'. Available: {list(MODEL_REGISTRY.keys())}"
        )
    return MODEL_REGISTRY[name](**kwargs)


__all__ = [
    "BasePredictor",
    "MODEL_REGISTRY",
    "get_model",
    "BiLSTMPredictor",
    "AttentionSeq2SeqPredictor",
    "DilatedCNNPredictor",
    "LSTMAttentionPredictor",
    "LightGBMPredictor",
    "XGBoostPredictor",
]
