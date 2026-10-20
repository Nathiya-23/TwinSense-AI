"""
TwinSense AI - SQLite Database Initialization & Access Layer
============================================================

Manages local SQLite database for:
1. Patient baseline profiles (EHR-style)
2. Timestamped CGM & wearable telemetry
3. Digital Twin prediction history

Guarantees idempotent population from existing synthetic CSV files.
"""

from pathlib import Path
from typing import Optional
import sqlite3
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "twinsense.db"

PROFILES_CSV = RAW_DATA_DIR / "patient_profiles.csv"
TIMESERIES_CSV = RAW_DATA_DIR / "glucose_timeseries.csv"


def get_db_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """
    Returns an open SQLite database connection with row factory enabled.
    Dynamically checks the active DB_PATH if db_path is None.
    """
    target_path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(str(target_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """
    Creates tables and indices if they do not exist.
    """
    target_path = db_path if db_path is not None else DB_PATH
    target_path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_db_connection(target_path)
    cursor = conn.cursor()

    # 1. Patients Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS patients (
            patient_id TEXT PRIMARY KEY,
            age INTEGER NOT NULL,
            bmi REAL NOT NULL,
            diabetes_type TEXT NOT NULL,
            baseline_hba1c REAL NOT NULL,
            diabetes_duration_years INTEGER NOT NULL,
            is_synthetic INTEGER DEFAULT 1,
            data_source TEXT NOT NULL
        )
    """)

    # 2. Readings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            glucose_mg_dl REAL NOT NULL,
            heart_rate INTEGER NOT NULL,
            steps INTEGER NOT NULL,
            meal_event INTEGER NOT NULL,
            is_synthetic INTEGER DEFAULT 1,
            data_source TEXT NOT NULL,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
            UNIQUE(patient_id, timestamp)
        )
    """)

    # Index for fast retrieval of latest readings by patient
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_readings_patient_timestamp 
        ON readings (patient_id, timestamp DESC)
    """)

    # 3. Prediction History Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL,
            prediction_timestamp TEXT NOT NULL,
            reading_timestamp TEXT NOT NULL,
            predicted_target_timestamp TEXT NOT NULL,
            prediction_horizon_minutes INTEGER DEFAULT 45,
            current_glucose_mg_dl REAL NOT NULL,
            predicted_risk_class INTEGER NOT NULL,
            risk_label TEXT NOT NULL,
            probabilities_json TEXT NOT NULL,
            contributing_factors_json TEXT NOT NULL,
            input_features_json TEXT NOT NULL,
            is_synthetic INTEGER DEFAULT 1,
            FOREIGN KEY (patient_id) REFERENCES patients(patient_id)
        )
    """)

    # 4. Users Table (Secure Authentication)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL COLLATE NOCASE,
            full_name TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)

    # 5. Sessions Table (Server-Managed Sessions & CSRF Protection)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            csrf_token TEXT NOT NULL,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_expires_at 
        ON sessions (expires_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_users_email 
        ON users (email)
    """)

    conn.commit()
    conn.close()


def populate_from_csv_if_empty(
    db_path: Optional[Path] = None,
    profiles_csv: Path = PROFILES_CSV,
    timeseries_csv: Path = TIMESERIES_CSV
) -> dict:
    """
    Safely populates SQLite database from existing raw CSV files.
    IDEMPOTENT: Uses INSERT OR IGNORE and checks existing records.
    Never duplicates data and never alters raw CSV files.
    """
    target_path = db_path if db_path is not None else DB_PATH
    init_db(target_path)
    conn = get_db_connection(target_path)
    cursor = conn.cursor()

    result = {"patients_inserted": 0, "readings_inserted": 0}

    # Populate Patients
    if profiles_csv.exists():
        profiles_df = pd.read_csv(profiles_csv)
        cursor.execute("SELECT COUNT(*) FROM patients")
        existing_patients = cursor.fetchone()[0]

        if existing_patients < len(profiles_df):
            records = profiles_df.to_dict(orient="records")
            cursor.executemany("""
                INSERT OR IGNORE INTO patients (
                    patient_id, age, bmi, diabetes_type, baseline_hba1c, 
                    diabetes_duration_years, is_synthetic, data_source
                ) VALUES (
                    :patient_id, :age, :bmi, :diabetes_type, :baseline_hba1c, 
                    :diabetes_duration_years, :is_synthetic, :data_source
                )
            """, records)
            result["patients_inserted"] = cursor.rowcount
            conn.commit()

    # Populate Readings
    if timeseries_csv.exists():
        cursor.execute("SELECT COUNT(*) FROM readings")
        existing_readings = cursor.fetchone()[0]

        # Only insert if table has fewer readings than the CSV
        if existing_readings == 0:
            timeseries_df = pd.read_csv(timeseries_csv)
            records = timeseries_df.to_dict(orient="records")
            cursor.executemany("""
                INSERT OR IGNORE INTO readings (
                    patient_id, timestamp, glucose_mg_dl, heart_rate, 
                    steps, meal_event, is_synthetic, data_source
                ) VALUES (
                    :patient_id, :timestamp, :glucose_mg_dl, :heart_rate, 
                    :steps, :meal_event, :is_synthetic, :data_source
                )
            """, records)
            result["readings_inserted"] = cursor.rowcount
            conn.commit()

    conn.close()
    return result


if __name__ == "__main__":
    print("[*] Initializing SQLite database...")
    init_db()
    res = populate_from_csv_if_empty()
    print(f"[+] DB initialized at: {DB_PATH}")
    print(f"[+] Records inserted: {res}")
