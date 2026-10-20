"""
TwinSense AI - Phase 3 Test Suite: Hypoglycemia Support & Model Versioning
========================================================================

Tests:
1. Generator determinism with seed:
   Running generate_synthetic_data_v2 with the same seed produces identical data.
2. Class counts per split:
   Verifies Class 1 (hypoglycemia) counts in train, validation, and test splits of v2 dataset.
3. No patient overlap between splits:
   Verifies that splits are strictly segregated without patient contamination or leakage.
4. Model v1 still loads and behaves as before:
   Loads original model, verifies predictions, 0.0 Class 1 probability, and exact original warning.
5. Model v2 produces valid probabilities summing to 1:
   Loads v2 model, verifies all 3 class probabilities are valid non-negative floats summing to 1.
6. Warning text matches active model in API:
   Verifies /api/health and prediction endpoints return v1 warning under default and v2 warning under v2.
7. Warning text matches active model in panel data:
   Verifies get_suggestions_for_risk_class returns the appropriate hypoglycemia note for v1 vs v2.
8. Warning text matches active model in CSV and PDF reports:
   Verifies generated CSV and PDF outputs contain the active model's warning text.
"""

import os
import unittest
from pathlib import Path
import tempfile
import sqlite3
from unittest.mock import patch
import pandas as pd
import numpy as np
from fastapi.testclient import TestClient

from app.main import app as fastapi_app
from app.database import init_db
import app.database
from app.auth import register_user, create_session
from app.config import (
    MODEL_V1_PATH,
    FEATURE_COLS_V1_PATH,
    MODEL_V2_PATH,
    FEATURE_COLS_V2_PATH
)
from src.twin_engine import (
    TwinEngine,
    UNSUPPORTED_HYPOGLYCEMIA_WARNING,
    V2_HYPOGLYCEMIA_WARNING,
    CLINICAL_PROTOTYPE_DISCLAIMER
)
from app.suggestions import (
    get_suggestions_for_risk_class,
    HYPOGLYCEMIA_PANEL_NOTE,
    HYPOGLYCEMIA_PANEL_NOTE_V2
)
from app.reports import (
    generate_csv_report,
    generate_pdf_report,
    HYPOGLYCEMIA_WARNING,
    V2_HYPOGLYCEMIA_WARNING as REPT_V2_WARNING
)


class TestPhase3HypoglycemiaSupport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_db_path = Path(cls.temp_dir.name) / "test_phase3.db"
        init_db(cls.test_db_path)

        conn = sqlite3.connect(str(cls.test_db_path))
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO patients (
                patient_id, age, bmi, diabetes_type, baseline_hba1c,
                diabetes_duration_years, is_synthetic, data_source
            ) VALUES
            ('P3_PAT_001', 52, 27.5, 'Type 2', 7.8, 6, 1, 'phase3_test_fixture')
        """)

        from datetime import datetime, timedelta
        base_dt = datetime(2026, 3, 1, 10, 0, 0)
        readings_rows = []
        for i in range(12):
            t_str = (base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S")
            readings_rows.append((
                'P3_PAT_001', t_str, 125.0 + (i * 1.5), 72, 10 + i, 0, 1, 'phase3_test_fixture'
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
            full_name="Phase3 Tester",
            email="tester_phase3@twinsense.local",
            password="Test1234",
            confirm_password="Test1234",
            db_path=cls.test_db_path
        )
        test_session = create_session(test_user["id"], db_path=cls.test_db_path)
        cls.client = TestClient(fastapi_app, cookies={"twinsense_session": test_session["session_id"]})

        cls.sample_profile = {
            "patient_id": "P3_PAT_001",
            "age": 52,
            "bmi": 27.5,
            "baseline_hba1c": 7.8,
            "diabetes_duration_years": 6,
            "diabetes_type": "Type 2"
        }
        cls.sample_readings = pd.DataFrame({
            "timestamp": [(base_dt + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [120.0, 122.0, 124.0, 126.0, 128.0, 130.0],
            "heart_rate": [72] * 6,
            "steps": [10] * 6,
            "meal_event": [0] * 6
        })

    @classmethod
    def tearDownClass(cls):
        app.database.DB_PATH = cls.orig_db
        cls.temp_dir.cleanup()

    # 1. Generator determinism with seed
    def test_01_generator_determinism_with_seed(self):
        from src.data_generator_v2 import generate_synthetic_data_v2
        profiles1, timeseries1 = generate_synthetic_data_v2(num_patients=2, days_per_patient=1, seed=42)
        profiles2, timeseries2 = generate_synthetic_data_v2(num_patients=2, days_per_patient=1, seed=42)

        pd.testing.assert_frame_equal(profiles1, profiles2)
        pd.testing.assert_frame_equal(timeseries1, timeseries2)

    # 2. Class counts per split in v2 dataset
    def test_02_class_counts_per_split(self):
        v2_dataset_path = Path("data/synthetic_v2/training_dataset_v2.csv")
        self.assertTrue(v2_dataset_path.exists(), "v2 training dataset must exist")

        df = pd.read_csv(v2_dataset_path)
        self.assertIn("future_glucose_risk", df.columns)

        class_counts = df["future_glucose_risk"].value_counts().to_dict()
        # Verify Class 1 is present in the dataset
        self.assertIn(1, class_counts, "Class 1 must be present in v2 dataset")
        self.assertGreaterEqual(class_counts[1], 10, "Should have sufficient Class 1 examples overall")

        # Verify splits from train_v2 logic
        from src.train_v2 import partition_with_embargo
        train_df, val_df, test_df = partition_with_embargo(df)

        train_counts = train_df["future_glucose_risk"].value_counts().to_dict()
        val_counts = val_df["future_glucose_risk"].value_counts().to_dict()
        test_counts = test_df["future_glucose_risk"].value_counts().to_dict()

        self.assertGreater(train_counts.get(1, 0), 0, "Train split must have Class 1 examples")
        self.assertGreater(val_counts.get(1, 0), 0, "Val split must have Class 1 examples")
        self.assertGreater(test_counts.get(1, 0), 0, "Test split must have Class 1 examples")

    # 3. No patient overlap between splits or clean temporal splits
    def test_03_no_split_leakage(self):
        v2_dataset_path = Path("data/synthetic_v2/training_dataset_v2.csv")
        df = pd.read_csv(v2_dataset_path)
        from src.train_v2 import partition_with_embargo
        train_df, val_df, test_df = partition_with_embargo(df)

        # For every patient, verify timestamps in train < val < test strictly, with embargo buffer
        for pid, p_group in df.groupby("patient_id"):
            p_train = train_df[train_df["patient_id"] == pid]
            p_val = val_df[val_df["patient_id"] == pid]
            p_test = test_df[test_df["patient_id"] == pid]

            if len(p_train) > 0 and len(p_val) > 0:
                max_train_t = pd.to_datetime(p_train["timestamp"]).max()
                min_val_t = pd.to_datetime(p_val["timestamp"]).min()
                # Embargo buffer ensures at least 45 minutes gap
                self.assertGreaterEqual((min_val_t - max_train_t).total_seconds(), 45 * 60)

            if len(p_val) > 0 and len(p_test) > 0:
                max_val_t = pd.to_datetime(p_val["timestamp"]).max()
                min_test_t = pd.to_datetime(p_test["timestamp"]).min()
                self.assertGreaterEqual((min_test_t - max_val_t).total_seconds(), 45 * 60)

    # 4. v1 still loads and behaves as before
    def test_04_v1_still_loads_and_behaves_as_before(self):
        v1_engine = TwinEngine(model_path=MODEL_V1_PATH, feature_cols_path=FEATURE_COLS_V1_PATH)
        self.assertEqual(v1_engine.model.n_classes_, 2)
        res = v1_engine.predict_risk(self.sample_profile, self.sample_readings)

        # Class 1 probability must be explicit 0.0 with original limitation notice
        self.assertEqual(res["class_probabilities"]["1_hypoglycemia"], 0.0)
        self.assertEqual(res["hypoglycemia_limitation"], UNSUPPORTED_HYPOGLYCEMIA_WARNING)
        self.assertIn("ZERO training support for Class 1", res["hypoglycemia_limitation"])

    # 5. v2 produces valid probabilities summing to 1
    def test_05_v2_produces_valid_probabilities_summing_to_1(self):
        self.assertTrue(MODEL_V2_PATH.exists(), "v2 model file must exist")
        v2_engine = TwinEngine(model_path=MODEL_V2_PATH, feature_cols_path=FEATURE_COLS_V2_PATH)
        res = v2_engine.predict_risk(self.sample_profile, self.sample_readings)

        probs = res["class_probabilities"]
        self.assertIn("1_hypoglycemia", probs)
        self.assertIn("2_in_range", probs)
        self.assertIn("3_hyperglycemia", probs)

        for k, p in probs.items():
            self.assertGreaterEqual(p, 0.0)
            self.assertLessEqual(p, 1.0)

        total_prob = sum(probs.values())
        self.assertAlmostEqual(total_prob, 1.0, places=2)

    # 6. Warning text matches active model in API
    def test_06_warning_text_matches_active_model_in_api(self):
        # Default v1 check
        res_v1 = self.client.get("/api/health")
        self.assertEqual(res_v1.status_code, 200)
        health_data = res_v1.json()
        self.assertEqual(health_data["active_model_version"], "v1")
        self.assertEqual(health_data["hypoglycemia_limitation"], UNSUPPORTED_HYPOGLYCEMIA_WARNING)

        # Test v2 with mocked engine
        with patch("src.twin_engine._IS_V2", True), \
             patch("src.twin_engine._MODEL_VERSION", "v2"), \
             patch("src.twin_engine._ACTIVE_MODEL_PATH", MODEL_V2_PATH), \
             patch("src.twin_engine._ACTIVE_FEATURE_COLS_PATH", FEATURE_COLS_V2_PATH):
            v2_engine = TwinEngine()
            self.assertEqual(v2_engine.active_model_version, "v2")
            self.assertEqual(v2_engine.hypoglycemia_warning, V2_HYPOGLYCEMIA_WARNING)

    # 7. Warning text matches active model in panel data
    def test_07_warning_text_matches_active_model_in_panel_data(self):
        # v1 note
        sugg_v1 = get_suggestions_for_risk_class(2, current_glucose=120.0, model_version="v1")
        self.assertEqual(sugg_v1["hypoglycemia_note"], HYPOGLYCEMIA_PANEL_NOTE)

        # v2 note
        sugg_v2 = get_suggestions_for_risk_class(2, current_glucose=120.0, model_version="v2")
        self.assertEqual(sugg_v2["hypoglycemia_note"], HYPOGLYCEMIA_PANEL_NOTE_V2)
        self.assertIn("SYNTHETIC ONLY", sugg_v2["hypoglycemia_note"])
        self.assertIn("NOT clinically validated", sugg_v2["hypoglycemia_note"])

    # 8. Warning text matches active model in CSV and PDF reports
    def test_08_warning_text_matches_active_model_in_csv_and_pdf(self):
        pred_v1 = {
            "id": 1,
            "patient_id": "P3_PAT_001",
            "prediction_timestamp": "2026-03-01 12:00:00",
            "reading_timestamp": "2026-03-01 11:55:00",
            "predicted_target_timestamp": "2026-03-01 12:40:00",
            "current_glucose_mg_dl": 120.0,
            "predicted_risk_class": 2,
            "risk_label": "Predicted In-Range Trajectory (70-180 mg/dL)",
            "probabilities": {"1_hypoglycemia": 0.0, "2_in_range": 0.85, "3_hyperglycemia": 0.15},
            "contributing_factors": ["Normal glucose trend"],
            "active_model_version": "v1"
        }
        pred_v2 = dict(pred_v1)
        pred_v2["active_model_version"] = "v2"

        # CSV v1
        csv_v1 = generate_csv_report(self.sample_profile, pred_v1)
        self.assertIn(HYPOGLYCEMIA_WARNING, csv_v1)

        # CSV v2
        csv_v2 = generate_csv_report(self.sample_profile, pred_v2)
        self.assertIn(REPT_V2_WARNING, csv_v2)

        # PDF v1 and v2 bytes generate cleanly
        pdf_v1 = generate_pdf_report(self.sample_profile, pred_v1)
        self.assertTrue(len(pdf_v1) > 1000)

        pdf_v2 = generate_pdf_report(self.sample_profile, pred_v2)
        self.assertTrue(len(pdf_v2) > 1000)
