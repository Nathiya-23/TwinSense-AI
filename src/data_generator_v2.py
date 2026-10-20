"""
TwinSense AI - Synthetic Data Generator v2 (Hypoglycemia-Extended)
==================================================================

ETHICAL & CLINICAL DISCLAIMER:
This module generates ARTIFICIAL, SYNTHETIC data strictly for software
prototyping and ML development. It does NOT represent real patient health
records. Not for clinical use.

WHAT IS NEW vs v1:
------------------
1. Dedicated hypoglycemia episode injection per patient per day using the
   project-defined threshold (future glucose < 70 mg/dL).
2. Episodes are triggered by simulated insulin over-bolusing and
   extended physical exertion, causing acute downward glucose perturbations.
3. Fixed random seed (RANDOM_SEED_V2 = 99) for determinism.
4. All output written to data/synthetic_v2/ (original v1 files untouched).
5. data_source label: synthetic_simulation_twin_v2
"""

import os
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

# ---------------------------------------------------------
# Configuration Constants
# ---------------------------------------------------------
RANDOM_SEED_V2 = 99
NUM_PATIENTS = 10
SIMULATION_DAYS = 7
INTERVAL_MINUTES = 5

GLUCOSE_MIN_BOUND = 40.0
GLUCOSE_MAX_BOUND = 400.0

# Class thresholds (must match feature_engineering.py exactly)
HYPOGLYCEMIA_THRESHOLD = 70.0   # < 70 => Class 1
IN_RANGE_UPPER = 180.0          # <= 180 => Class 2, else Class 3

# Hypoglycemia episode parameters
HYPO_EPISODES_PER_PATIENT_PER_DAY = 2.5   # avg episodes per patient per day (ensures val/test have Class 1)
HYPO_EPISODE_DURATION_STEPS = 18          # ~90 min of suppressed glucose
HYPO_NADIR_MG_DL = 52.0                  # target nadir during episode

# Directories
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_V2_DIR = PROJECT_ROOT / "data" / "synthetic_v2"


def generate_patient_profiles_v2(num_patients: int = NUM_PATIENTS, seed: int = RANDOM_SEED_V2) -> pd.DataFrame:
    """
    Generate v2 synthetic patient profiles.
    Same distribution as v1 but with different seed and data_source label.
    """
    rng = np.random.default_rng(seed)

    patient_ids = [f"SYNTH_PAT_{i+1:03d}" for i in range(num_patients)]
    ages = rng.integers(24, 76, size=num_patients)
    bmis = np.round(rng.normal(loc=28.5, scale=4.8, size=num_patients).clip(19.0, 44.0), 1)
    diabetes_types = rng.choice(["Type 1", "Type 2"], size=num_patients, p=[0.35, 0.65])
    baseline_hba1c = np.round(rng.normal(loc=7.6, scale=1.1, size=num_patients).clip(5.7, 12.0), 1)

    durations = []
    for i in range(num_patients):
        max_duration = max(1, ages[i] - 18)
        dur = int(rng.integers(1, min(35, max_duration) + 1))
        durations.append(dur)

    return pd.DataFrame({
        "patient_id": patient_ids,
        "age": ages,
        "bmi": bmis,
        "diabetes_type": diabetes_types,
        "baseline_hba1c": baseline_hba1c,
        "diabetes_duration_years": durations,
        "is_synthetic": True,
        "data_source": "synthetic_simulation_twin_v2"
    })


def _simulate_patient_v2(
    patient_id: str,
    baseline_hba1c: float,
    diabetes_type: str,
    start_time: datetime,
    total_steps: int,
    rng: np.random.Generator
) -> pd.DataFrame:
    """
    Simulate single-patient v2 CGM + wearables with deliberate hypoglycemia episodes.

    Episodes are injected by:
      a) Simulated insulin over-bolusing: sudden glucose suppression effect
         applied at random daytime steps, causing a slow nadir descent.
      b) Extreme prolonged exercise: steps spike, glucose drops sharply.

    The suppression wears off naturally via the AR(1) process returning to resting.
    """
    resting_glucose = 28.7 * baseline_hba1c - 46.7
    resting_glucose = float(np.clip(resting_glucose, 100.0, 240.0))

    timestamps = []
    glucose_readings = []
    heart_rates = []
    steps_list = []
    meal_events = []

    current_glucose = resting_glucose + rng.normal(0, 5)
    postprandial_surge = 0.0
    hypo_suppression = 0.0       # Additional downward pull during episode
    hypo_remaining_steps = 0     # Countdown for active episode

    # Decide which steps will trigger a hypo episode
    total_days = SIMULATION_DAYS
    n_episodes = rng.poisson(lam=HYPO_EPISODES_PER_PATIENT_PER_DAY * total_days)
    episode_trigger_steps = set()
    steps_per_day = int(24 * 60 / INTERVAL_MINUTES)
    for _ in range(n_episodes):
        # Inject in daytime hours (9am-3pm), avoiding first/last 20 steps
        day = int(rng.integers(0, total_days))
        hour_offset = int(rng.integers(9 * 12, 15 * 12))  # 9:00 to 15:00 in 5-min steps
        trig_step = day * steps_per_day + hour_offset
        if 20 <= trig_step < total_steps - HYPO_EPISODE_DURATION_STEPS:
            episode_trigger_steps.add(trig_step)

    current_dt = start_time

    for step in range(total_steps):
        hour = current_dt.hour
        minute = current_dt.minute
        time_fraction = hour + minute / 60.0

        # Meal events (same as v1)
        is_meal = 0
        if minute == 0 and hour in [8, 13, 19]:
            is_meal = 1
            surge_mag = rng.uniform(45.0, 95.0) if diabetes_type == "Type 1" else rng.uniform(30.0, 70.0)
            postprandial_surge += surge_mag
        elif minute == 30 and hour == 16 and rng.random() < 0.5:
            is_meal = 1
            postprandial_surge += rng.uniform(20.0, 40.0)

        postprandial_surge *= 0.92

        # Activity
        if 23 <= hour or hour < 7:
            step_count = int(rng.poisson(lam=1.5))
            hr = int(rng.normal(62, 3))
            activity_drop = 0.0
        else:
            if rng.random() < 0.08:
                step_count = int(rng.uniform(150, 450))
                hr = int(rng.normal(108, 10))
                activity_drop = step_count * 0.025
            else:
                step_count = int(rng.uniform(5, 50))
                hr = int(rng.normal(74, 5))
                activity_drop = step_count * 0.005

        # Circadian
        circadian_drift = 12.0 * np.sin(2 * np.pi * (time_fraction - 6.0) / 24.0)
        if 4 <= hour <= 7:
            circadian_drift += 15.0

        # Hypoglycemia episode trigger
        if step in episode_trigger_steps:
            hypo_remaining_steps = HYPO_EPISODE_DURATION_STEPS
            hypo_suppression = resting_glucose - HYPO_NADIR_MG_DL + rng.uniform(-5, 5)

        if hypo_remaining_steps > 0:
            # Gradual suppression: subtract a fraction each step
            episode_progress = 1.0 - (hypo_remaining_steps / HYPO_EPISODE_DURATION_STEPS)
            # Bell-shape suppression: strongest at midpoint
            bell = np.sin(np.pi * episode_progress)
            extra_drop = hypo_suppression * bell * 1.3
            activity_drop += max(0, extra_drop)
            hypo_remaining_steps -= 1

        # AR(1) update
        target = resting_glucose + circadian_drift + postprandial_surge - activity_drop
        alpha = 0.88
        stochastic_noise = rng.normal(0, 3.2)
        current_glucose = alpha * current_glucose + (1.0 - alpha) * target + stochastic_noise
        current_glucose = float(np.clip(current_glucose, GLUCOSE_MIN_BOUND, GLUCOSE_MAX_BOUND))

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
        "data_source": "synthetic_simulation_twin_v2"
    })


def generate_timeseries_v2(
    patient_profiles: pd.DataFrame,
    days: int = SIMULATION_DAYS,
    interval_min: int = INTERVAL_MINUTES,
    seed: int = RANDOM_SEED_V2
) -> pd.DataFrame:
    """Generate v2 time-series for all patients."""
    total_steps_per_patient = int((days * 24 * 60) / interval_min)
    base_start_time = datetime(2026, 3, 1, 0, 0, 0)

    all_series = []
    for idx, row in patient_profiles.iterrows():
        patient_seed = seed + int(idx) * 1013
        p_rng = np.random.default_rng(patient_seed)
        p_df = _simulate_patient_v2(
            patient_id=row["patient_id"],
            baseline_hba1c=float(row["baseline_hba1c"]),
            diabetes_type=str(row["diabetes_type"]),
            start_time=base_start_time,
            total_steps=total_steps_per_patient,
            rng=p_rng
        )
        all_series.append(p_df)

    return pd.concat(all_series, ignore_index=True)


def generate_synthetic_data_v2(
    num_patients: int = NUM_PATIENTS,
    days_per_patient: int = SIMULATION_DAYS,
    seed: int = RANDOM_SEED_V2
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Generate synthetic data v2 deterministically given a seed.
    Returns (profiles_df, timeseries_df).
    """
    profiles = generate_patient_profiles_v2(num_patients=num_patients, seed=seed)
    timeseries = generate_timeseries_v2(profiles, days=days_per_patient, seed=seed)
    return profiles, timeseries


def run_pipeline_v2() -> tuple:
    """
    Main orchestration for v2 synthetic data generation.
    Writes to data/synthetic_v2/ (never overwrites v1 data).
    Returns (profiles_df, timeseries_df).
    """
    DATA_V2_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 70)
    print(" TwinSense AI v2 - Hypoglycemia-Extended Synthetic Data Generator")
    print("=" * 70)
    print(f"[*] Random Seed v2: {RANDOM_SEED_V2}")
    print(f"[*] Hypo episodes per patient per day: {HYPO_EPISODES_PER_PATIENT_PER_DAY}")
    print("[*] NOTICE: Purely synthetic development data. Not real clinical records.\n")

    profiles_df = generate_patient_profiles_v2()
    timeseries_df = generate_timeseries_v2(profiles_df)

    profiles_path = DATA_V2_DIR / "patient_profiles_v2.csv"
    timeseries_path = DATA_V2_DIR / "glucose_timeseries_v2.csv"

    profiles_df.to_csv(profiles_path, index=False)
    timeseries_df.to_csv(timeseries_path, index=False)

    print(f"[+] Saved profiles: {profiles_path} ({len(profiles_df)} rows)")
    print(f"[+] Saved timeseries: {timeseries_path} ({len(timeseries_df)} rows)")
    print("=" * 70)

    return profiles_df, timeseries_df


if __name__ == "__main__":
    profiles_df, timeseries_df = run_pipeline_v2()
    print("\n--- v2 Glucose min/max ---")
    print(f"  Min: {timeseries_df['glucose_mg_dl'].min():.1f}  Max: {timeseries_df['glucose_mg_dl'].max():.1f}")
