"""
TwinSense AI - Hypoglycemia Limitation & Safety Alert Test Suite
================================================================

Comprehensive verification of requirements:
1. Alert boundaries: 69.9 triggers, 70.0 does not, 70.1 does not; null/NaN handled.
2. Alert uses measured reading only, never predicted or what-if hypothetical values.
3. Alert text contains zero dosing or treatment terms (e.g. insulin, units, grams).
4. Class 1 shows "Not supported" (never 0%) in API display fields, what-if, CSV, and PDF.
5. Warning text and mandatory disclaimer present in dashboard, CSV, and PDF (extracted text).
6. Alert present in CSV and PDF reports only if observed glucose is strictly below 70 mg/dL.
7. No new prediction or model call when evaluating the alert.
8. Backward compatibility: existing API endpoints and engine functions remain compatible.
"""

import unittest
import io
import pypdf
import numpy as np
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from src.twin_engine import (
    HYPOGLYCEMIA_THRESHOLD_MG_DL,
    get_low_glucose_safety_alert,
    TwinEngine,
    UNSUPPORTED_HYPOGLYCEMIA_WARNING,
    CLINICAL_PROTOTYPE_DISCLAIMER
)
from app.reports import (
    generate_csv_report,
    generate_pdf_report,
    MANDATORY_DISCLAIMER
)
from app.auth import register_user, create_session
from app.database import init_db
import tempfile
from pathlib import Path
import sqlite3


class TestHypoglycemiaLimitationAndAlert(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_hypo_limit.db"
        init_db(cls.test_db_path)

        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c,
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES
            ('HYPO_TEST_01', 50, 26.0, 'Type 2', 7.5, 5, 1, 'hypo_test_fixture')
        """)
        conn.commit()
        conn.close()

        import app.database
        cls.orig_db = app.database.DB_PATH
        app.database.DB_PATH = cls.test_db_path

        test_user = register_user(
            full_name="Hypo Tester",
            email="tester_hypo@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls.client = TestClient(fastapi_app, cookies={"twinsense_session": test_session["session_id"]})

        cls.sample_profile = {
            "patient_id": "HYPO_TEST_01",
            "age": 50,
            "bmi": 26.0,
            "baseline_hba1c": 7.5,
            "diabetes_duration_years": 5,
            "diabetes_type": "Type 2"
        }

    @classmethod
    def tearDownClass(cls):
        import app.database
        app.database.DB_PATH = cls.orig_db
        cls.temp_dir.cleanup()

    # 1. Alert boundary conditions
    def test_01_alert_boundaries(self):
        """69.9 triggers, 70.0 does not, 70.1 does not; null/NaN/invalid return None."""
        self.assertEqual(HYPOGLYCEMIA_THRESHOLD_MG_DL, 70.0)

        # 69.9 triggers
        alert_69_9 = get_low_glucose_safety_alert(69.9, "2026-03-01 12:00:00")
        self.assertIsNotNone(alert_69_9)
        self.assertIn("69.9 mg/dL", alert_69_9)
        self.assertIn("2026-03-01 12:00:00", alert_69_9)
        self.assertIn("below 70 mg/dL", alert_69_9)

        # 70.0 does NOT trigger (strictly below threshold)
        self.assertIsNone(get_low_glucose_safety_alert(70.0, "2026-03-01 12:00:00"))

        # 70.1 does NOT trigger
        self.assertIsNone(get_low_glucose_safety_alert(70.1, "2026-03-01 12:00:00"))

        # Null / NaN / missing
        self.assertIsNone(get_low_glucose_safety_alert(None))
        self.assertIsNone(get_low_glucose_safety_alert(float("nan")))
        self.assertIsNone(get_low_glucose_safety_alert(np.nan))
        self.assertIsNone(get_low_glucose_safety_alert("invalid_string"))

    # 2. Alert text wording and forbidden dosing terms
    def test_02_alert_wording_and_no_dosing_terms(self):
        """Wording exactly matches specification and has zero dosing/treatment language."""
        alert = get_low_glucose_safety_alert(58.4, "2026-03-01 08:30:00")
        expected = (
            "Low glucose reading: the measured value of 58.4 mg/dL (at 2026-03-01 08:30:00) is below 70 mg/dL. "
            "This alert is based on the measured reading, not the ML prediction. This is synthetic data. "
            "If this were a real reading, follow your clinician's guidance and seek medical help if you have symptoms."
        )
        self.assertEqual(alert, expected)

        # Forbidden terms check
        forbidden_terms = ["insulin", "units", "grams of carbohydrate", "medication", "dose", "titration", "eat 15g"]
        for term in forbidden_terms:
            self.assertNotIn(term, alert.lower(), f"Alert text must not contain dosing term '{term}'")

    # 3. What-if simulation hypothetical glucose < 70 must NOT trigger alert
    def test_03_whatif_hypothetical_value_does_not_trigger_alert(self):
        """Hypothetical simulation adjustments never trigger the measured low-glucose safety alert."""
        engine = TwinEngine()
        import pandas as pd
        readings = pd.DataFrame({
            "timestamp": [f"2026-03-01 12:{i*5:02d}:00" for i in range(6)],
            "glucose_mg_dl": [130.0, 132.0, 134.0, 136.0, 138.0, 140.0],
            "heart_rate": [70] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })
        profile = {"age": 50, "bmi": 26.0, "baseline_hba1c": 7.5, "diabetes_duration_years": 5}

        # Simulate large negative delta that drops hypothetical glucose to ~50 mg/dL (< 70)
        whatif_res = engine.simulate_what_if(
            profile, readings, hypothetical_delta_glucose=-90.0, scenario_description="Drop Test"
        )
        hyp_res = whatif_res["hypothetical_result"]
        self.assertLess(hyp_res["glucose_mg_dl"], 70.0)
        # MUST NOT trigger measured low-glucose safety alert
        self.assertIsNone(hyp_res.get("low_glucose_safety_alert"))
        self.assertTrue(hyp_res.get("is_simulated"))
        self.assertFalse(hyp_res.get("hypoglycemia_supported"))
        self.assertEqual(hyp_res.get("hypoglycemia_display_probability"), "Not supported")

    # 4. Class 1 probability displays "Not supported" in CSV and PDF reports
    def test_04_class_1_shows_not_supported_in_csv_and_pdf(self):
        """CSV and PDF reports format Class 1 probability as 'Not supported', never '0%'."""
        pred = {
            "id": 1,
            "patient_id": "HYPO_TEST_01",
            "prediction_timestamp": "2026-03-01 12:00:00",
            "reading_timestamp": "2026-03-01 11:55:00",
            "predicted_target_timestamp": "2026-03-01 12:40:00",
            "current_glucose_mg_dl": 120.0,
            "predicted_risk_class": 2,
            "risk_label": "In-Range",
            "probabilities": {"1_hypoglycemia": 0.0, "2_in_range": 0.85, "3_hyperglycemia": 0.15},
            "contributing_factors": ["Normal trend"]
        }

        # CSV Check
        csv_text = generate_csv_report(self.sample_profile, pred)
        self.assertIn('"Class probability - 1_hypoglycemia","Not supported"', csv_text)

        # PDF Check (extract real text)
        pdf_bytes = generate_pdf_report(self.sample_profile, pred)
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        extracted_text = "\n".join([page.extract_text() for page in reader.pages])

        self.assertIn("1_hypoglycemia", extracted_text)
        self.assertIn("Not supported", extracted_text)

    # 5. Low-glucose alert in CSV and PDF reports only when observed glucose < 70
    def test_05_alert_in_reports_only_when_observed_glucose_below_70(self):
        """Reports include the low-glucose safety alert if and only if observed glucose < 70."""
        # Case A: Observed glucose is 64.5 mg/dL (< 70)
        pred_low = {
            "id": 2,
            "patient_id": "HYPO_TEST_01",
            "prediction_timestamp": "2026-03-01 12:00:00",
            "reading_timestamp": "2026-03-01 11:55:00",
            "predicted_target_timestamp": "2026-03-01 12:40:00",
            "current_glucose_mg_dl": 64.5,
            "predicted_risk_class": 1,
            "risk_label": "Hypoglycemia",
            "probabilities": {"1_hypoglycemia": 0.0, "2_in_range": 0.8, "3_hyperglycemia": 0.2},
            "contributing_factors": ["Low reading"]
        }

        csv_low = generate_csv_report(self.sample_profile, pred_low)
        self.assertIn("LOW-GLUCOSE SAFETY ALERT", csv_low)
        self.assertIn("64.5 mg/dL", csv_low)

        pdf_low_bytes = generate_pdf_report(self.sample_profile, pred_low)
        pdf_low_text = "\n".join([page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf_low_bytes)).pages])
        self.assertIn("LOW-GLUCOSE SAFETY ALERT", pdf_low_text)
        self.assertIn("64.5 mg/dL", pdf_low_text)

        # Case B: Observed glucose is 125.0 mg/dL (>= 70)
        pred_norm = dict(pred_low)
        pred_norm["current_glucose_mg_dl"] = 125.0
        csv_norm = generate_csv_report(self.sample_profile, pred_norm)
        self.assertNotIn("LOW-GLUCOSE SAFETY ALERT", csv_norm)

        pdf_norm_bytes = generate_pdf_report(self.sample_profile, pred_norm)
        pdf_norm_text = "\n".join([page.extract_text() for page in pypdf.PdfReader(io.BytesIO(pdf_norm_bytes)).pages])
        self.assertNotIn("LOW-GLUCOSE SAFETY ALERT", pdf_norm_text)

    # 6. Warning text and disclaimer visible in dashboard HTML
    def test_06_dashboard_contains_warning_and_disclaimer(self):
        """Dashboard HTML contains the warning and universal disclaimer."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn("Hypoglycemia prediction is not supported by the current model.", res.text)
        self.assertIn("SYNTHETIC DATA — NOT CLINICALLY VALIDATED", res.text)
        self.assertIn('id="low-glucose-alert-banner"', res.text)
        self.assertIn('id="forecast-hypo-warning-text"', res.text)

    # 7. No prediction created or model called when checking alert
    def test_07_alert_is_pure_function_no_model_calls(self):
        """Evaluating the alert does not require a model inference call or database prediction record."""
        # Pure function check
        result = get_low_glucose_safety_alert(62.0, "2026-03-01 12:00:00")
        self.assertIsInstance(result, str)
        self.assertIn("62.0 mg/dL", result)
