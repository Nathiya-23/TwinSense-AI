"""
TwinSense AI - Safety, Reassurance Prevention, and Clinical Disclaimer Test Suite
==================================================================================

Validates:
1. Clear safety warnings near every prediction.
2. Prevention of false reassurance (no guarantees, distinct actual vs predicted, no treatment advice).
3. Unreliable prediction state on missing, invalid, outdated, or out-of-range data.
4. High and low glucose caution messages and emergency guidance.
5. Hypoglycemia limitation: zero training examples, no 0% proof, exact unsupported statement.
6. Latest reading reminder and staleness detection.
7. Honest educational prototype disclaimer.
8. Regression coverage confirming existing predictions, history, chart, and what-if remain functional.
"""

import unittest
from pathlib import Path
import tempfile
import sqlite3
from datetime import datetime, timedelta
import pandas as pd
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.database import init_db
import app.database
from app.auth import register_user, create_session
from src.twin_engine import (
    TwinEngine,
    SAFETY_WARNING,
    UNRELIABLE_PREDICTION_MESSAGE,
    HYPOGLYCEMIA_UNSUPPORTED_STATEMENT,
    UNSUPPORTED_HYPOGLYCEMIA_WARNING,
    CLINICAL_PROTOTYPE_DISCLAIMER,
    RISK_CLASS_MAP
)


class TestSafetyAndReliability(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.engine = TwinEngine()
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_safety.db"
        init_db(cls.test_db_path)

        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c,
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES
            ('SAFE_PAT_001', 48, 26.0, 'Type 2', 7.4, 5, 1, 'safety_test_fixture'),
            ('SAFE_PAT_002', 32, 22.5, 'Type 1', 8.0, 4, 1, 'safety_test_fixture')
        """)

        # 12 readings @ 5-min intervals
        base_dt = datetime(2026, 3, 1, 10, 0, 0)
        readings_rows = []
        for i in range(12):
            t_str = (base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
            readings_rows.append((
                'SAFE_PAT_001', t_str, 120.0 + (i * 2.0), 72, 10 + i, 0, 1, 'safety_test_fixture'
            ))
        cursor.executemany("""
            INSERT INTO readings (
                patient_id, timestamp, glucose_mg_dl, heart_rate,
                steps, meal_event, is_synthetic, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, readings_rows)

        conn.commit()
        conn.close()

        cls.orig_db = app.database.DB_PATH
        app.database.DB_PATH = cls.test_db_path

        # Create a test user and session so GET / doesn't redirect to login
        test_user = register_user(
            full_name="Safety Test User",
            email="testuser_safety@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls._test_session_id = test_session["session_id"]

        cls.client = TestClient(fastapi_app, cookies={"twinsense_session": cls._test_session_id})

    @classmethod
    def tearDownClass(cls):
        app.database.DB_PATH = cls.orig_db
        cls.temp_dir.cleanup()

    # -------------------------------------------------------------
    # 1. Clear Safety Warning
    # -------------------------------------------------------------
    def test_01_safety_warning_exact_text_in_engine_and_api(self):
        """Every prediction must return the exact mandatory safety warning."""
        expected_warning = (
            "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. "
            "Do not rely on this prediction alone for medical decisions."
        )
        self.assertEqual(SAFETY_WARNING, expected_warning)

        # In TwinEngine output
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)
        readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [130.0, 132.0, 134.0, 136.0, 138.0, 140.0],
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        engine_res = self.engine.predict_risk(profile, readings)
        self.assertIn("safety_warning", engine_res)
        self.assertEqual(engine_res["safety_warning"], expected_warning)

        # In API endpoint response
        api_res = self.client.post("/api/patients/SAFE_PAT_001/predict", json={})
        self.assertEqual(api_res.status_code, 201)
        data = api_res.json()
        self.assertIn("safety_warning", data)
        self.assertEqual(data["safety_warning"], expected_warning)

    def test_02_safety_warning_rendered_in_html_dashboard(self):
        """HTML dashboard must render the exact safety warning text."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(
            "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions.",
            res.text
        )

    # -------------------------------------------------------------
    # 2. Prevent False Reassurance
    # -------------------------------------------------------------
    def test_03_no_false_reassurance_guarantees(self):
        """No code or template may claim 'glucose will become normal' or guarantee recovery."""
        # Check twin_engine
        engine_code = Path("src/twin_engine.py").read_text(encoding="utf-8").lower()
        self.assertNotIn("will become normal", engine_code)
        self.assertNotIn("glucose will return to normal", engine_code)

        # Check HTML dashboard
        html_code = Path("app/static/index.html").read_text(encoding="utf-8").lower()
        self.assertNotIn("will become normal", html_code)

        # Verify Class 2 risk label uses predicted range trajectory
        self.assertIn("Predicted In-Range Trajectory", RISK_CLASS_MAP[2])

    def test_04_no_insulin_or_treatment_recommendations(self):
        """System must never recommend insulin doses, medication adjustments, or treatments."""
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)
        high_readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [220.0, 230.0, 240.0, 250.0, 260.0, 275.0],
            "heart_rate": [80] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res = self.engine.predict_risk(profile, high_readings)
        for factor in res["key_contributing_factors"]:
            factor_lower = factor.lower()
            self.assertNotIn("inject", factor_lower)
            self.assertNotIn("insulin dose", factor_lower)
            self.assertNotIn("take medication", factor_lower)
            self.assertNotIn("titrate", factor_lower)

    # -------------------------------------------------------------
    # 3. Unreliable Prediction State
    # -------------------------------------------------------------
    def test_05_unreliable_prediction_message_on_insufficient_history(self):
        """Insufficient readings (<6) must return the required unreliable prediction message."""
        expected_msg = "Unable to provide a reliable prediction. Check the latest glucose reading and seek appropriate medical guidance."
        self.assertEqual(UNRELIABLE_PREDICTION_MESSAGE, expected_msg)

        short_readings = [
            {"timestamp": "2026-03-01 12:00:00", "glucose_mg_dl": 140.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:05:00", "glucose_mg_dl": 142.0, "heart_rate": 70, "steps": 10, "meal_event": 0}
        ]
        res = self.client.post("/api/patients/SAFE_PAT_001/predict", json={"readings": short_readings})
        self.assertEqual(res.status_code, 422)
        detail = res.json()["detail"]
        self.assertIn(expected_msg, detail)
        self.assertIn("Insufficient reading history", detail)

    def test_06_unreliable_prediction_on_out_of_bounds_telemetry(self):
        """Readings outside supported bounds (<30 or >500 mg/dL) and non-chronological readings trigger unreliable errors."""
        expected_msg = "Unable to provide a reliable prediction. Check the latest glucose reading and seek appropriate medical guidance."

        # Engine level: out-of-bounds glucose (<30 or >500)
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)
        oob_readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [140.0, 142.0, 145.0, 150.0, 155.0, 650.0],  # 650 is > 500
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(profile, oob_readings)
        self.assertIn("allowable bounds (30-500 mg/dL)", str(ctx.exception))

        # API level: Disordered timestamps trigger 422 with UNRELIABLE_PREDICTION_MESSAGE
        disordered_readings = [
            {"timestamp": "2026-03-01 12:25:00", "glucose_mg_dl": 140.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:05:00", "glucose_mg_dl": 142.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:10:00", "glucose_mg_dl": 144.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:15:00", "glucose_mg_dl": 146.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:20:00", "glucose_mg_dl": 148.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:00:00", "glucose_mg_dl": 150.0, "heart_rate": 70, "steps": 10, "meal_event": 0}
        ]
        res = self.client.post("/api/patients/SAFE_PAT_001/predict", json={"readings": disordered_readings})
        self.assertEqual(res.status_code, 422)
        detail = res.json()["detail"]
        self.assertIn(expected_msg, detail)
        self.assertIn("chronological order", detail)


    def test_07_unreliable_state_container_in_dashboard(self):
        """Dashboard must contain the dedicated unreliable prediction state container."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn('id="prediction-unreliable-state"', res.text)
        self.assertIn(
            "Unable to provide a reliable prediction. Check the latest glucose reading and seek appropriate medical guidance.",
            res.text
        )

    # -------------------------------------------------------------
    # 4. Handle High and Low Glucose Carefully
    # -------------------------------------------------------------
    def test_08_out_of_target_glucose_triggers_caution(self):
        """Current reading outside 70-180 mg/dL triggers caution message and in_target=False."""
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)

        # High glucose reading (>180)
        high_readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [170.0, 175.0, 180.0, 185.0, 190.0, 210.0],
            "heart_rate": [75] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res_high = self.engine.predict_risk(profile, high_readings)
        self.assertFalse(res_high["is_current_glucose_in_target"])
        self.assertIsNotNone(res_high["current_glucose_caution"])
        self.assertIn("above the configured target range", res_high["current_glucose_caution"])
        self.assertIn("A reassuring AI forecast does NOT override", res_high["current_glucose_caution"])

        # In-range reading (120)
        norm_readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [115.0, 118.0, 120.0, 122.0, 120.0, 120.0],
            "heart_rate": [75] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res_norm = self.engine.predict_risk(profile, norm_readings)
        self.assertTrue(res_norm["is_current_glucose_in_target"])
        self.assertIsNone(res_norm["current_glucose_caution"])

    def test_09_severe_symptoms_emergency_protocol_visible(self):
        """Dashboard must contain immediate emergency instructions for acute symptoms."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("SEEK EMERGENCY MEDICAL HELP IMMEDIATELY", res.text)
        self.assertIn("Never allow a reassuring AI result to override dangerous symptoms", res.text)

    # -------------------------------------------------------------
    # 5. Fix Hypoglycemia Limitation
    # -------------------------------------------------------------
    def test_10_hypoglycemia_limitation_exact_statement(self):
        """Must state 'Hypoglycemia prediction is not supported by the current model.'"""
        expected_statement = "Hypoglycemia prediction is not supported by the current model."
        self.assertEqual(HYPOGLYCEMIA_UNSUPPORTED_STATEMENT, expected_statement)

        # In engine output
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)
        readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [130.0, 132.0, 134.0, 136.0, 138.0, 140.0],
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res = self.engine.predict_risk(profile, readings)
        self.assertEqual(res["hypoglycemia_message"], expected_statement)
        self.assertIn("ZERO training support for Class 1", res["hypoglycemia_limitation"])
        self.assertIn("A 0% model output must never be interpreted as evidence that hypoglycemia cannot happen", res["hypoglycemia_limitation"])

        # In HTML dashboard
        html_res = self.client.get("/")
        self.assertIn(expected_statement, html_res.text)

    # -------------------------------------------------------------
    # 6. Latest Reading Reminder & Staleness
    # -------------------------------------------------------------
    def test_11_latest_reading_reminder_and_staleness_flag(self):
        """Telemetry gaps > 15 minutes are detected and marked as stale."""
        profile = {"age": 50, "bmi": 27.0, "baseline_hba1c": 7.0, "diabetes_duration_years": 5}
        base_t = datetime(2026, 3, 1, 12, 0, 0)

        # Standard 5-min intervals (not stale)
        fresh_readings = pd.DataFrame({
            "timestamp": [(base_t + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [140.0] * 6,
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res_fresh = self.engine.predict_risk(profile, fresh_readings)
        self.assertFalse(res_fresh["is_stale"])

        # 30-min gap between reading 4 and 5 (stale)
        stale_timestamps = [
            "2026-03-01 12:00:00",
            "2026-03-01 12:05:00",
            "2026-03-01 12:10:00",
            "2026-03-01 12:15:00",
            "2026-03-01 12:20:00",
            "2026-03-01 13:00:00"  # 40-minute gap
        ]
        stale_readings = pd.DataFrame({
            "timestamp": stale_timestamps,
            "glucose_mg_dl": [140.0] * 6,
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        res_stale = self.engine.predict_risk(profile, stale_readings)
        self.assertTrue(res_stale["is_stale"])

    # -------------------------------------------------------------
    # 7. Keep Project Honest: Prototype Disclaimer
    # -------------------------------------------------------------
    def test_12_honest_prototype_disclaimer_rendered(self):
        """The exact disclaimer must appear in dashboard and engine output."""
        expected_disclaimer = (
            "TwinSense AI is an educational prototype using synthetic data. "
            "It has not been clinically validated and is not intended for diagnosis, treatment, or emergency monitoring."
        )
        self.assertIn(expected_disclaimer, CLINICAL_PROTOTYPE_DISCLAIMER)

        html_res = self.client.get("/")
        self.assertIn(expected_disclaimer, html_res.text)

    # -------------------------------------------------------------
    # 8. Regression: Existing Features Still Work
    # -------------------------------------------------------------
    def test_13_existing_prediction_and_history_work(self):
        """Prediction logging and history retrieval operate normally."""
        pred_res = self.client.post("/api/patients/SAFE_PAT_001/predict", json={})
        self.assertEqual(pred_res.status_code, 201)
        pred_data = pred_res.json()
        self.assertEqual(pred_data["patient_id"], "SAFE_PAT_001")
        self.assertIn("prediction_id", pred_data)

        hist_res = self.client.get("/api/patients/SAFE_PAT_001/predictions")
        self.assertEqual(hist_res.status_code, 200)
        hist_data = hist_res.json()
        self.assertTrue(hist_data["count"] >= 1)

    def test_14_existing_what_if_simulation_works(self):
        """What-if sensitivity simulation functions without mutating records."""
        payload = {
            "hypothetical_delta_glucose": -15.0,
            "hypothetical_delta_steps": 250,
            "scenario_description": "Post-Meal Stroll"
        }
        res = self.client.post("/api/patients/SAFE_PAT_001/what-if", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data["is_hypothetical_simulation"])
        self.assertIn("observed_result", data)
        self.assertIn("hypothetical_result", data)
        self.assertIn("safety_warning", data)
        self.assertIn("hypoglycemia_message", data)


if __name__ == "__main__":
    unittest.main()
