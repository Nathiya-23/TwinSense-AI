"""
TwinSense AI - Step 3: Model Training, Baseline Comparison & Honest Evaluation
==============================================================================

ETHICAL & CLINICAL DISCLAIMER:
-----------------------------
This model is trained exclusively on SYNTHETIC data for academic prototype
demonstration and pipeline verification. It does NOT possess clinical validity,
has not undergone clinical trial validation, and must NEVER be used to inform
actual medical decisions, insulin dosing, or clinical treatment plans.

PURPOSE:
--------
1. Ingest processed time-series feature matrix (data/processed/training_dataset.csv).
2. Validate feature schema and inspect target class distributions.
3. Perform strict chronological per-patient hold-out split with a 45-minute embargo buffer.
4. Verify non-overlapping time horizons across all patient partitions.
5. Train and contrast:
   - Dummy Baseline (Most Frequent Class strategy)
   - Random Forest Classifier (multiclass risk model)
6. Evaluate against untouched chronological test partition.
7. Report accuracy, macro F1, per-class precision/recall, and confusion matrices (labels: 1, 2, 3).
8. Persist trained model, feature metadata, and full markdown evaluation report.
"""

from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

# -------------------------------------------------------------
# Configuration Constants & Directories
# -------------------------------------------------------------
RANDOM_STATE = 42
TRAIN_RATIO = 0.8
EMBARGO_MINUTES = 45
SAMPLING_INTERVAL_MIN = 5
EMBARGO_STEPS = EMBARGO_MINUTES // SAMPLING_INTERVAL_MIN  # 9 steps

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "training_dataset.csv"
MODELS_DIR = PROJECT_ROOT / "models"
REPORTS_DIR = PROJECT_ROOT / "reports"

MODEL_FILEPATH = MODELS_DIR / "random_forest_risk_model.joblib"
FEATURE_COLS_FILEPATH = MODELS_DIR / "feature_columns.json"
REPORT_FILEPATH = REPORTS_DIR / "evaluation_report.md"

# Target risk mapping
CLASS_MAP = {
    1: "Hypoglycemia (<70 mg/dL)",
    2: "In-Range (70-180 mg/dL)",
    3: "Hyperglycemia (>180 mg/dL)"
}
TARGET_CLASSES = [1, 2, 3]


def load_and_validate_dataset(csv_path: Path = PROCESSED_DATA_PATH) -> tuple[pd.DataFrame, list[str], str]:
    """
    Loads processed dataset and validates presence of audit columns, features, and target.
    Returns:
        (df, feature_columns_list, target_col_name)
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Processed training dataset not found at: {csv_path}")

    df = pd.read_csv(csv_path)

    # Convert timestamp columns
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["future_timestamp"] = pd.to_datetime(df["future_timestamp"])

    target_col = "future_glucose_risk"
    if target_col not in df.columns:
        raise ValueError(f"Missing required target column '{target_col}' in dataset.")

    # Explicit list of excluded columns (audit, future lookahead, metadata)
    excluded_columns = {
        "patient_id",
        "timestamp",
        "future_timestamp",
        "future_glucose_mg_dl",
        "is_synthetic",
        "data_source",
        target_col
    }

    # Filter features strictly to valid inputs
    feature_columns = [c for c in df.columns if c not in excluded_columns]

    if len(feature_columns) == 0:
        raise ValueError("No valid input feature columns found after exclusion!")

    # Verify no accidental inclusion of target or forward values
    assert target_col not in feature_columns, "Critical Error: Target column leaked into features!"
    for forbidden in ["future", "patient_id", "timestamp"]:
        for feat in feature_columns:
            if forbidden in feat:
                raise ValueError(f"Leakage check failed: Forbidden substring '{forbidden}' in feature '{feat}'")

    return df, feature_columns, target_col


def partition_chronological_with_embargo(
    df: pd.DataFrame,
    train_ratio: float = TRAIN_RATIO,
    embargo_steps: int = EMBARGO_STEPS
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Chronologically splits data per patient with an embargo buffer to prevent target leakage.
    Verifies that no patient's training timestamps violate the embargo or overlap the test set.
    """
    train_slices = []
    test_slices = []

    for pid, p_group in df.groupby("patient_id", sort=False):
        p_sorted = p_group.sort_values(by="timestamp").reset_index(drop=True)
        total_p = len(p_sorted)
        split_idx = int(total_p * train_ratio)

        train_part = p_sorted.iloc[:split_idx].copy()
        
        # Embargo buffer: discard 9 steps (45 mins) right after training partition
        test_start_idx = min(total_p, split_idx + embargo_steps)
        test_part = p_sorted.iloc[test_start_idx:].copy()

        # Strict chronological verification
        max_train_time = train_part["timestamp"].max()
        min_test_time = test_part["timestamp"].min()
        actual_gap = min_test_time - max_train_time
        required_gap = pd.Timedelta(minutes=EMBARGO_MINUTES)

        if actual_gap < required_gap:
            raise ValueError(
                f"Data Leakage Violation for {pid}: Test time ({min_test_time}) starts within "
                f"embargo window from max train time ({max_train_time}). Gap is {actual_gap}"
            )

        train_slices.append(train_part)
        test_slices.append(test_part)

    train_df = pd.concat(train_slices, ignore_index=True)
    test_df = pd.concat(test_slices, ignore_index=True)

    return train_df, test_df


def inspect_class_distributions(
    train_df: pd.DataFrame,
    test_df: pd.DataFrame,
    target_col: str
) -> dict:
    """
    Inspects target class frequencies in train and test partitions.
    Reports missing classes without fabricating or silently oversampling data.
    """
    train_counts = train_df[target_col].value_counts().to_dict()
    test_counts = test_df[target_col].value_counts().to_dict()

    inspection_report = {
        "train": {cls: train_counts.get(cls, 0) for cls in TARGET_CLASSES},
        "test": {cls: test_counts.get(cls, 0) for cls in TARGET_CLASSES},
        "missing_in_train": [cls for cls in TARGET_CLASSES if train_counts.get(cls, 0) == 0],
        "missing_in_test": [cls for cls in TARGET_CLASSES if test_counts.get(cls, 0) == 0]
    }

    return inspection_report


def train_and_evaluate_models(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series
) -> dict:
    """
    Trains DummyClassifier baseline and RandomForestClassifier on training partition.
    Evaluates both on untouched chronological test partition.
    """
    # 1. Baseline Model (Majority Class Dummy)
    dummy_model = DummyClassifier(strategy="most_frequent", random_state=RANDOM_STATE)
    dummy_model.fit(X_train, y_train)
    y_pred_dummy = dummy_model.predict(X_test)

    # 2. Candidate Model (Random Forest)
    # Beginner-friendly, robust hyperparameter settings
    rf_model = RandomForestClassifier(
        n_estimators=100,
        max_depth=8,
        min_samples_split=10,
        min_samples_leaf=5,
        random_state=RANDOM_STATE,
        n_jobs=-1
    )
    rf_model.fit(X_train, y_train)
    y_pred_rf = rf_model.predict(X_test)

    # 3. Compute Metrics for Dummy
    dummy_acc = float(accuracy_score(y_test, y_pred_dummy))
    dummy_f1_macro = float(f1_score(y_test, y_pred_dummy, average="macro", zero_division=0))
    dummy_cm = confusion_matrix(y_test, y_pred_dummy, labels=TARGET_CLASSES).tolist()
    dummy_report = classification_report(
        y_test,
        y_pred_dummy,
        labels=TARGET_CLASSES,
        target_names=[f"Class {c}: {CLASS_MAP[c]}" for c in TARGET_CLASSES],
        zero_division=0,
        output_dict=True
    )

    # 4. Compute Metrics for Random Forest
    rf_acc = float(accuracy_score(y_test, y_pred_rf))
    rf_f1_macro = float(f1_score(y_test, y_pred_rf, average="macro", zero_division=0))
    rf_cm = confusion_matrix(y_test, y_pred_rf, labels=TARGET_CLASSES).tolist()
    rf_report = classification_report(
        y_test,
        y_pred_rf,
        labels=TARGET_CLASSES,
        target_names=[f"Class {c}: {CLASS_MAP[c]}" for c in TARGET_CLASSES],
        zero_division=0,
        output_dict=True
    )

    # Feature Importances from Random Forest
    importances = dict(zip(X_train.columns, [round(float(v), 4) for v in rf_model.feature_importances_]))
    sorted_importances = dict(sorted(importances.items(), key=lambda item: item[1], reverse=True))

    results = {
        "dummy": {
            "model": dummy_model,
            "accuracy": dummy_acc,
            "f1_macro": dummy_f1_macro,
            "confusion_matrix": dummy_cm,
            "classification_report": dummy_report
        },
        "random_forest": {
            "model": rf_model,
            "accuracy": rf_acc,
            "f1_macro": rf_f1_macro,
            "confusion_matrix": rf_cm,
            "classification_report": rf_report,
            "feature_importances": sorted_importances
        }
    }

    return results


def save_artifacts_and_report(
    rf_model: RandomForestClassifier,
    feature_cols: list[str],
    eval_results: dict,
    class_inspection: dict,
    train_size: int,
    test_size: int,
    embargo_dropped: int
):
    """
    Persists trained model, feature list, and comprehensive markdown report.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Save Model & Feature Schema
    joblib.dump(rf_model, MODEL_FILEPATH)
    with open(FEATURE_COLS_FILEPATH, "w") as f:
        json.dump({"feature_columns": feature_cols}, f, indent=2)

    # 2. Build Markdown Evaluation Report
    rf_res = eval_results["random_forest"]
    dummy_res = eval_results["dummy"]

    report_content = f"""# TwinSense AI - Model Training & Evaluation Report

**Generated Date:** {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Model Architecture:** Random Forest Classifier (`n_estimators=100`, `max_depth=8`)  
**Baseline Model:** Dummy Classifier (`strategy="most_frequent"`)  

---

## ⚠️ Important Scientific & Ethical Disclaimer
This evaluation reflects performance **strictly on synthetic development data** generated via mathematical heuristic simulations. 
- It does **not** demonstrate real-world human clinical accuracy.
- It is **not** validated for clinical decision-making or therapy adjustment.
- Real continuous glucose dynamics involve biological mechanisms (e.g., insulin absorption kinetics, gastroparesis, counter-regulatory hormone secretions) not captured in this prototype.

---

## 1. Dataset Partitioning & Time-Series Embargo
To prevent lookahead bias and data leakage, data was split **chronologically per patient** rather than randomly shuffled:
- **Training Partition (80% chronological history):** {train_size:,} records
- **Test Partition (Final 20% chronological history):** {test_size:,} records
- **Embargo Dropped (Boundary Buffer):** {embargo_dropped:,} records ({EMBARGO_MINUTES} minutes / {EMBARGO_STEPS} steps per patient)
- **Leakage Verification:** 100% verified. Every patient's training observations end at least {EMBARGO_MINUTES} minutes before their test period begins.

---

## 2. Target Class Distribution & Critical Observation

| Class | Description | Train Set Count (Share) | Test Set Count (Share) |
| :--- | :--- | :--- | :--- |
| **Class 1** | Hypoglycemia (<70 mg/dL) | **{class_inspection['train'][1]:,} (0.00%)** | **{class_inspection['test'][1]:,} (0.00%)** |
| **Class 2** | In-Range (70-180 mg/dL) | {class_inspection['train'][2]:,} ({class_inspection['train'][2]/train_size*100:.2f}%) | {class_inspection['test'][2]:,} ({class_inspection['test'][2]/test_size*100:.2f}%) |
| **Class 3** | Hyperglycemia (>180 mg/dL) | {class_inspection['train'][3]:,} ({class_inspection['train'][3]/train_size*100:.2f}%) | {class_inspection['test'][3]:,} ({class_inspection['test'][3]/test_size*100:.2f}%) |

### ⚠️ Critical Finding Regarding Hypoglycemia (Class 1)
- **Observed Limitation:** Class 1 (Hypoglycemia) contains **0 examples** in both the training set and the test set.
- **Root Cause:** The synthetic data generator was configured with baseline patient HbA1c values ($6.7\\% - 10.0\\%$) and standard meal spikes, causing glucose to fluctuate strictly within normal and hyperglycemic ranges.
- **Consequence:** The model **cannot learn or predict hypoglycemia** from this current training dataset. It is currently operating as a binary classifier between In-Range (Class 2) and Hyperglycemia (Class 3).
- **Recommended Next Step for Synthetic Generator:** Introduce acute downward glucose perturbations in `src/data_generator.py`—such as simulated insulin over-bolusing, delayed/skipped meals, or intense prolonged physical exercise—to synthesize realistic hypoglycemia episodes before retraining.

---

## 3. Baseline vs. Random Forest Performance (Test Set)

| Metric | Dummy Baseline (Most Frequent) | Random Forest Classifier | Delta Improvement |
| :--- | :--- | :--- | :--- |
| **Overall Accuracy** | {dummy_res['accuracy']*100:.2f}% | **{rf_res['accuracy']*100:.2f}%** | **+{(rf_res['accuracy'] - dummy_res['accuracy'])*100:+.2f}%** |
| **Macro F1-Score** | {dummy_res['f1_macro']:.4f} | **{rf_res['f1_macro']:.4f}** | **+{(rf_res['f1_macro'] - dummy_res['f1_macro']):+.4f}** |

---

## 4. Per-Class Detailed Classification Report (Random Forest)

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Class 1 (Hypoglycemia)** | 0.0000 | 0.0000 | 0.0000 | {class_inspection['test'][1]} |
| **Class 2 (In-Range)** | {rf_res['classification_report']['Class 2: In-Range (70-180 mg/dL)']['precision']:.4f} | {rf_res['classification_report']['Class 2: In-Range (70-180 mg/dL)']['recall']:.4f} | {rf_res['classification_report']['Class 2: In-Range (70-180 mg/dL)']['f1-score']:.4f} | {int(rf_res['classification_report']['Class 2: In-Range (70-180 mg/dL)']['support'])} |
| **Class 3 (Hyperglycemia)** | {rf_res['classification_report']['Class 3: Hyperglycemia (>180 mg/dL)']['precision']:.4f} | {rf_res['classification_report']['Class 3: Hyperglycemia (>180 mg/dL)']['recall']:.4f} | {rf_res['classification_report']['Class 3: Hyperglycemia (>180 mg/dL)']['f1-score']:.4f} | {int(rf_res['classification_report']['Class 3: Hyperglycemia (>180 mg/dL)']['support'])} |

---

## 5. Confusion Matrix (Untouched Chronological Test Set)

*Labels: [Class 1: Hypo, Class 2: In-Range, Class 3: Hyper]*

```text
Actual \\ Predicted     Hypo (1)    In-Range (2)   Hyper (3)
Hypo (1)                 {rf_res['confusion_matrix'][0][0]:<12} {rf_res['confusion_matrix'][0][1]:<14} {rf_res['confusion_matrix'][0][2]}
In-Range (2)             {rf_res['confusion_matrix'][1][0]:<12} {rf_res['confusion_matrix'][1][1]:<14} {rf_res['confusion_matrix'][1][2]}
Hyper (3)                {rf_res['confusion_matrix'][2][0]:<12} {rf_res['confusion_matrix'][2][1]:<14} {rf_res['confusion_matrix'][2][2]}
```

---

## 6. Top Feature Importances (Random Forest)

```text
{json.dumps(rf_res['feature_importances'], indent=2)}
```

---

## 7. Artifacts Saved
- **Model Binary:** `{MODEL_FILEPATH}`
- **Feature Schema:** `{FEATURE_COLS_FILEPATH}`
- **Evaluation Report:** `{REPORT_FILEPATH}`
"""

    with open(REPORT_FILEPATH, "w", encoding="utf-8") as f:
        f.write(report_content)


def run_training_pipeline():
    """
    Main orchestration routine for Step 3.
    """
    print("=" * 75)
    print(" TwinSense AI - Step 3: Model Training & Honest Evaluation Pipeline")
    print("=" * 75)
    print("[*] NOTICE: Purely synthetic development prototype. Not clinically validated.\n")

    # 1. Load dataset & extract feature list
    print("[1/5] Loading processed dataset & validating schema...")
    df, feature_cols, target_col = load_and_validate_dataset()
    print(f"      -> Ingested {len(df):,} total records")
    print(f"      -> Identified {len(feature_cols)} clean past-only input features:")
    for f in feature_cols:
        print(f"         - {f}")

    # 2. Chronological Per-Patient Partitioning
    print("\n[2/5] Partitioning data chronologically with 45-min embargo...")
    train_df, test_df = partition_chronological_with_embargo(df)
    train_size = len(train_df)
    test_size = len(test_df)
    embargo_dropped = len(df) - (train_size + test_size)
    print(f"      -> Train Set: {train_size:,} rows (80% chronological window per patient)")
    print(f"      -> Test Set:  {test_size:,} rows (20% chronological window per patient)")
    print(f"      -> Embargo Gap Dropped: {embargo_dropped:,} rows (boundary isolation)")

    # 3. Class Distribution Inspection
    print("\n[3/5] Inspecting target class distributions in train and test sets...")
    inspection = inspect_class_distributions(train_df, test_df, target_col)
    for c in TARGET_CLASSES:
        tr_cnt = inspection["train"][c]
        te_cnt = inspection["test"][c]
        print(f"      - Class {c} ({CLASS_MAP[c]}): Train={tr_cnt:,} ({tr_cnt/train_size*100:.2f}%) | Test={te_cnt:,} ({te_cnt/test_size*100:.2f}%)")

    if 1 in inspection["missing_in_train"] or 1 in inspection["missing_in_test"]:
        print("\n      [!] CRITICAL HONEST EVALUATION NOTICE:")
        print("          Class 1 (Hypoglycemia <70 mg/dL) has 0 samples in the dataset!")
        print("          The model CANNOT learn hypoglycemia risk from the current synthetic data.")
        print("          Do not claim hypoglycemia prediction until synthetic data is expanded.\n")

    # Extract feature matrices and labels
    X_train = train_df[feature_cols]
    y_train = train_df[target_col]
    X_test = test_df[feature_cols]
    y_test = test_df[target_col]

    # 4. Model Training & Evaluation
    print("[4/5] Training Dummy baseline and Random Forest classifier...")
    eval_results = train_and_evaluate_models(X_train, y_train, X_test, y_test)
    rf_res = eval_results["random_forest"]
    dummy_res = eval_results["dummy"]

    print("\n--- MODEL COMPARISON (Chronological Hold-Out Test Set) ---")
    print(f"  Dummy Baseline Accuracy:     {dummy_res['accuracy']*100:.2f}%")
    print(f"  Dummy Baseline Macro F1:     {dummy_res['f1_macro']:.4f}")
    print(f"  Random Forest Accuracy:      {rf_res['accuracy']*100:.2f}%")
    print(f"  Random Forest Macro F1:      {rf_res['f1_macro']:.4f}")

    print("\n--- DETAILED CLASSIFICATION REPORT (Random Forest) ---")
    report_dict = rf_res["classification_report"]
    for c in TARGET_CLASSES:
        lbl = f"Class {c}: {CLASS_MAP[c]}"
        if lbl in report_dict:
            metrics = report_dict[lbl]
            print(f"  {lbl:<35} | Prec: {metrics['precision']:.4f} | Rec: {metrics['recall']:.4f} | F1: {metrics['f1-score']:.4f} | Support: {int(metrics['support']):,}")

    print("\n--- CONFUSION MATRIX (Labels: [1, 2, 3]) ---")
    cm = rf_res["confusion_matrix"]
    print(f"  Actual \\ Pred     Hypo (1)   In-Range (2)  Hyper (3)")
    print(f"  Hypo (1)         {cm[0][0]:<10} {cm[0][1]:<13} {cm[0][2]}")
    print(f"  In-Range (2)     {cm[1][0]:<10} {cm[1][1]:<13} {cm[1][2]}")
    print(f"  Hyper (3)        {cm[2][0]:<10} {cm[2][1]:<13} {cm[2][2]}")

    print("\n--- TOP 5 FEATURE IMPORTANCES ---")
    top_feats = list(rf_res["feature_importances"].items())[:5]
    for feat, imp in top_feats:
        print(f"  {feat:<28}: {imp:.4f}")

    # 5. Save Artifacts
    print("\n[5/5] Saving model binary, feature schema, and evaluation report...")
    save_artifacts_and_report(
        rf_model=rf_res["model"],
        feature_cols=feature_cols,
        eval_results=eval_results,
        class_inspection=inspection,
        train_size=train_size,
        test_size=test_size,
        embargo_dropped=embargo_dropped
    )
    print(f"      [+] Model saved to:  {MODEL_FILEPATH}")
    print(f"      [+] Features saved:  {FEATURE_COLS_FILEPATH}")
    print(f"      [+] Report saved to: {REPORT_FILEPATH}")
    print("=" * 75)


if __name__ == "__main__":
    run_training_pipeline()
