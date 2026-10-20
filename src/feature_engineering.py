"""
TwinSense AI - Step 2: Feature Engineering & Time-Windowing Pipeline
====================================================================

ETHICAL & CLINICAL DISCLAIMER:
-----------------------------
This module processes SYNTHETIC data designed strictly for research, pipeline
prototyping, and academic demonstration. It does NOT process real clinical records,
nor does it constitute a clinically validated forecasting algorithm.

PURPOSE:
--------
1. Ingest raw synthetic patient profiles and CGM/wearable time-series logs.
2. Join static baseline health records (EHR) to dynamic sensor telemetry per patient.
3. Compute strictly backward-looking (past-only) rolling features at 5-minute sampling:
   - Current glucose reading (time t).
   - Mean glucose over past 15 min (3 readings: t-10m, t-5m, t).
   - Mean glucose over past 30 min (6 readings: t-25m to t).
   - Glucose change over past 15 min (reading at t minus reading at t-15m).
   - Mean heart rate over past 15 min.
   - Total steps over past 15 min.
   - Current meal event (time t).
   - Baseline EHR features: age, BMI, baseline HbA1c, diabetes duration.
4. Construct target: Future glucose risk category exactly 45 minutes ahead:
   - 1 = hypoglycemia (< 70 mg/dL)
   - 2 = in_range (70 to 180 mg/dL, inclusive)
   - 3 = hyperglycemia (> 180 mg/dL)
5. Enforce strict patient boundary isolation and chronological integrity.
6. Provide chronological per-patient train/test split functionality to prevent leakage.
"""

from pathlib import Path
import numpy as np
import pandas as pd

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

PATIENT_PROFILES_PATH = DATA_RAW_DIR / "patient_profiles.csv"
GLUCOSE_TIMESERIES_PATH = DATA_RAW_DIR / "glucose_timeseries.csv"
OUTPUT_TRAINING_PATH = DATA_PROCESSED_DIR / "training_dataset.csv"

# Sampling Parameters
SAMPLING_INTERVAL_MINUTES = 5
PREDICTION_HORIZON_MINUTES = 45
STEPS_AHEAD = PREDICTION_HORIZON_MINUTES // SAMPLING_INTERVAL_MINUTES  # 9 steps

# Window Definitions (at 5-min intervals)
# 15 min window: 3 intervals (t-10m, t-5m, t)
WINDOW_15M_STEPS = 15 // SAMPLING_INTERVAL_MINUTES  # 3 steps
# 30 min window: 6 intervals (t-25m, ..., t)
WINDOW_30M_STEPS = 30 // SAMPLING_INTERVAL_MINUTES  # 6 steps
# 15 min lag for change: reading(t) - reading(t - 15m)
LAG_15M_STEPS = 15 // SAMPLING_INTERVAL_MINUTES     # 3 steps


def load_raw_data(
    profiles_path: Path = PATIENT_PROFILES_PATH,
    timeseries_path: Path = GLUCOSE_TIMESERIES_PATH
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load raw patient profiles and glucose time-series CSVs without altering raw files.
    """
    if not profiles_path.exists():
        raise FileNotFoundError(f"Missing patient profiles at: {profiles_path}")
    if not timeseries_path.exists():
        raise FileNotFoundError(f"Missing glucose timeseries at: {timeseries_path}")

    profiles_df = pd.read_csv(profiles_path)
    timeseries_df = pd.read_csv(timeseries_path)

    # Parse timestamps
    timeseries_df["timestamp"] = pd.to_datetime(timeseries_df["timestamp"])

    # Sort strictly by patient_id and timestamp
    timeseries_df = timeseries_df.sort_values(by=["patient_id", "timestamp"]).reset_index(drop=True)

    return profiles_df, timeseries_df


def engineer_features_and_target(
    profiles_df: pd.DataFrame,
    timeseries_df: pd.DataFrame
) -> pd.DataFrame:
    """
    Computes past-only features per patient, aligns exact 45-minute targets,
    and merges patient baseline EHR features.
    
    WINDOWING SPECIFICATION:
    -----------------------
    - Current reading (t) is included in the current features.
    - Past rolling features include [t - window + 1, ..., t].
    - Zero future readings are used in feature columns (strict lookahead prevention).
    - Future readings are used ONLY to create the 45-minute target column.
    """
    processed_dfs = []

    # Process each patient independently to guarantee zero cross-patient data bleeding
    for pid, p_group in timeseries_df.groupby("patient_id", sort=False):
        # Work on a chronologically sorted copy for this patient
        df_p = p_group.sort_values(by="timestamp").copy()

        # -------------------------------------------------------------
        # 1. Past-Only Dynamic Sensor Features (Rolling Windows)
        # -------------------------------------------------------------
        # Current glucose at time t
        df_p["current_glucose_mg_dl"] = df_p["glucose_mg_dl"]

        # Mean glucose over past 15 minutes: includes t-10m, t-5m, t (window=3)
        df_p["glucose_mean_past_15m"] = df_p["glucose_mg_dl"].rolling(
            window=WINDOW_15M_STEPS, min_periods=WINDOW_15M_STEPS
        ).mean()

        # Mean glucose over past 30 minutes: includes t-25m to t (window=6)
        df_p["glucose_mean_past_30m"] = df_p["glucose_mg_dl"].rolling(
            window=WINDOW_30M_STEPS, min_periods=WINDOW_30M_STEPS
        ).mean()

        # Glucose change over past 15 minutes: glucose(t) - glucose(t - 15m) (shift=3)
        df_p["glucose_change_past_15m"] = (
            df_p["glucose_mg_dl"] - df_p["glucose_mg_dl"].shift(LAG_15M_STEPS)
        )

        # Mean heart rate over past 15 minutes: includes t-10m, t-5m, t
        df_p["heart_rate_mean_past_15m"] = df_p["heart_rate"].rolling(
            window=WINDOW_15M_STEPS, min_periods=WINDOW_15M_STEPS
        ).mean()

        # Total steps over past 15 minutes: sum of steps in [t-10m, t-5m, t]
        df_p["steps_sum_past_15m"] = df_p["steps"].rolling(
            window=WINDOW_15M_STEPS, min_periods=WINDOW_15M_STEPS
        ).sum()

        # Current meal event at time t
        df_p["current_meal_event"] = df_p["meal_event"]

        # -------------------------------------------------------------
        # 2. Target Generation (Exact 45 Minutes Forward)
        # -------------------------------------------------------------
        # Shift -9 steps forward to look at reading at t + 45 minutes
        df_p["future_timestamp"] = df_p["timestamp"].shift(-STEPS_AHEAD)
        df_p["future_glucose_mg_dl"] = df_p["glucose_mg_dl"].shift(-STEPS_AHEAD)

        # Verify exact 45-minute timestamp alignment
        expected_future_time = df_p["timestamp"] + pd.Timedelta(minutes=PREDICTION_HORIZON_MINUTES)
        valid_alignment = df_p["future_timestamp"] == expected_future_time

        # Invalidate future readings if the alignment is not exactly 45 minutes
        df_p.loc[~valid_alignment, "future_glucose_mg_dl"] = np.nan

        # Categorize future glucose into 3 risk levels:
        # 1 = hypoglycemia (< 70 mg/dL)
        # 2 = in_range (70 to 180 mg/dL, inclusive)
        # 3 = hyperglycemia (> 180 mg/dL)
        conditions = [
            df_p["future_glucose_mg_dl"] < 70.0,
            (df_p["future_glucose_mg_dl"] >= 70.0) & (df_p["future_glucose_mg_dl"] <= 180.0),
            df_p["future_glucose_mg_dl"] > 180.0
        ]
        choices = [1, 2, 3]
        df_p["future_glucose_risk"] = np.select(conditions, choices, default=np.nan)

        processed_dfs.append(df_p)

    combined_features_df = pd.concat(processed_dfs, ignore_index=True)

    # -----------------------------------------------------------------
    # 3. Merge Static Patient Baseline Features (EHR records)
    # -----------------------------------------------------------------
    # Select baseline features to join
    profile_subset = profiles_df[[
        "patient_id",
        "age",
        "bmi",
        "baseline_hba1c",
        "diabetes_duration_years"
    ]].copy()

    merged_df = pd.merge(combined_features_df, profile_subset, on="patient_id", how="left")

    # -----------------------------------------------------------------
    # 4. Filter Rows with Incomplete History or Future Target
    # -----------------------------------------------------------------
    # Exclude initial warmup rows (where 30m rolling stats are NaN)
    # and tail horizon rows (where 45m ahead target is unavailable)
    required_columns = [
        "current_glucose_mg_dl",
        "glucose_mean_past_15m",
        "glucose_mean_past_30m",
        "glucose_change_past_15m",
        "heart_rate_mean_past_15m",
        "steps_sum_past_15m",
        "current_meal_event",
        "age",
        "bmi",
        "baseline_hba1c",
        "diabetes_duration_years",
        "future_glucose_risk"
    ]

    clean_df = merged_df.dropna(subset=required_columns).copy()

    # Convert target to integer type
    clean_df["future_glucose_risk"] = clean_df["future_glucose_risk"].astype(int)

    # -----------------------------------------------------------------
    # 5. Format Column Order (Audit Columns + Features + Target)
    # -----------------------------------------------------------------
    # Exclude identifiers, timestamps, raw future glucose, is_synthetic, data_source from features.
    # Keep patient_id and timestamps purely as audit columns for traceability.
    final_columns = [
        # Audit columns
        "patient_id",
        "timestamp",
        "future_timestamp",
        # Input features (past & static only)
        "current_glucose_mg_dl",
        "glucose_mean_past_15m",
        "glucose_mean_past_30m",
        "glucose_change_past_15m",
        "heart_rate_mean_past_15m",
        "steps_sum_past_15m",
        "current_meal_event",
        "age",
        "bmi",
        "baseline_hba1c",
        "diabetes_duration_years",
        # Prediction target
        "future_glucose_risk"
    ]

    return clean_df[final_columns].reset_index(drop=True)


def validate_processed_dataset(dataset_df: pd.DataFrame) -> dict:
    """
    Executes automated validation checks:
    - Zero nulls across all features and target
    - Target labels strictly in {1, 2, 3}
    - Exact 45-minute timestamp alignment between timestamp and future_timestamp
    - Chronological ordering within each patient
    - Non-empty records per patient (patient separation intact)
    """
    report = {"status": "PASSED", "checks": {}}

    # 1. Missing Values Check
    null_counts = int(dataset_df.isnull().sum().sum())
    report["checks"]["no_missing_values"] = {
        "passed": (null_counts == 0),
        "total_nulls": null_counts
    }

    # 2. Target Label Set Validity
    unique_targets = set(dataset_df["future_glucose_risk"].unique())
    report["checks"]["target_labels_valid"] = {
        "passed": unique_targets.issubset({1, 2, 3}),
        "unique_target_values": sorted(list(unique_targets))
    }

    # 3. Exact 45-minute Target Gap Verification
    gaps = (pd.to_datetime(dataset_df["future_timestamp"]) - pd.to_datetime(dataset_df["timestamp"]))
    expected_gap = pd.Timedelta(minutes=45)
    invalid_gaps = int((gaps != expected_gap).sum())
    report["checks"]["exact_45m_alignment"] = {
        "passed": (invalid_gaps == 0),
        "invalid_gap_count": invalid_gaps
    }

    # 4. Chronological Ordering per Patient
    is_ordered = True
    for pid, p_df in dataset_df.groupby("patient_id"):
        ts_series = pd.to_datetime(p_df["timestamp"])
        if not ts_series.is_monotonic_increasing:
            is_ordered = False
            break
    report["checks"]["chronological_ordering"] = {
        "passed": is_ordered
    }

    # 5. Patient Count & Separation
    patient_counts = dataset_df["patient_id"].value_counts().to_dict()
    report["checks"]["patient_separation"] = {
        "passed": len(patient_counts) > 0 and all(c > 0 for c in patient_counts.values()),
        "patient_count": len(patient_counts),
        "min_patient_records": min(patient_counts.values()),
        "max_patient_records": max(patient_counts.values())
    }

    all_passed = all(check["passed"] for check in report["checks"].values())
    if not all_passed:
        report["status"] = "FAILED"
        raise ValueError(f"Feature engineering validation failed: {report}")

    return report


def split_train_test_chronological(
    dataset_df: pd.DataFrame,
    train_ratio: float = 0.8,
    embargo_steps: int = STEPS_AHEAD
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits the dataset chronologically within each patient to avoid lookahead bias
    and data leakage.

    NOTE ON TIME-SERIES EMBARGO:
    Because our target forecasts 45 minutes (9 steps) into the future, a random
    k-fold or shuffle split causes severe data leakage. Even a naive chronological split
    can leak if the last training sample's 45m target overlaps with the test set's input window.
    An embargo buffer of `embargo_steps` is optionally omitted between train and test
    to guarantee strictly zero leakage across the partition boundary.
    """
    train_dfs = []
    test_dfs = []

    for pid, p_df in dataset_df.groupby("patient_id", sort=False):
        p_sorted = p_df.sort_values(by="timestamp").reset_index(drop=True)
        n = len(p_sorted)
        split_idx = int(n * train_ratio)

        # Train partition: [0, split_idx]
        train_p = p_sorted.iloc[:split_idx]

        # Test partition: [split_idx + embargo_steps, n] to prevent target overlap
        start_test_idx = min(n, split_idx + embargo_steps)
        test_p = p_sorted.iloc[start_test_idx:]

        train_dfs.append(train_p)
        test_dfs.append(test_p)

    train_df = pd.concat(train_dfs, ignore_index=True)
    test_df = pd.concat(test_dfs, ignore_index=True)

    return train_df, test_df


def run_pipeline() -> tuple[pd.DataFrame, dict]:
    """
    Main orchestration routine for Step 2:
    1. Loads raw CSV datasets without modifying them.
    2. Constructs engineered features and aligned 45-minute risk targets.
    3. Runs integrity validations.
    4. Writes processed output to data/processed/training_dataset.csv.
    """
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" TwinSense AI - Step 2: Feature Engineering & Time-Windowing")
    print("=" * 70)

    # 1. Load raw data
    print("[1/4] Loading raw patient profiles and glucose time-series...")
    profiles_df, timeseries_df = load_raw_data()
    print(f"      -> Loaded {len(profiles_df)} patient profiles")
    print(f"      -> Loaded {len(timeseries_df)} time-series readings")

    # 2. Engineer features
    print("[2/4] Constructing past-only rolling features & 45-minute risk target...")
    dataset_df = engineer_features_and_target(profiles_df, timeseries_df)
    print(f"      -> Generated {len(dataset_df)} processed rows with complete history & targets")

    # 3. Validate
    print("[3/4] Running feature engineering validation suite...")
    report = validate_processed_dataset(dataset_df)
    print("      -> Validation Status:", report["status"])
    for check_name, check_data in report["checks"].items():
        print(f"         - {check_name}: {'PASS' if check_data['passed'] else 'FAIL'}")

    # 4. Save
    print(f"[4/4] Saving processed dataset to: {OUTPUT_TRAINING_PATH}...")
    dataset_df.to_csv(OUTPUT_TRAINING_PATH, index=False)
    print(f"      [+] Saved successfully ({len(dataset_df)} rows)")

    # 5. Class distribution & statistics
    class_map = {1: "Hypoglycemia (<70)", 2: "In-Range (70-180)", 3: "Hyperglycemia (>180)"}
    counts = dataset_df["future_glucose_risk"].value_counts().sort_index()

    print("\n--- TARGET CLASS DISTRIBUTION (`future_glucose_risk`) ---")
    for cls_val, cnt in counts.items():
        pct = (cnt / len(dataset_df)) * 100
        print(f"  Class {cls_val} ({class_map.get(cls_val, 'Unknown')}): {cnt:,} rows ({pct:.2f}%)")

    # Split verification test
    train_df, test_df = split_train_test_chronological(dataset_df, train_ratio=0.8)
    print(f"\n--- CHRONOLOGICAL EMBARGOED SPLIT CHECK ---")
    print(f"  Training Set: {len(train_df):,} rows")
    print(f"  Test Set:     {len(test_df):,} rows")
    print(f"  Embargo Dropped (Boundary Protection): {len(dataset_df) - (len(train_df) + len(test_df)):,} rows")
    print("=" * 70)

    return dataset_df, report


if __name__ == "__main__":
    dataset_df, report = run_pipeline()

    print("\n--- SAMPLE PROCESSED ROWS (Top 3) ---")
    sample_cols = [
        "patient_id", "timestamp", "current_glucose_mg_dl",
        "glucose_mean_past_15m", "glucose_change_past_15m",
        "baseline_hba1c", "future_glucose_risk"
    ]
    print(dataset_df[sample_cols].head(3).to_string(index=False))
