"""
TwinSense AI - Deterministic Synthetic Healthcare Data Generator
================================================================

ETHICAL & CLINICAL DISCLAIMER:
-----------------------------
This module generates ARTIFICIAL, SYNTHETIC data strictly for software
prototyping, data pipeline engineering, and machine learning development.
It does NOT represent real patient health records or validated human physiology.
The mathematical formulations (circadian drifts, postprandial curves, activity
adjustments) are simplified heuristics and must NOT be used for clinical decision-
making, medical diagnosis, or treatment planning.

FEATURES:
---------
1. Reproducible & deterministic generation using a fixed random seed.
2. Distinct tabular patient profiles (static historical baseline).
3. Paired wearable continuous glucose monitor (CGM) & biometric time-series.
4. Comprehensive integrity validations (nulls, bounds, duplicates, foreign keys).
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# ---------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------
RANDOM_SEED = 42
NUM_PATIENTS = 10
SIMULATION_DAYS = 7
INTERVAL_MINUTES = 5  # Standard Continuous Glucose Monitor (CGM) sampling rate

# Physiologic simulation bounds for validation
GLUCOSE_MIN_BOUND = 40.0   # Severe hypoglycemia limit
GLUCOSE_MAX_BOUND = 400.0  # Severe hyperglycemia limit

# Directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW_DIR = PROJECT_ROOT / "data" / "raw"
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


def generate_patient_profiles(num_patients: int = NUM_PATIENTS, seed: int = RANDOM_SEED) -> pd.DataFrame:
    """
    Generate synthetic historical patient profiles (EHR-style baseline records).
    
    Parameters:
        num_patients: Number of synthetic patient records to generate.
        seed: Fixed random seed for deterministic reproducibility.
        
    Returns:
        pd.DataFrame containing patient baseline demographic and clinical features.
    """
    rng = np.random.default_rng(seed)

    patient_ids = [f"SYNTH_PAT_{i+1:03d}" for i in range(num_patients)]
    
    # Realistic distributions for adult diabetes cohort
    ages = rng.integers(24, 76, size=num_patients)
    bmis = np.round(rng.normal(loc=28.5, scale=4.8, size=num_patients).clip(19.0, 44.0), 1)
    
    # 35% Type 1 Diabetes, 65% Type 2 Diabetes
    diabetes_types = rng.choice(["Type 1", "Type 2"], size=num_patients, p=[0.35, 0.65])
    
    # Baseline HbA1c (%) typically 5.8% to 11.2% in simulated cohorts
    baseline_hba1c = np.round(rng.normal(loc=7.6, scale=1.1, size=num_patients).clip(5.7, 12.0), 1)
    
    # Duration of diabetes (years) bounded reasonably by patient age
    durations = []
    for i in range(num_patients):
        max_duration = max(1, ages[i] - 18)
        dur = int(rng.integers(1, min(35, max_duration) + 1))
        durations.append(dur)

    profiles_df = pd.DataFrame({
        "patient_id": patient_ids,
        "age": ages,
        "bmi": bmis,
        "diabetes_type": diabetes_types,
        "baseline_hba1c": baseline_hba1c,
        "diabetes_duration_years": durations,
        "is_synthetic": True,
        "data_source": "synthetic_simulation_twin_v1"
    })

    return profiles_df


def _simulate_single_patient_cgm(
    patient_id: str,
    baseline_hba1c: float,
    diabetes_type: str,
    start_time: datetime,
    total_steps: int,
    rng: np.random.Generator
) -> pd.DataFrame:
    """
    Simulates time-series continuous glucose monitor (CGM) telemetry for a single patient.
    Uses an autoregressive formulation with circadian drift, meal spikes, and exercise effects.
    """
    # Estimated average glucose (eAG) in mg/dL from baseline HbA1c (ADAG formula)
    # eAG = 28.7 * HbA1c - 46.7
    resting_glucose = 28.7 * baseline_hba1c - 46.7
    resting_glucose = float(np.clip(resting_glucose, 100.0, 240.0))

    timestamps = []
    glucose_readings = []
    heart_rates = []
    steps_list = []
    meal_events = []

    # Dynamic state trackers
    current_glucose = resting_glucose + rng.normal(0, 5)
    postprandial_surge = 0.0  # Residual glucose from meals
    
    current_dt = start_time

    for step in range(total_steps):
        hour = current_dt.hour
        minute = current_dt.minute
        time_fraction = hour + minute / 60.0

        # 1. Meal Schedule & Event Detection
        # Breakfast (07:30-08:30), Lunch (12:30-13:30), Dinner (19:00-20:00), Snack (16:00-16:30)
        is_meal = 0
        if minute == 0 and hour in [8, 13, 19]:
            # Main meals
            is_meal = 1
            # Meal carb surge magnitude depends on diabetes type
            surge_mag = rng.uniform(45.0, 95.0) if diabetes_type == "Type 1" else rng.uniform(30.0, 70.0)
            postprandial_surge += surge_mag
        elif minute == 30 and hour == 16 and rng.random() < 0.5:
            # 50% probability of an afternoon snack
            is_meal = 1
            postprandial_surge += rng.uniform(20.0, 40.0)

        # Exponential decay of postprandial glucose effect (half-life ~ 45 mins = 9 intervals)
        postprandial_surge *= 0.92

        # 2. Activity (Steps & Heart Rate)
        # Sleep hours (23:00 to 07:00): low heart rate, zero steps
        if 23 <= hour or hour < 7:
            step_count = int(rng.poisson(lam=1.5))
            hr = int(rng.normal(62, 3))
            activity_drop = 0.0
        else:
            # Daytime
            # Chance of deliberate walk or exercise
            if rng.random() < 0.08:
                step_count = int(rng.uniform(150, 450))
                hr = int(rng.normal(108, 10))
                activity_drop = step_count * 0.025  # Glucose consumed by exertion
            else:
                step_count = int(rng.uniform(5, 50))
                hr = int(rng.normal(74, 5))
                activity_drop = step_count * 0.005

        # 3. Circadian Rhythm (Dawn phenomenon: subtle glucose rise between 04:00 and 07:00)
        circadian_drift = 12.0 * np.sin(2 * np.pi * (time_fraction - 6.0) / 24.0)
        if 4 <= hour <= 7:
            circadian_drift += 15.0

        # 4. Autoregressive Update
        target = resting_glucose + circadian_drift + postprandial_surge - activity_drop
        # AR(1) inertia coefficient
        alpha = 0.88
        stochastic_noise = rng.normal(0, 3.2)
        current_glucose = alpha * current_glucose + (1.0 - alpha) * target + stochastic_noise

        # Physical clamping to valid physiological simulation bounds
        current_glucose = float(np.clip(current_glucose, GLUCOSE_MIN_BOUND, GLUCOSE_MAX_BOUND))

        # Record reading
        timestamps.append(current_dt.strftime("%Y-%m-%d %H:%M:%S"))
        glucose_readings.append(round(current_glucose, 1))
        heart_rates.append(int(np.clip(hr, 45, 185)))
        steps_list.append(int(max(0, step_count)))
        meal_events.append(is_meal)

        current_dt += timedelta(minutes=INTERVAL_MINUTES)

    return pd.DataFrame({
        "patient_id": patient_id,
        "timestamp": timestamps,
        "glucose_mg_dl": glucose_readings,
        "heart_rate": heart_rates,
        "steps": steps_list,
        "meal_event": meal_events,
        "is_synthetic": True,
        "data_source": "synthetic_simulation_twin_v1"
    })


def generate_timeseries_data(
    patient_profiles: pd.DataFrame,
    days: int = SIMULATION_DAYS,
    interval_min: int = INTERVAL_MINUTES,
    seed: int = RANDOM_SEED
) -> pd.DataFrame:
    """
    Generate synthetic time-series wearable stream for each patient in the profile DataFrame.
    """
    total_steps_per_patient = int((days * 24 * 60) / interval_min)
    base_start_time = datetime(2026, 3, 1, 0, 0, 0)
    
    all_series = []
    for idx, row in patient_profiles.iterrows():
        # Independent yet reproducible deterministic seed per patient
        patient_seed = seed + int(idx) * 1013
        p_rng = np.random.default_rng(patient_seed)
        
        p_df = _simulate_single_patient_cgm(
            patient_id=row["patient_id"],
            baseline_hba1c=float(row["baseline_hba1c"]),
            diabetes_type=str(row["diabetes_type"]),
            start_time=base_start_time,
            total_steps=total_steps_per_patient,
            rng=p_rng
        )
        all_series.append(p_df)

    combined_df = pd.concat(all_series, ignore_index=True)
    return combined_df


def validate_synthetic_datasets(profiles_df: pd.DataFrame, timeseries_df: pd.DataFrame) -> dict:
    """
    Runs comprehensive data validation checks:
    - Missing values
    - Duplicate timestamps per patient
    - Foreign key integrity (invalid/orphan patient IDs)
    - Glucose readings outside acceptable simulation bounds
    """
    validation_report = {
        "status": "PASSED",
        "checks": {}
    }

    # 1. Check Missing / Null values
    prof_nulls = int(profiles_df.isnull().sum().sum())
    ts_nulls = int(timeseries_df.isnull().sum().sum())
    validation_report["checks"]["null_values"] = {
        "passed": (prof_nulls == 0 and ts_nulls == 0),
        "profiles_null_count": prof_nulls,
        "timeseries_null_count": ts_nulls
    }

    # 2. Check Duplicate Timestamps per patient
    duplicate_rows = timeseries_df.duplicated(subset=["patient_id", "timestamp"]).sum()
    validation_report["checks"]["duplicate_timestamps"] = {
        "passed": (duplicate_rows == 0),
        "duplicate_count": int(duplicate_rows)
    }

    # 3. Check Foreign Key / Patient ID consistency
    profile_pids = set(profiles_df["patient_id"].unique())
    ts_pids = set(timeseries_df["patient_id"].unique())
    orphan_pids = ts_pids - profile_pids
    missing_pids = profile_pids - ts_pids
    validation_report["checks"]["patient_id_consistency"] = {
        "passed": (len(orphan_pids) == 0 and len(missing_pids) == 0),
        "orphan_in_timeseries": list(orphan_pids),
        "missing_in_timeseries": list(missing_pids)
    }

    # 4. Check Simulation Glucose Bounds
    min_observed_glucose = float(timeseries_df["glucose_mg_dl"].min())
    max_observed_glucose = float(timeseries_df["glucose_mg_dl"].max())
    out_of_bounds = int(((timeseries_df["glucose_mg_dl"] < GLUCOSE_MIN_BOUND) |
                         (timeseries_df["glucose_mg_dl"] > GLUCOSE_MAX_BOUND)).sum())
    validation_report["checks"]["glucose_bounds"] = {
        "passed": (out_of_bounds == 0),
        "min_bound": GLUCOSE_MIN_BOUND,
        "max_bound": GLUCOSE_MAX_BOUND,
        "min_observed": min_observed_glucose,
        "max_observed": max_observed_glucose,
        "out_of_bounds_count": out_of_bounds
    }

    # Overall verdict
    all_passed = all(check["passed"] for check in validation_report["checks"].values())
    if not all_passed:
        validation_report["status"] = "FAILED"
        raise ValueError(f"Synthetic dataset validation failed: {validation_report}")

    return validation_report


def run_pipeline() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """
    Main orchestration routine:
    1. Ensures target directories exist.
    2. Generates patient profiles and time-series data deterministically.
    3. Validates datasets.
    4. Writes CSV artifacts.
    """
    DATA_RAW_DIR.mkdir(parents=True, exist_ok=True)
    DATA_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" TwinSense AI - Deterministic Synthetic Healthcare Data Generator")
    print("=" * 70)
    print(f"[*] Configuration: {NUM_PATIENTS} patients | {SIMULATION_DAYS} days | {INTERVAL_MINUTES}-min intervals")
    print(f"[*] Random Seed: {RANDOM_SEED}")
    print("[*] NOTICE: Purely synthetic development data. Not real clinical records.\n")

    # Step 1: Patient Profiles
    print("[1/4] Generating patient baseline profiles...")
    profiles_df = generate_patient_profiles(num_patients=NUM_PATIENTS, seed=RANDOM_SEED)

    # Step 2: Time-series Stream
    print("[2/4] Generating paired CGM and wearable time-series...")
    timeseries_df = generate_timeseries_data(
        patient_profiles=profiles_df,
        days=SIMULATION_DAYS,
        interval_min=INTERVAL_MINUTES,
        seed=RANDOM_SEED
    )

    # Step 3: Validation
    print("[3/4] Running data integrity and physiological bound validations...")
    report = validate_synthetic_datasets(profiles_df, timeseries_df)
    print("      -> Validation Status:", report["status"])
    for check_name, check_data in report["checks"].items():
        print(f"         - {check_name}: {'PASS' if check_data['passed'] else 'FAIL'}")

    # Step 4: Export CSVs
    profiles_csv_path = DATA_RAW_DIR / "patient_profiles.csv"
    timeseries_csv_path = DATA_RAW_DIR / "glucose_timeseries.csv"

    print(f"\n[4/4] Writing datasets to disk...")
    profiles_df.to_csv(profiles_csv_path, index=False)
    timeseries_df.to_csv(timeseries_csv_path, index=False)

    print(f"      [+] Saved: {profiles_csv_path} ({len(profiles_df)} rows)")
    print(f"      [+] Saved: {timeseries_csv_path} ({len(timeseries_df)} rows)")
    print("=" * 70)

    return profiles_df, timeseries_df, report


if __name__ == "__main__":
    profiles_df, timeseries_df, report = run_pipeline()

    print("\n--- SAMPLE: Patient Profiles (Top 3) ---")
    print(profiles_df.head(3).to_string(index=False))

    print("\n--- SAMPLE: Time-series CGM Readings (Top 5) ---")
    print(timeseries_df.head(5).to_string(index=False))
