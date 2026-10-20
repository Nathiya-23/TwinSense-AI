"""
TwinSense AI - General Suggestions Test Suite
=============================================

Tests:
1. Each existing risk class maps to a non-empty suggestion list (3-5 suggestions),
   or the explicit fallback "No suggestions available for this result."
2. Suggestions match the predicted class of the exact forecast returned.
3. Hypoglycemia note and disclaimer appear in API and panel data for every class.
4. Forbidden terms test: no suggestion text contains dosing language
   (e.g., "units of insulin", "take insulin", "mg of", "grams of carbohydrate").
5. Unknown or missing class returns the fallback, not a 500 error.
6. No new prediction is created and no model call is made when fetching suggestions.
7. HTML dashboard includes suggestions panel with empty state, exact disclaimer,
   and hypoglycemia note.
8. CSV and PDF prediction exports contain the General Suggestions section.
9. Verified presence of clinician review notice comment in app/suggestions.py.
"""

import unittest
from pathlib import Path
import tempfile
import sqlite3
import io
from datetime import datetime, timedelta
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.database import init_db
import app.database
from app.auth import register_user, create_session
from app.suggestions import (
    SUGGESTIONS_MAP,
    SUGGESTIONS_DISCLAIMER,
    HYPOGLYCEMIA_PANEL_NOTE,
    ESCALATION_LINE,
    FALLBACK_SUGGESTION,
    get_suggestions_for_risk_class
)


class TestSuggestions(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_suggestions.db"
        init_db(cls.test_db_path)

        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c,
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES
            ('SUGG_PAT_001', 46, 26.5, 'Type 2', 7.2, 5, 1, 'sugg_test_fixture'),
            ('SUGG_PAT_002', 34, 23.0, 'Type 1', 8.4, 4, 1, 'sugg_test_fixture')
        """)

        # 12 readings @ 5-min intervals
        base_dt = datetime(2026, 3, 1, 10, 0, 0)
        readings_rows = []
        for i in range(12):
            t_str = (base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
            readings_rows.append((
                'SUGG_PAT_001', t_str, 130.0 + (i * 2.0), 72, 10 + i, 0, 1, 'sugg_test_fixture'
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

        test_user = register_user(
            full_name="Suggestions Tester",
            email="tester_suggestions@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls._test_session_id = test_session["session_id"]
        cls._test_csrf = test_session["csrf_token"]

        cls.client = TestClient(fastapi_app, cookies={"twinsense_session": cls._test_session_id})

    @classmethod
    def tearDownClass(cls):
        app.database.DB_PATH = cls.orig_db
        cls.temp_dir.cleanup()

    # ------------------------------------------------------------------
    # 1. Non-empty suggestions for all existing classes & fallback
    # ------------------------------------------------------------------
    def test_01_all_existing_classes_map_to_non_empty_suggestions(self):
        """Every defined class in the mapping has 3 to 5 non-empty short suggestions."""
        for cls_id in [1, 2, 3]:
            res = get_suggestions_for_risk_class(cls_id, current_glucose=120.0)
            self.assertEqual(res["risk_class"], cls_id)
            self.assertTrue(len(res["suggestions"]) >= 3)
            self.assertTrue(len(res["suggestions"]) <= 5)
            for s in res["suggestions"]:
                self.assertIsInstance(s, str)
                self.assertTrue(len(s.strip()) > 10)

    # ------------------------------------------------------------------
    # 2. Unknown or missing class returns fallback, not a 500
    # ------------------------------------------------------------------
    def test_02_unknown_or_missing_class_returns_fallback_not_500(self):
        """Missing or unknown class returns graceful fallback without error."""
        for invalid_cls in [None, 0, 4, 999, -1]:
            res = get_suggestions_for_risk_class(invalid_cls)
            self.assertEqual(res["suggestions"], [FALLBACK_SUGGESTION])
            self.assertIn("No suggestions available", res["suggestions"][0])

        # Test API endpoint GET /api/suggestions (missing query param)
        api_res = self.client.get("/api/suggestions")
        self.assertEqual(api_res.status_code, 200)
        data = api_res.json()
        self.assertEqual(data["suggestions"], [FALLBACK_SUGGESTION])

        # Test API endpoint GET /api/suggestions/999
        api_res_999 = self.client.get("/api/suggestions/999")
        self.assertEqual(api_res_999.status_code, 200)
        self.assertEqual(api_res_999.json()["suggestions"], [FALLBACK_SUGGESTION])

    # ------------------------------------------------------------------
    # 3. Hypoglycemia note and disclaimer appear for every class
    # ------------------------------------------------------------------
    def test_03_hypoglycemia_note_and_disclaimer_for_every_class(self):
        """Fixed hypoglycemia note and exact disclaimer appear for every class including unknown."""
        expected_disclaimer = (
            "SYNTHETIC DATA — NOT CLINICALLY VALIDATED. "
            "This prototype must not be used for diagnosis, treatment, insulin dosing, or medical decisions."
        )
        expected_hypo_note = (
            "Low-glucose risk is not predicted by this prototype. "
            "A 0% probability does not mean hypoglycemia is impossible. "
            "If you experience symptoms such as shakiness, sweating, confusion, or dizziness, "
            "follow your clinician's guidance and seek medical help."
        )

        self.assertEqual(SUGGESTIONS_DISCLAIMER, expected_disclaimer)
        self.assertEqual(HYPOGLYCEMIA_PANEL_NOTE, expected_hypo_note)

        for cls_id in [1, 2, 3, 999, None]:
            res = get_suggestions_for_risk_class(cls_id)
            self.assertEqual(res["disclaimer"], expected_disclaimer)
            self.assertEqual(res["hypoglycemia_note"], expected_hypo_note)

    # ------------------------------------------------------------------
    # 4. Escalation line for elevated-risk classes
    # ------------------------------------------------------------------
    def test_04_escalation_line_for_elevated_risk_classes(self):
        """Classes 1 and 3 (elevated risk) contain the escalation line."""
        expected_escalation = (
            "If you feel unwell or symptoms worsen, contact a healthcare professional or local emergency services."
        )
        self.assertEqual(ESCALATION_LINE, expected_escalation)

        # Class 3 (Hyperglycemia)
        res_3 = get_suggestions_for_risk_class(3)
        self.assertTrue(res_3["is_elevated_risk"])
        self.assertEqual(res_3["escalation_line"], expected_escalation)
        self.assertIn(expected_escalation, res_3["suggestions"])

        # Class 1 (Hypoglycemia limitation)
        res_1 = get_suggestions_for_risk_class(1)
        self.assertTrue(res_1["is_elevated_risk"])
        self.assertEqual(res_1["escalation_line"], expected_escalation)
        self.assertIn(expected_escalation, res_1["suggestions"])

        # Class 2 (In-Range) should NOT have escalation line
        res_2 = get_suggestions_for_risk_class(2)
        self.assertFalse(res_2["is_elevated_risk"])
        self.assertIsNone(res_2["escalation_line"])

    # ------------------------------------------------------------------
    # 5. Forbidden terms test
    # ------------------------------------------------------------------
    def test_05_forbidden_terms_test(self):
        """No suggestion text contains dosing language, carb amounts, or safety guarantees."""
        forbidden_phrases = [
            "units of insulin",
            "take insulin",
            "mg of",
            "grams of carbohydrate",
            "inject",
            "titrate",
            "insulin dose",
            "take medication",
            "will become normal",
            "you are safe",
            "cure",
            "diagnose"
        ]

        for cls_id, data in SUGGESTIONS_MAP.items():
            for suggestion in data["suggestions"]:
                sugg_lower = suggestion.lower()
                for phrase in forbidden_phrases:
                    self.assertNotIn(
                        phrase,
                        sugg_lower,
                        f"Forbidden phrase '{phrase}' found in Class {cls_id} suggestion: {suggestion}"
                    )

    # ------------------------------------------------------------------
    # 6. No new prediction is created and no model call when fetching suggestions
    # ------------------------------------------------------------------
    def test_06_no_new_prediction_and_no_model_call(self):
        """Fetching suggestions does NOT execute ML inference or log new DB predictions."""
        conn = sqlite3.connect(str(self.test_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM predictions")
        count_before = cursor.fetchone()[0]
        conn.close()

        # Call endpoint for class 2
        with patch("src.twin_engine.TwinEngine.predict_risk") as mock_predict:
            res = self.client.get("/api/suggestions/2?glucose=115.0")
            self.assertEqual(res.status_code, 200)
            mock_predict.assert_not_called()

        # Call endpoint for general suggestions
        with patch("src.twin_engine.TwinEngine.predict_risk") as mock_predict:
            res = self.client.get("/api/suggestions?risk_class=3")
            self.assertEqual(res.status_code, 200)
            mock_predict.assert_not_called()

        # Verify DB predictions count did not change
        conn = sqlite3.connect(str(self.test_db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM predictions")
        count_after = cursor.fetchone()[0]
        conn.close()

        self.assertEqual(count_before, count_after)

    # ------------------------------------------------------------------
    # 7. Suggestions match predicted class of exact forecast returned
    # ------------------------------------------------------------------
    def test_07_suggestions_match_forecast_predicted_class(self):
        """POST /api/patients/{id}/predict returns suggestions matching predicted risk class."""
        res = self.client.post("/api/patients/SUGG_PAT_001/predict", json={})
        self.assertEqual(res.status_code, 201)
        data = res.json()

        self.assertIn("suggestions", data)
        sugg = data["suggestions"]
        self.assertIsNotNone(sugg)
        self.assertEqual(sugg["risk_class"], data["predicted_risk_class"])

        expected_mapping = SUGGESTIONS_MAP[data["predicted_risk_class"]]
        self.assertEqual(sugg["suggestions"], expected_mapping["suggestions"])
        self.assertIn("Why am I seeing this?", sugg["why_am_i_seeing_this"])
        self.assertIn(str(round(data["current_glucose_mg_dl"], 1)), sugg["why_am_i_seeing_this"])

    # ------------------------------------------------------------------
    # 8. Dashboard HTML includes Suggestions panel, empty state & disclaimers
    # ------------------------------------------------------------------
    def test_08_dashboard_html_contains_suggestions_panel_and_disclaimers(self):
        """HTML contains suggestions-panel, empty state text, exact disclaimer, and hypo note."""
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        html = res.text

        self.assertIn('id="suggestions-panel"', html)
        self.assertIn('id="suggestions-empty-state"', html)
        self.assertIn("Run a forecast to see general suggestions.", html)
        self.assertIn("SYNTHETIC DATA — NOT CLINICALLY VALIDATED.", html)
        self.assertIn("Low-glucose risk is not predicted by this prototype.", html)

    # ------------------------------------------------------------------
    # 9. CSV and PDF exports contain General Suggestions section
    # ------------------------------------------------------------------
    def test_09_csv_and_pdf_contain_general_suggestions(self):
        """Exported CSV and PDF include GENERAL SUGGESTIONS section with disclaimer and note."""
        # Ensure at least one prediction exists
        self.client.post("/api/patients/SUGG_PAT_001/predict", json={})

        # Test CSV export
        csv_res = self.client.get("/api/patients/SUGG_PAT_001/report/csv")
        self.assertEqual(csv_res.status_code, 200)
        csv_text = csv_res.text
        self.assertIn("=== GENERAL SUGGESTIONS ===", csv_text)
        self.assertIn("SYNTHETIC DATA — NOT CLINICALLY VALIDATED.", csv_text)
        self.assertIn("Low-glucose risk is not predicted by this prototype.", csv_text)
        self.assertIn("Suggestion 1", csv_text)

        # Test PDF export
        pdf_res = self.client.get("/api/patients/SUGG_PAT_001/report/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(pdf_res.content))
        pdf_text = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
        self.assertIn("General Suggestions", pdf_text)
        self.assertIn("SYNTHETIC DATA — NOT CLINICALLY VALIDATED.", pdf_text)
        self.assertIn("Low-glucose risk is not predicted by this prototype.", pdf_text)

    # ------------------------------------------------------------------
    # 10. Required clinician review notice in code
    # ------------------------------------------------------------------
    def test_10_clinician_review_notice_in_suggestions_module(self):
        """app/suggestions.py must contain the exact clinician review notice comment."""
        code = Path("app/suggestions.py").read_text(encoding="utf-8")
        self.assertIn(
            "Requires review by a qualified clinician before any real-world use.",
            code
        )


if __name__ == "__main__":
    unittest.main()
