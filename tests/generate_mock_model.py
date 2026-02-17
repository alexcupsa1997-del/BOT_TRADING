import torch
import numpy as np
import json
import os
import sys

# Add project root
sys.path.append(os.getcwd())

from engine.models.goliath import GoliathTransformerV2, TrainingConfig

def generate_mock():
    # 1. Config
    config = TrainingConfig()
    
    # 2. Model
    model = GoliathTransformerV2(config, input_dim=8)
    
    # 3. Save Model State
    os.makedirs("tests/data", exist_ok=True)
    model_path = "tests/data/goliath_mock.pth"
    torch.save(model.state_dict(), model_path)
    print(f"Saved mock model to {model_path}")
    
    # 4. Save Scaler
    scaler_path = "tests/data/scaler_mock.json"
    dummy_scaler = {
        "mean": [0.0] * 8,
        "scale": [1.0] * 8
    }
    with open(scaler_path, 'w') as f:
        json.dump(dummy_scaler, f)
    print(f"Saved mock scaler to {scaler_path}")

if __name__ == "__main__":
    generate_mock()
