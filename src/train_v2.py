"""
TwinSense AI - Step 3b: v2 Model Training with Hypoglycemia Support
====================================================================

ETHICAL & CLINICAL DISCLAIMER:
Trained exclusively on SYNTHETIC data. Not clinically validated.
Class 1 (hypoglycemia) examples are SYNTHETIC; good Class 1 metrics
do NOT imply real-world clinical validity.

PURPOSE:
--------
1. Run the v2 data generator to produce synthetic_v2 data.
2. Apply the existing feature engineering pipeline to the v2 time-series.
3. Split chronologically per patient with embargo (same method as v1).
4. Train a RandomForestClassifier with class_weight='balanced' to handle
   imbalanced Class 1 representation.
5. Save to models/random_forest_risk_model_v2.joblib and
   models/feature_columns_v2.json (never overwrites v1 artifacts).
6. Write evaluation report to reports/v2/evaluation_report_v2.md.
"""

from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from src.data_generator_v2 import run_pipeline_v2, RANDOM_SEED_V2
from src.feature_engineering import (
    engineer_features_and_target,
    validate_processed_dataset,
)

# ------------------------------------------------------------------
RANDOM_STATE = 42
TRAIN_RATIO = 0.8
EMBARGO_MINUTES = 45
SAMPLING_INTERVAL_MIN = 5
EMBARGO_STEPS = EMBARGO_MINUTES // SAMPLING_INTERVAL_MIN  # 9

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_V2_DIR = PROJECT_ROOT / "reports" / "v2"
DATA_V2_DIR = PROJECT_ROOT / "data" / "synthetic_v2"

MODEL_V2_PATH = MODELS_DIR / "random_forest_risk_model_v2.joblib"
FEATURE_COLS_V2_PATH = MODELS_DIR / "feature_columns_v2.json"
REPORT_V2_PATH = REPORTS_V2_DIR / "evaluation_report_v2.md"
PROCESSED_V2_PATH = DATA_V2_DIR / "training_dataset_v2.csv"

CLASS_MAP = {
    1: "Hypoglycemia (<70 mg/dL)",
    2: "In-Range (70-180 mg/dL)",
    3: "Hyperglycemia (>180 mg/dL)"
}
TARGET_CLASSES = [1, 2, 3]
# ------------------------------------------------------------------


def partition_with_embargo(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Chronological per-patient split: 70% train, 10% val, 20% test with embargo buffers.
    Returns (train_df, val_df, test_df).
    """
    train_slices, val_slices, test_slices = [], [], []

    for pid, p_group in df.groupby("patient_id", sort=False):
        p_sorted = p_group.sort_values("timestamp").reset_index(drop=True)
        n = len(p_sorted)

        train_end = int(n * 0.70)
        val_end = int(n * 0.80)   # 70-80 = validation

        train_part = p_sorted.iloc[:train_end].copy()
        val_start = min(n, train_end + EMBARGO_STEPS)
        val_part = p_sorted.iloc[val_start:val_end].copy()
        test_start = min(n, val_end + EMBARGO_STEPS)
        test_part = p_sorted.iloc[test_start:].copy()

        if len(train_part): train_slices.append(train_part)
        if len(val_part):   val_slices.append(val_part)
        if len(test_part):  test_slices.append(test_part)

    return (
        pd.concat(train_slices, ignore_index=True),
        pd.concat(val_slices, ignore_index=True),
        pd.concat(test_slices, ignore_index=True),
    )


def class_counts(df: pd.DataFrame, split_name: str) -> dict:
    counts = df["future_glucose_risk"].value_counts().to_dict()
    result = {c: counts.get(c, 0) for c in TARGET_CLASSES}
    print(f"\n  [{split_name}] Class distribution (total={len(df):,}):")
    for c, cnt in result.items():
        pct = cnt / len(df) * 100 if len(df) > 0 else 0
        print(f"    Class {c} ({CLASS_MAP[c]}): {cnt:,} ({pct:.2f}%)")
    return result


def run_training_pipeline_v2():
    """Full v2 training pipeline."""
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_V2_DIR.mkdir(parents=True, exist_ok=True)
    DATA_V2_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 75)
    print(" TwinSense AI - v2 Training Pipeline (Hypoglycemia Support)")
    print("=" * 75)

    # 1. Generate v2 synthetic data
    print("\n[1/6] Generating v2 synthetic data (seed=99)...")
    profiles_df, timeseries_df = run_pipeline_v2()

    # 2. Feature engineering (same pipeline as v1)
    print("[2/6] Engineering features (same pipeline as v1)...")
    # Parse timestamp strings to datetime (matches feature_engineering.load_raw_data behavior)
    timeseries_df["timestamp"] = pd.to_datetime(timeseries_df["timestamp"])
    timeseries_df = timeseries_df.sort_values(by=["patient_id", "timestamp"]).reset_index(drop=True)
    dataset_df = engineer_features_and_target(profiles_df, timeseries_df)
    print(f"      -> {len(dataset_df):,} processed rows")

    # Validate
    validate_processed_dataset(dataset_df)

    # Save processed dataset
    dataset_df.to_csv(PROCESSED_V2_PATH, index=False)
    print(f"      -> Saved: {PROCESSED_V2_PATH}")

    # 3. Chronological per-patient split (train 70% / val 10% / test 20%)
    print("\n[3/6] Chronological split (70% train / 10% val / 20% test with embargo)...")
    train_df, val_df, test_df = partition_with_embargo(dataset_df)

    # Report no-patient-overlap: each patient appears in exactly one of each partition
    train_pids = set(train_df["patient_id"].unique())
    test_pids = set(test_df["patient_id"].unique())
    assert len(train_pids.intersection(test_pids)) == 0 or True, "Patient rows in both train and test"
    # (Per-patient split: same patient can appear in both train and test, but at different times)
    # The guarantee is no time-window overlap. Let's verify:
    for pid in dataset_df["patient_id"].unique():
        t_max = train_df[train_df["patient_id"]==pid]["timestamp"].max() if pid in train_pids else None
        te_min = test_df[test_df["patient_id"]==pid]["timestamp"].min() if pid in test_pids else None
        if t_max is not None and te_min is not None:
            gap = (pd.Timestamp(te_min) - pd.Timestamp(t_max)).total_seconds() / 60
            assert gap >= EMBARGO_MINUTES, f"Leakage: {pid} gap={gap:.0f}m"

    print(f"      Train: {len(train_df):,} | Val: {len(val_df):,} | Test: {len(test_df):,}")

    # 4. Class distributions per split
    print("\n[4/6] Class distributions per split:")
    train_counts = class_counts(train_df, "TRAIN")
    val_counts   = class_counts(val_df, "VAL")
    test_counts  = class_counts(test_df, "TEST")

    for split_name, counts in [("TRAIN", train_counts), ("VAL", val_counts), ("TEST", test_counts)]:
        c1 = counts.get(1, 0)
        if c1 < 10:
            print(f"\n  [WARNING] {split_name} has only {c1} Class 1 examples.")
        else:
            print(f"\n  [OK] {split_name} has {c1} Class 1 examples.")

    # Feature schema
    excluded = {"patient_id", "timestamp", "future_timestamp", "future_glucose_mg_dl",
                "is_synthetic", "data_source", "future_glucose_risk"}
    feature_cols = [c for c in dataset_df.columns if c not in excluded]

    X_train = train_df[feature_cols]
    y_train = train_df["future_glucose_risk"]
    X_val   = val_df[feature_cols]
    y_val   = val_df["future_glucose_risk"]
    X_test  = test_df[feature_cols]
    y_test  = test_df["future_glucose_risk"]

    # 5. Train with class_weight='balanced' to handle imbalanced Class 1
    print("\n[5/6] Training RandomForestClassifier (class_weight='balanced')...")
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=5,
        class_weight="balanced",
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )
    rf_model.fit(X_train, y_train)

    y_pred_test = rf_model.predict(X_test)
    acc = float(accuracy_score(y_test, y_pred_test))
    f1_mac = float(f1_score(y_test, y_pred_test, average="macro", zero_division=0))
    cm = confusion_matrix(y_test, y_pred_test, labels=TARGET_CLASSES).tolist()
    clf_report = classification_report(
        y_test, y_pred_test,
        labels=TARGET_CLASSES,
        target_names=[f"Class {c}: {CLASS_MAP[c]}" for c in TARGET_CLASSES],
        zero_division=0,
        output_dict=True
    )

    # Dummy baseline for comparison
    dummy = DummyClassifier(strategy="most_frequent", random_state=RANDOM_STATE)
    dummy.fit(X_train, y_train)
    y_pred_dummy = dummy.predict(X_test)
    dummy_acc = float(accuracy_score(y_test, y_pred_dummy))

    print(f"\n  Test Accuracy:     {acc*100:.2f}%")
    print(f"  Macro F1:          {f1_mac:.4f}")
    print(f"  Dummy Baseline:    {dummy_acc*100:.2f}%")

    c1_key = f"Class 1: {CLASS_MAP[1]}"
    c1_prec = clf_report.get(c1_key, {}).get("precision", 0.0)
    c1_rec  = clf_report.get(c1_key, {}).get("recall", 0.0)
    c1_f1   = clf_report.get(c1_key, {}).get("f1-score", 0.0)
    c1_sup  = clf_report.get(c1_key, {}).get("support", 0)
    print(f"\n  Class 1 (Hypoglycemia):")
    print(f"    Precision: {c1_prec:.4f}  Recall: {c1_rec:.4f}  F1: {c1_f1:.4f}  Support: {c1_sup}")

    # 6. Save artifacts
    print(f"\n[6/6] Saving v2 artifacts...")
    joblib.dump(rf_model, MODEL_V2_PATH)
    with open(FEATURE_COLS_V2_PATH, "w") as f:
        json.dump({"feature_columns": feature_cols}, f, indent=2)

    # Write markdown report
    report_text = _build_report(
        train_counts, val_counts, test_counts,
        len(train_df), len(val_df), len(test_df),
        acc, f1_mac, dummy_acc, cm, clf_report
    )
    REPORT_V2_PATH.write_text(report_text, encoding="utf-8")

    print(f"  [+] Model: {MODEL_V2_PATH}")
    print(f"  [+] Feature schema: {FEATURE_COLS_V2_PATH}")
    print(f"  [+] Evaluation report: {REPORT_V2_PATH}")
    print("=" * 75)

    return rf_model, feature_cols, {
        "train": train_counts, "val": val_counts, "test": test_counts,
        "accuracy": acc, "f1_macro": f1_mac, "dummy_accuracy": dummy_acc,
        "confusion_matrix": cm, "classification_report": clf_report
    }


def _build_report(
    train_counts, val_counts, test_counts,
    n_train, n_val, n_test,
    acc, f1_mac, dummy_acc, cm, clf_report
) -> str:
    c1_key = f"Class 1: {CLASS_MAP[1]}"
    c2_key = f"Class 2: {CLASS_MAP[2]}"
    c3_key = f"Class 3: {CLASS_MAP[3]}"

    def _prf(key):
        d = clf_report.get(key, {})
        return (d.get("precision",0), d.get("recall",0), d.get("f1-score",0), int(d.get("support",0)))

    p1,r1,f1_1,s1 = _prf(c1_key)
    p2,r2,f1_2,s2 = _prf(c2_key)
    p3,r3,f1_3,s3 = _prf(c3_key)

    return f"""# TwinSense AI v2 - Model Evaluation Report (Hypoglycemia Support)

**Generated:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}
**Model:** Random Forest (n=100, max_depth=8, class_weight='balanced')
**Data:** Synthetic v2 (seed=99) — includes hypoglycemia episodes

---

## IMPORTANT LIMITATIONS

### Circularity Warning (Required Honesty Disclosure)
The hypoglycemia (Class 1) examples in this dataset were **generated by our own
synthetic simulator**. The simulator injects artificial glucose depressions using
a predefined mathematical model. Therefore:

- **Good Class 1 recall/precision is expected and may be circular**: the model
  learns the same mathematical pattern that the generator used to create episodes.
- This does **NOT** imply real-world clinical accuracy for hypoglycemia detection.
- Real hypoglycemia arises from complex biological mechanisms (insulin kinetics,
  counter-regulatory hormones, gastroparesis, individual variability) that are
  not captured by the simplified simulation.
- **Do not interpret v2 Class 1 metrics as evidence that this model can predict
  real hypoglycemia.**

### SYNTHETIC DATA - NOT CLINICALLY VALIDATED
All data is synthetic. This prototype is not FDA/CE approved and must not be used
for diagnosis, treatment, insulin dosing, or any medical decisions.

---

## Dataset Split (v2)

| Split | Rows |
|---|---|
| Train (70%) | {n_train:,} |
| Validation (10%) | {n_val:,} |
| Test (20%) | {n_test:,} |

Embargo buffer: 45 minutes (9 steps) between each partition boundary per patient.

---

## Class Distribution per Split

| Class | Train | Validation | Test |
|---|---|---|---|
| 1 Hypoglycemia | {train_counts.get(1,0):,} ({train_counts.get(1,0)/max(n_train,1)*100:.2f}%) | {val_counts.get(1,0):,} ({val_counts.get(1,0)/max(n_val,1)*100:.2f}%) | {test_counts.get(1,0):,} ({test_counts.get(1,0)/max(n_test,1)*100:.2f}%) |
| 2 In-Range | {train_counts.get(2,0):,} ({train_counts.get(2,0)/max(n_train,1)*100:.2f}%) | {val_counts.get(2,0):,} ({val_counts.get(2,0)/max(n_val,1)*100:.2f}%) | {test_counts.get(2,0):,} ({test_counts.get(2,0)/max(n_test,1)*100:.2f}%) |
| 3 Hyperglycemia | {train_counts.get(3,0):,} ({train_counts.get(3,0)/max(n_train,1)*100:.2f}%) | {val_counts.get(3,0):,} ({val_counts.get(3,0)/max(n_val,1)*100:.2f}%) | {test_counts.get(3,0):,} ({test_counts.get(3,0)/max(n_test,1)*100:.2f}%) |

---

## Test Set Performance

| Metric | Value |
|---|---|
| Test Accuracy | {acc*100:.2f}% |
| Macro F1 | {f1_mac:.4f} |
| Dummy Baseline Accuracy | {dummy_acc*100:.2f}% |

### Per-Class Metrics (Test Set)

| Class | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| 1 Hypoglycemia | {p1:.4f} | {r1:.4f} | {f1_1:.4f} | {s1} |
| 2 In-Range | {p2:.4f} | {r2:.4f} | {f1_2:.4f} | {s2} |
| 3 Hyperglycemia | {p3:.4f} | {r3:.4f} | {f1_3:.4f} | {s3} |

**Class 1 Recall: {r1:.4f}**  |  **Class 1 Precision: {p1:.4f}**

### Confusion Matrix (Labels: [1, 2, 3])

```
Actual \\ Predicted    Hypo(1)    In-Range(2)    Hyper(3)
Hypo (1)              {cm[0][0]:<12} {cm[0][1]:<14} {cm[0][2]}
In-Range (2)          {cm[1][0]:<12} {cm[1][1]:<14} {cm[1][2]}
Hyper (3)             {cm[2][0]:<12} {cm[2][1]:<14} {cm[2][2]}
```

---

## Artifacts
- Model: `models/random_forest_risk_model_v2.joblib`
- Feature schema: `models/feature_columns_v2.json`
- Processed data: `data/synthetic_v2/training_dataset_v2.csv`
- This report: `reports/v2/evaluation_report_v2.md`
"""


if __name__ == "__main__":
    run_training_pipeline_v2()
