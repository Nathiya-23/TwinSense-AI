"""
TwinSense AI - API Integration & Route Test Suite
=================================================

Tests FastAPI endpoints using a temporary isolated SQLite database.
Guarantees zero modifications to production `data/twinsense.db`.
Uses synthetic fixtures only.
"""

import unittest
from pathlib import Path
import tempfile
import sqlite3
import json
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.database import init_db
import app.database
from app.auth import register_user, authenticate_user, create_session


class TestTwinSenseAPI(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Create an isolated temporary SQLite database for testing
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_twinsense.db"

        # Initialize schema in test DB
        init_db(cls.test_db_path)

        # Seed isolated test database with synthetic fixtures
        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()

        # Insert 2 test synthetic patients
        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c, 
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES 
            ('SYNTH_PAT_001', 52, 27.5, 'Type 2', 7.8, 8, 1, 'synthetic_test_fixture'),
            ('SYNTH_PAT_002', 30, 23.1, 'Type 1', 8.2, 5, 1, 'synthetic_test_fixture')
        """)

        # Insert 12 timestamped readings for SYNTH_PAT_001 (1 hour of 5-min readings)
        base_dt = datetime(2026, 3, 1, 12, 0, 0)
        readings_rows = []
        for i in range(12):
            t_str = (base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
            readings_rows.append((
                'SYNTH_PAT_001', t_str, 140.0 + (i * 2.0), 72 + i, 15 + (i * 5), 0, 1, 'synthetic_test_fixture'
            ))

        cursor.executemany("""
            INSERT INTO readings (
                patient_id, timestamp, glucose_mg_dl, heart_rate, 
                steps, meal_event, is_synthetic, data_source
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, readings_rows)

        conn.commit()
        conn.close()

        # Patch DB_PATH in database module to use test_db_path
        cls.orig_database_db = app.database.DB_PATH
        app.database.DB_PATH = cls.test_db_path

        # Create a test user and session so auth-protected routes work
        test_user = register_user(
            full_name="Test User",
            email="testuser_api@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls._test_session_id = test_session["session_id"]
        cls._test_csrf_token = test_session["csrf_token"]

        cls.client = TestClient(fastapi_app, cookies={"twinsense_session": cls._test_session_id})

    @classmethod
    def tearDownClass(cls):
        # Restore original path and cleanup temp dir
        app.database.DB_PATH = cls.orig_database_db
        cls.temp_dir.cleanup()

    def test_01_health_status_endpoint(self):
        """GET /api/health returns 200, status HEALTHY, and model loaded."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "HEALTHY")
        self.assertTrue(data["model_loaded"])
        self.assertTrue(data["database_connected"])
        self.assertEqual(data["total_patients"], 2)
        self.assertEqual(data["total_readings"], 12)
        self.assertIn("CRITICAL LIMITATION", data["hypoglycemia_limitation"])
        self.assertIn("FOR DEMONSTRATION ONLY", data["clinical_disclaimer"])

    def test_02_list_patients(self):
        """GET /api/patients lists available synthetic patients."""
        response = self.client.get("/api/patients")
        self.assertEqual(response.status_code, 200)
        patients = response.json()
        self.assertEqual(len(patients), 2)
        p_ids = [p["patient_id"] for p in patients]
        self.assertIn("SYNTH_PAT_001", p_ids)
        self.assertIn("SYNTH_PAT_002", p_ids)

    def test_03_get_patient_profile_valid(self):
        """GET /api/patients/{id} returns profile for existing patient."""
        response = self.client.get("/api/patients/SYNTH_PAT_001")
        self.assertEqual(response.status_code, 200)
        profile = response.json()
        self.assertEqual(profile["patient_id"], "SYNTH_PAT_001")
        self.assertEqual(profile["age"], 52)
        self.assertEqual(profile["baseline_hba1c"], 7.8)
        self.assertTrue(profile["is_synthetic"])

    def test_04_get_patient_profile_not_found(self):
        """GET /api/patients/{id} returns 404 for missing patient."""
        response = self.client.get("/api/patients/NON_EXISTENT_PATIENT")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_05_get_patient_readings(self):
        """GET /api/patients/{id}/readings returns chronological readings."""
        response = self.client.get("/api/patients/SYNTH_PAT_001/readings?limit=10")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["patient_id"], "SYNTH_PAT_001")
        self.assertEqual(len(data["readings"]), 10)
        self.assertTrue(data["is_synthetic"])

    def test_06_predict_from_db_readings(self):
        """POST /api/patients/{id}/predict calculates prediction and logs to history."""
        response = self.client.post("/api/patients/SYNTH_PAT_001/predict", json={})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertEqual(data["patient_id"], "SYNTH_PAT_001")
        self.assertIn(data["predicted_risk_class"], [2, 3])
        self.assertEqual(data["prediction_horizon_minutes"], 45)
        self.assertTrue(len(data["key_contributing_factors"]) >= 4)
        self.assertIn("CRITICAL LIMITATION", data["hypoglycemia_limitation"])
        self.assertIn("prediction_id", data)

    def test_07_prediction_history_retrieval(self):
        """GET /api/patients/{id}/predictions retrieves logged predictions."""
        response = self.client.get("/api/patients/SYNTH_PAT_001/predictions")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["patient_id"], "SYNTH_PAT_001")
        self.assertTrue(data["count"] >= 1)
        latest_pred = data["predictions"][0]
        self.assertIn("predicted_risk_class", latest_pred)
        self.assertIn("key_contributing_factors", latest_pred)

    def test_08_predict_insufficient_custom_readings_rejected(self):
        """POST /api/patients/{id}/predict with fewer than 6 readings returns 422."""
        short_readings = [
            {"timestamp": "2026-03-01 12:00:00", "glucose_mg_dl": 140.0, "heart_rate": 70, "steps": 10, "meal_event": 0},
            {"timestamp": "2026-03-01 12:05:00", "glucose_mg_dl": 142.0, "heart_rate": 70, "steps": 10, "meal_event": 0}
        ]
        response = self.client.post("/api/patients/SYNTH_PAT_001/predict", json={"readings": short_readings})
        self.assertEqual(response.status_code, 422)
        self.assertIn("Insufficient reading history", response.json()["detail"])

    def test_09_what_if_simulation_valid(self):
        """POST /api/patients/{id}/what-if executes counterfactual comparison."""
        payload = {
            "hypothetical_delta_glucose": -20.0,
            "hypothetical_delta_steps": 350,
            "scenario_description": "Post-Dinner Brisk Walk"
        }
        response = self.client.post("/api/patients/SYNTH_PAT_001/what-if", json=payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["patient_id"], "SYNTH_PAT_001")
        self.assertTrue(data["is_hypothetical_simulation"])
        self.assertIn("observed_result", data)
        self.assertIn("hypothetical_result", data)
        self.assertIn("HYPOTHETICAL SIMULATION NOTICE", data["simulation_notice"])
        self.assertIn("CRITICAL LIMITATION", data["hypoglycemia_limitation"])

    def test_10_what_if_invalid_delta_bounds_rejected(self):
        """POST /api/patients/{id}/what-if with out-of-bound delta is rejected by Pydantic."""
        payload = {
            "hypothetical_delta_glucose": 999.0,  # Exceeds le=150.0 bound
            "hypothetical_delta_steps": 200,
            "scenario_description": "Extreme Delta"
        }
        response = self.client.post("/api/patients/SYNTH_PAT_001/what-if", json=payload)
        self.assertEqual(response.status_code, 422)

    def test_11_serve_dashboard_root(self):
        """GET / serves the TwinSense AI index.html dashboard."""
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers.get("content-type", ""))
        self.assertIn("TwinSense AI", response.text)
        self.assertIn("Healthcare Digital Twin", response.text)

    def test_12_static_assets_reachable(self):
        """GET /static/style.css and /static/app.js return 200."""
        css_res = self.client.get("/static/style.css")
        self.assertEqual(css_res.status_code, 200)
        self.assertIn("TwinSense AI", css_res.text)

        js_res = self.client.get("/static/app.js")
        self.assertEqual(js_res.status_code, 200)
        self.assertIn("TwinSense AI", js_res.text)



if __name__ == "__main__":
    unittest.main()


class TestReportDownloadEndpoints(unittest.TestCase):
    """
    Tests for CSV and PDF prediction report download endpoints.
    Runs against its own isolated test SQLite database.
    A prediction is seeded in setUpClass before download tests run.
    """

    @classmethod
    def setUpClass(cls):
        import tempfile
        import sqlite3
        from datetime import datetime, timedelta

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "report_test.db"

        init_db(cls.test_db_path)

        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c,
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES ('REPT_PAT_001', 45, 26.2, 'Type 2', 7.5, 6, 1, 'report_test_fixture'),
                     ('REPT_PAT_002', 55, 29.0, 'Type 1', 8.1, 12, 1, 'report_test_fixture')
        """)

        base_dt = datetime(2026, 4, 1, 10, 0, 0)
        readings_rows = []
        for i in range(12):
            t_str = (base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
            readings_rows.append((
                'REPT_PAT_001', t_str, 150.0 + (i * 1.5), 74, 20 + i, 0, 1, 'report_test_fixture'
            ))
            readings_rows.append((
                'REPT_PAT_002', t_str, 170.0 + (i * 1.5), 78, 15 + i, 0, 1, 'report_test_fixture'
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

        # Create a test user and session so auth-protected routes work
        test_user = register_user(
            full_name="Report Test User",
            email="testuser_report@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls._test_session_id = test_session["session_id"]
        cls._test_csrf_token = test_session["csrf_token"]

        cls.client = TestClient(
            fastapi_app,
            cookies={"twinsense_session": cls._test_session_id}
        )

        # Seed predictions for both patients
        res1 = cls.client.post(
            "/api/patients/REPT_PAT_001/predict",
            json={},
            headers={"X-CSRF-Token": cls._test_csrf_token}
        )
        cls.pred_id_1 = res1.json()["prediction_id"]

        res2 = cls.client.post(
            "/api/patients/REPT_PAT_002/predict",
            json={},
            headers={"X-CSRF-Token": cls._test_csrf_token}
        )
        cls.pred_id_2 = res2.json()["prediction_id"]

    @classmethod
    def tearDownClass(cls):
        app.database.DB_PATH = cls.orig_db
        cls.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # CSV endpoint tests
    # ------------------------------------------------------------------
    def test_13_csv_download_returns_200(self):
        """GET /api/patients/{id}/report/csv returns 200 OK."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertEqual(response.status_code, 200)

    def test_14_csv_content_type(self):
        """CSV endpoint returns text/csv content-type."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertIn("text/csv", response.headers.get("content-type", ""))

    def test_15_csv_content_disposition_attachment(self):
        """CSV sets Content-Disposition attachment with correct filename pattern."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        disposition = response.headers.get("content-disposition", "")
        self.assertIn("attachment", disposition)
        self.assertIn("TwinSense_Report_REPT_PAT_001", disposition)
        self.assertIn(".csv", disposition)

    def test_16_csv_contains_patient_id(self):
        """CSV body contains the correct synthetic patient ID."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertIn("REPT_PAT_001", response.text)

    def test_17_csv_contains_safety_disclaimers(self):
        """CSV body includes all 5 mandatory safety limitation statements."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        body = response.text
        self.assertIn("synthetic simulation data", body)
        self.assertIn("not clinically validated", body)
        self.assertIn("insulin dosing", body)
        self.assertIn("zero training examples", body)
        self.assertIn("0.0 probability", body)

    def test_18_csv_contains_hypoglycemia_warning(self):
        """CSV body contains the CRITICAL hypoglycemia limitation warning."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertIn("CRITICAL MODEL LIMITATION", response.text)

    def test_19_csv_contains_probabilities(self):
        """CSV body contains model-estimated class probabilities as percentages."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertIn("Class probability", response.text)
        self.assertIn("%", response.text)

    def test_20_csv_specific_prediction_id_not_found_returns_404(self):
        """GET /report/csv with non-existent prediction_id returns 404."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv?prediction_id=9999999")
        self.assertEqual(response.status_code, 404)
        self.assertIn("not found", response.json()["detail"].lower())

    def test_21_csv_invalid_patient_returns_404(self):
        """GET /report/csv for non-existent patient returns 404."""
        response = self.client.get("/api/patients/GHOST_PATIENT/report/csv")
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # PDF endpoint tests
    # ------------------------------------------------------------------
    def test_22_pdf_download_status(self):
        """GET /api/patients/{id}/report/pdf returns 200 or 503 (if reportlab missing)."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/pdf")
        self.assertIn(response.status_code, [200, 503])

    def test_23_pdf_valid_signature(self):
        """PDF response starts with %PDF- when reportlab is available."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/pdf")
        if response.status_code == 200:
            self.assertTrue(
                response.content.startswith(b"%PDF-"),
                f"Expected %PDF- prefix, got: {response.content[:8]}"
            )

    def test_24_pdf_content_disposition_attachment(self):
        """PDF response sets Content-Disposition attachment with correct filename."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/pdf")
        if response.status_code == 200:
            disposition = response.headers.get("content-disposition", "")
            self.assertIn("attachment", disposition)
            self.assertIn("TwinSense_Report_REPT_PAT_001", disposition)
            self.assertIn(".pdf", disposition)

    def test_25_pdf_specific_prediction_not_found_returns_404(self):
        """GET /report/pdf with non-existent prediction_id returns 404."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/pdf?prediction_id=9999999")
        self.assertEqual(response.status_code, 404)

    def test_26_pdf_invalid_patient_returns_404(self):
        """GET /report/pdf for non-existent patient returns 404."""
        response = self.client.get("/api/patients/GHOST_PATIENT/report/pdf")
        self.assertEqual(response.status_code, 404)

    # ------------------------------------------------------------------
    # Regression checks
    # ------------------------------------------------------------------
    def test_27_regression_health_still_works(self):
        """Regression: /api/health still returns HEALTHY after report endpoints added."""
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "HEALTHY")

    def test_28_regression_predict_still_works(self):
        """Regression: POST /predict still works and logs prediction correctly."""
        response = self.client.post("/api/patients/REPT_PAT_001/predict", json={})
        self.assertEqual(response.status_code, 201)
        data = response.json()
        self.assertIn("prediction_id", data)
        self.assertIn(data["predicted_risk_class"], [1, 2, 3])

    def test_29_csv_exact_disclaimer_and_title(self):
        """CSV contains exact title and verbatim mandatory clinical disclaimer."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.assertEqual(response.status_code, 200)
        from app.reports import MANDATORY_DISCLAIMER, REPORT_TITLE
        self.assertIn(REPORT_TITLE, response.text)
        self.assertIn(MANDATORY_DISCLAIMER, response.text)

    def test_30_pdf_extracted_text_contains_patient_probabilities_and_disclaimer(self):
        """PDF extracted text contains patient ID, probabilities, and exact disclaimer."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/pdf")
        self.assertEqual(response.status_code, 200)
        import io
        from pypdf import PdfReader
        from app.reports import MANDATORY_DISCLAIMER
        reader = PdfReader(io.BytesIO(response.content))
        raw_text = " ".join(page.extract_text() for page in reader.pages)
        # Normalize whitespace and soft line wraps from PDF rendering
        norm_text = " ".join(raw_text.split())
        self.assertIn("REPT_PAT_001", norm_text)
        self.assertIn("Model-Estimated Class Probabilities", norm_text)
        self.assertIn(MANDATORY_DISCLAIMER, norm_text)

    def test_31_mismatched_patient_prediction_pair_returns_409(self):
        """Mismatched pair (prediction ID belonging to another patient) returns HTTP 409."""
        response = self.client.get(f"/api/patients/REPT_PAT_001/report/csv?prediction_id={self.pred_id_2}")
        self.assertEqual(response.status_code, 409)
        self.assertIn("mismatched pair", response.json()["detail"].lower())

    def test_32_malformed_patient_id_rejected(self):
        """Malformed patient IDs with invalid characters or directory traversal return 400."""
        response = self.client.get("/api/patients/../../etc/passwd/report/csv")
        self.assertIn(response.status_code, [400, 404])

    def test_33_missing_fields_render_not_available(self):
        """Missing profile or prediction fields render 'Not available' without crashing."""
        from app.reports import generate_csv_report, generate_pdf_report
        csv_out = generate_csv_report({}, {})
        self.assertIn("Not available", csv_out)
        pdf_out = generate_pdf_report({}, {})
        self.assertTrue(pdf_out.startswith(b"%PDF-"))

    def test_34_csv_escaping_and_formula_injection(self):
        """Formula injection cells starting with =, +, -, @ get a leading apostrophe while numbers stay numeric."""
        from app.reports import sanitize_csv_cell
        self.assertEqual(sanitize_csv_cell("=SUM(1,2)"), "'=SUM(1,2)")
        self.assertEqual(sanitize_csv_cell("+cmd|' /C calc'!A0"), "'+cmd|' /C calc'!A0")
        self.assertEqual(sanitize_csv_cell("-malicious"), "'-malicious")
        self.assertEqual(sanitize_csv_cell("@danger"), "'@danger")
        self.assertEqual(sanitize_csv_cell(146.9), 146.9)
        self.assertEqual(sanitize_csv_cell(-15), -15)
        self.assertEqual(sanitize_csv_cell(None), "Not available")

    def test_35_download_does_not_create_new_prediction(self):
        """Downloading CSV or PDF reports never increments prediction row count."""
        import sqlite3
        conn = sqlite3.connect(str(self.test_db_path))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM predictions")
        count_before = c.fetchone()[0]
        conn.close()

        self.client.get("/api/patients/REPT_PAT_001/report/csv")
        self.client.get("/api/patients/REPT_PAT_001/report/pdf")

        conn = sqlite3.connect(str(self.test_db_path))
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM predictions")
        count_after = c.fetchone()[0]
        conn.close()

        self.assertEqual(count_before, count_after)

    def test_36_both_timestamps_distinct_labels(self):
        """Observation timestamp and target timestamp (+45 min later) are clearly distinct."""
        response = self.client.get("/api/patients/REPT_PAT_001/report/csv")
        body = response.text
        self.assertIn("Observation Timestamp (Reading)", body)
        self.assertIn("Target Timestamp (45 Minutes Later)", body)
