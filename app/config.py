import os
from pathlib import Path

MODEL_VERSION: str = os.environ.get("TWINSENSE_MODEL_VERSION", "v1").strip().lower()

if MODEL_VERSION not in ("v1", "v2"):
    import warnings
    warnings.warn("Unknown TWINSENSE_MODEL_VERSION. Defaulting to v1.", RuntimeWarning, stacklevel=2)
    MODEL_VERSION = "v1"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

MODEL_V1_PATH = MODELS_DIR / "random_forest_risk_model.joblib"
FEATURE_COLS_V1_PATH = MODELS_DIR / "feature_columns.json"
MODEL_V2_PATH = MODELS_DIR / "random_forest_risk_model_v2.joblib"
FEATURE_COLS_V2_PATH = MODELS_DIR / "feature_columns_v2.json"


def get_active_model_path() -> Path:
    return MODEL_V2_PATH if MODEL_VERSION == "v2" else MODEL_V1_PATH


def get_active_feature_cols_path() -> Path:
    return FEATURE_COLS_V2_PATH if MODEL_VERSION == "v2" else FEATURE_COLS_V1_PATH


def is_v2_active() -> bool:
    return MODEL_VERSION == "v2"
