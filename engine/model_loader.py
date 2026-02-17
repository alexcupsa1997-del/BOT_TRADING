"""
engine/model_loader.py - ML Model Interface
===========================================

Handles loading of PyTorch models and performing inference.
Includes manualScaler for feature normalization.
"""

import torch
import numpy as np
import os
import json
from typing import Dict, Optional, Tuple, Any
from loguru import logger
from engine.models.goliath import GoliathTransformerV2, TrainingConfig

class StandardScaler:
    """
    Manual implementation of StandardScaler to avoid sklearn dependency in hot path
    and to allow manual setting of parameters.
    """
    def __init__(self):
        self.mean = None
        self.scale = None
        
    def fit(self, X: np.ndarray):
        self.mean = np.mean(X, axis=0)
        self.scale = np.std(X, axis=0)
        self.scale[self.scale == 0] = 1.0 # Prevent div by zero
        
    def transform(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.scale is None:
            raise ValueError("Scaler not fitted")
        return (X - self.mean) / self.scale
        
    def load(self, path: str):
        with open(path, 'r') as f:
            data = json.load(f)
            self.mean = np.array(data['mean'], dtype=np.float32)
            self.scale = np.array(data['scale'], dtype=np.float32)
            
    def save(self, path: str):
        with open(path, 'w') as f:
            json.dump({
                'mean': self.mean.tolist(),
                'scale': self.scale.tolist()
            }, f)

class ModelLoader:
    def __init__(self, model_path: str, scaler_path: Optional[str] = None, device: str = "cpu"):
        self.model_path = model_path
        self.scaler_path = scaler_path
        self.device = torch.device(device)
        self.model: Optional[GoliathTransformerV2] = None
        self.scaler = StandardScaler()
        self.config = TrainingConfig() # Defaults
        
    def load(self):
        logger.info(f"Loading model from {self.model_path}")
        
        if not os.path.exists(self.model_path):
             logger.warning(f"Model file not found: {self.model_path}. Random init for testing.")
             # We initialize anyway for testing purposes
        
        if self.scaler_path and os.path.exists(self.scaler_path):
            self.scaler.load(self.scaler_path)
            input_dim = len(self.scaler.mean)
            logger.info(f"Scaler loaded. Inferred input_dim: {input_dim}")
        else:
            logger.warning("No scaler loaded. Using default input_dim=8.")
            input_dim = 8
            # Auto-init naive scaler for testing
            self.scaler.mean = np.zeros(input_dim)
            self.scaler.scale = np.ones(input_dim)

        # Initialize Architecture
        self.model = GoliathTransformerV2(self.config, input_dim=input_dim)
        
        if os.path.exists(self.model_path):
            try:
                state_dict = torch.load(self.model_path, map_location=self.device)
                self.model.load_state_dict(state_dict)
                self.model.to(self.device)
                self.model.eval()
                logger.success("Model loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load model logic: {e}")
        
        # Load Scaler
        if self.scaler_path and os.path.exists(self.scaler_path):
            self.scaler.load(self.scaler_path)
            logger.info("Scaler loaded.")
        else:
            logger.warning("No scaler loaded. Predictions will be garbage unless raw data is normalized.")
            # Auto-init naive scaler for testing
            self.scaler.mean = np.zeros(8)
            self.scaler.scale = np.ones(8)

    def predict(self, sequence: np.ndarray) -> Dict[str, Any]:
        """
        Args:
            sequence: np.ndarray of shape (seq_len, features)
        Returns:
            Dict: {'action': int, 'confidence': float, 'tp_sl': [float, float]}
        """
        if self.model is None:
            raise ValueError("Model not loaded")
            
        # 1. Normalize
        # Sequence is (seq_len, features)
        # We process it row by row or vectorized
        norm_seq = self.scaler.transform(sequence)
        
        # 2. To Tensor (Batch=1)
        # Input shape to model: (batch, seq_len, features)
        x_tensor = torch.FloatTensor(norm_seq).unsqueeze(0).to(self.device)
        
        # 3. Inference
        with torch.no_grad():
            outputs = self.model(x_tensor)
            
        # 4. Decode
        # Direction: 0=Sell, 1=Hold, 2=Buy
        direction_logits = outputs['direction'].cpu().numpy()[0]
        action = np.argmax(direction_logits)
        
        confidence = outputs['confidence'].cpu().item()
        tp_sl_mult = outputs['tp_sl'].cpu().numpy()[0]
        
        # Remap Action to match Engine Enums or logic
        # 0: SELL, 1: HOLD, 2: BUY
        
        return {
            'action': int(action),
            'confidence': confidence,
            'tp_sl': tp_sl_mult, # [tp_mult, sl_mult]
            'logits': direction_logits
        }
