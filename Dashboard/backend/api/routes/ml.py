"""
ML model info endpoints.
GET /api/ml/model-info   - Model type, architecture, device
GET /api/ml/predictions  - Latest predictions from Redis
"""

from pathlib import Path
from fastapi import APIRouter

from config import settings

router = APIRouter(prefix="/api/ml", tags=["ml"])


@router.get("/model-info")
async def get_model_info():
    """Get info about loaded ML models."""
    models_dir = Path(settings.engine_root) / "models"
    model_files = []

    if models_dir.exists():
        for f in models_dir.rglob("*.pth"):
            model_files.append({
                "name": f.name,
                "path": str(f.relative_to(models_dir)),
                "size_mb": round(f.stat().st_size / (1024 * 1024), 2),
            })

    # Try to detect model architecture from checkpoint
    info = {
        "model_type": "GoliathTransformerV2",
        "architecture": {
            "d_model": 256,
            "nhead": 8,
            "num_layers": 6,
            "output_heads": ["direction (3-class)", "tp_sl (2)", "confidence (1)"],
        },
        "device": "auto-detect (CUDA/ROCm/CPU)",
        "available_models": model_files,
        "note": "ML training is performed on a separate machine. This service loads trained checkpoints only.",
    }

    return {"data": info}


@router.get("/predictions")
async def get_predictions():
    """Latest prediction results. Placeholder until engine integration."""
    return {
        "data": None,
        "note": "Connect to the live prediction script or analysis signal server for real-time predictions.",
    }
