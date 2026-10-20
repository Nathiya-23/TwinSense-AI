"""
TwinSense AI - Backend Business Logic & Data Services Layer
===========================================================

Coordinates between SQLite database and TwinEngine inference module.
Ensures zero duplication of feature engineering or ML prediction code.
"""

from pathlib import Path
import json
from datetime import datetime
from typing import Optional, List
import pandas as pd
from fastapi import HTTPException

from app.database import get_db_connection
from app.suggestions import get_suggestions_for_risk_class
from src.twin_engine import (
    predict_patient_risk,
    simulate_what_if,
    get_engine,
    UNSUPPORTED_HYPOGLYCEMIA_WARNING,
    CLINICAL_PROTOTYPE_DISCLAIMER,
    SAFETY_WARNING,
    UNRELIABLE_PREDICTION_MESSAGE,
    HYPOGLYCEMIA_UNSUPPORTED_STATEMENT
)



def get_all_patients(db_path: Optional[Path] = None) -> List[dict]:
    """
    Fetches all synthetic patients with their latest telemetry readings.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    query = """
        SELECT 
            p.patient_id,
            p.age,
            p.bmi,
            p.diabetes_type,
            p.baseline_hba1c,
            p.diabetes_duration_years,
            p.is_synthetic,
            r.latest_timestamp AS latest_reading_timestamp,
            r.latest_glucose AS latest_glucose_mg_dl
        FROM patients p
        LEFT JOIN (
            SELECT 
                patient_id, 
                MAX(timestamp) AS latest_timestamp,
                glucose_mg_dl AS latest_glucose
            FROM readings
            GROUP BY patient_id
        ) r ON p.patient_id = r.patient_id
        ORDER BY p.patient_id ASC
    """
    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_patient_profile(patient_id: str, db_path: Optional[Path] = None) -> dict:
    """
    Fetches a single patient profile by ID. Raises 404 if not found.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM patients WHERE patient_id = ?", (patient_id,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail=f"Patient '{patient_id}' not found in database.")

    return dict(row)


def get_recent_readings(patient_id: str, limit: int = 50, db_path: Optional[Path] = None) -> List[dict]:
    """
    Fetches the most recent timestamped readings for a patient in chronological order.
    """
    # Verify patient exists
    get_patient_profile(patient_id, db_path=db_path)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    # Query last `limit` readings, ordered ascending for time-series display
    query = """
        SELECT timestamp, glucose_mg_dl, heart_rate, steps, meal_event
        FROM (
            SELECT timestamp, glucose_mg_dl, heart_rate, steps, meal_event
            FROM readings
            WHERE patient_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        )
        ORDER BY timestamp ASC
    """
    cursor.execute(query, (patient_id, limit))
    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def predict_for_patient(
    patient_id: str,
    custom_readings: Optional[List[dict]] = None,
    db_path: Optional[Path] = None
) -> dict:
    """
    Executes TwinEngine risk prediction for a patient and logs result to SQLite history.
    """
    profile = get_patient_profile(patient_id, db_path=db_path)

    # 1. Prepare Telemetry DataFrame
    if custom_readings and len(custom_readings) > 0:
        readings_df = pd.DataFrame(custom_readings)
    else:
        # Fetch last 12 readings (1 hour of 5-min history) from SQLite
        raw_readings = get_recent_readings(patient_id, limit=12, db_path=db_path)
        if len(raw_readings) < 6:
            raise HTTPException(
                status_code=400,
                detail=f"{UNRELIABLE_PREDICTION_MESSAGE} (Patient has only {len(raw_readings)} readings. At least 6 readings required.)"
            )
        readings_df = pd.DataFrame(raw_readings)

    # 2. Execute TwinEngine Inference
    try:
        prediction_result = predict_patient_risk(profile, readings_df)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{UNRELIABLE_PREDICTION_MESSAGE} ({str(e)})")

    # 3. Log to SQLite predictions history
    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    now_iso = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO predictions (
            patient_id, prediction_timestamp, reading_timestamp, 
            predicted_target_timestamp, prediction_horizon_minutes, 
            current_glucose_mg_dl, predicted_risk_class, risk_label, 
            probabilities_json, contributing_factors_json, input_features_json, is_synthetic
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
    """, (
        patient_id,
        now_iso,
        prediction_result["current_timestamp"],
        prediction_result["predicted_target_timestamp"],
        prediction_result["prediction_horizon_minutes"],
        prediction_result["current_glucose_mg_dl"],
        prediction_result["predicted_risk_class"],
        prediction_result["risk_label"],
        json.dumps(prediction_result["class_probabilities"]),
        json.dumps(prediction_result["key_contributing_factors"]),
        json.dumps(prediction_result["input_features"])
    ))
    prediction_id = cursor.lastrowid
    conn.commit()
    conn.close()

    prediction_result["prediction_id"] = prediction_id
    prediction_result["patient_id"] = patient_id
    prediction_result["suggestions"] = get_suggestions_for_risk_class(
        prediction_result["predicted_risk_class"],
        current_glucose=prediction_result["current_glucose_mg_dl"],
        model_version=prediction_result.get("active_model_version")
    )
    return prediction_result


def get_prediction_history(patient_id: str, limit: int = 20, db_path: Optional[Path] = None) -> List[dict]:
    """
    Retrieves previous prediction history for a patient.
    """
    get_patient_profile(patient_id, db_path=db_path)

    conn = get_db_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT 
            id, patient_id, prediction_timestamp, reading_timestamp,
            predicted_target_timestamp, prediction_horizon_minutes,
            current_glucose_mg_dl, predicted_risk_class, risk_label,
            probabilities_json, contributing_factors_json
        FROM predictions
        WHERE patient_id = ?
        ORDER BY id DESC
        LIMIT ?
    """, (patient_id, limit))
    rows = cursor.fetchall()
    conn.close()

    history = []
    for r in rows:
        d = dict(r)
        d["probabilities"] = json.loads(d.pop("probabilities_json"))
        d["key_contributing_factors"] = json.loads(d.pop("contributing_factors_json"))
        history.append(d)

    return history


def what_if_for_patient(
    patient_id: str,
    hypothetical_delta_glucose: float,
    hypothetical_delta_steps: int,
    scenario_description: str,
    db_path: Optional[Path] = None
) -> dict:
    """
    Runs counterfactual what-if simulation using patient's latest readings from DB.
    """
    profile = get_patient_profile(patient_id, db_path=db_path)
    raw_readings = get_recent_readings(patient_id, limit=12, db_path=db_path)
    if len(raw_readings) < 6:
        raise HTTPException(
            status_code=400,
            detail=f"{UNRELIABLE_PREDICTION_MESSAGE} (Patient has only {len(raw_readings)} readings. At least 6 readings required.)"
        )

    readings_df = pd.DataFrame(raw_readings)

    try:
        what_if_res = simulate_what_if(
            baseline_profile=profile,
            recent_readings=readings_df,
            hypothetical_delta_glucose=hypothetical_delta_glucose,
            hypothetical_delta_steps=hypothetical_delta_steps,
            scenario_description=scenario_description
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"{UNRELIABLE_PREDICTION_MESSAGE} ({str(e)})")

    what_if_res["patient_id"] = patient_id
    return what_if_res
