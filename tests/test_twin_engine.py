"""
TwinSense AI - Step 4 Deterministic Unit Tests
==============================================
Validates input validation, feature ordering, risk-label mapping,
unsupported hypoglycemia messaging, timestamp integrity, and immutability.
Uses synthetic test fixtures exclusively.
"""

import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from src.twin_engine import TwinEngine, UNSUPPORTED_HYPOGLYCEMIA_WARNING, CLINICAL_PROTOTYPE_DISCLAIMER


class TestTwinEngine(unittest.TestCase):

    def setUp(self):
        self.engine = TwinEngine()

        # Synthetic Patient Profile Fixture
        self.valid_profile = {
            "age": 45,
            "bmi": 26.5,
            "baseline_hba1c": 7.5,
            "diabetes_duration_years": 6
        }

        # Synthetic 6-reading history fixture (5-minute intervals = 30 min span)
        base_time = datetime(2026, 3, 1, 10, 0, 0)
        self.valid_readings = pd.DataFrame({
            "timestamp": [(base_time + timedelta(minutes=5 * i)).strftime("%Y-%m-%d %H:%M:%S") for i in range(6)],
            "glucose_mg_dl": [140.0, 142.5, 145.0, 147.0, 150.0, 153.5],
            "heart_rate": [72, 74, 75, 73, 76, 78],
            "steps": [10, 15, 8, 22, 12, 18],
            "meal_event": [0, 0, 0, 0, 0, 0]
        })

    def test_feature_ordering_matches_schema_exactly(self):
        """Feature extraction must match exact schema column order without omission."""
        feature_df = self.engine.extract_features(self.valid_profile, self.valid_readings)
        self.assertEqual(
            list(feature_df.columns),
            self.engine.expected_feature_columns,
            "Engine extracted features do not match trained schema order!"
        )
        self.assertEqual(len(feature_df), 1)

    def test_valid_prediction_returns_complete_structure(self):
        """Valid inputs must produce a structured risk score and all required metadata."""
        result = self.engine.predict_risk(self.valid_profile, self.valid_readings)
        self.assertEqual(result["status"], "SUCCESS")
        self.assertIn("current_glucose_mg_dl", result)
        self.assertIn("predicted_risk_class", result)
        self.assertIn("risk_label", result)
        self.assertEqual(result["prediction_horizon_minutes"], 45)
        self.assertIn("key_contributing_factors", result)
        self.assertTrue(len(result["key_contributing_factors"]) >= 4)
        self.assertIn("hypoglycemia_limitation", result)
        self.assertIn("clinical_disclaimer", result)

    def test_unsupported_hypoglycemia_messaging(self):
        """Every prediction must clearly warn that hypoglycemia is unsupported by current model."""
        result = self.engine.predict_risk(self.valid_profile, self.valid_readings)
        self.assertIn("ZERO training support for Class 1", result["hypoglycemia_limitation"])
        self.assertIn("CANNOT predict or rule out hypoglycemia", result["hypoglycemia_limitation"])
        # Probability for class 1 must be explicitly 0.0 with limitation note
        self.assertEqual(result["class_probabilities"]["1_hypoglycemia"], 0.0)

    def test_risk_label_mapping(self):
        """Risk classes must map accurately to their respective human-readable labels."""
        # Test in-range prediction with moderate glucose
        res_in_range = self.engine.predict_risk(self.valid_profile, self.valid_readings)
        self.assertIn(res_in_range["predicted_risk_class"], [2, 3])
        if res_in_range["predicted_risk_class"] == 2:
            self.assertIn("In-Range", res_in_range["risk_label"])

        # Test high glucose fixture driving hyperglycemia
        high_readings = self.valid_readings.copy()
        high_readings["glucose_mg_dl"] = [220.0, 225.0, 230.0, 235.0, 240.0, 248.0]
        res_hyper = self.engine.predict_risk(self.valid_profile, high_readings)
        self.assertEqual(res_hyper["predicted_risk_class"], 3)
        self.assertIn("Hyperglycemia", res_hyper["risk_label"])

    def test_insufficient_history_rejected(self):
        """Passing fewer than 6 readings (< 30 minutes) must raise ValueError."""
        short_readings = self.valid_readings.iloc[:4]  # Only 4 readings
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(self.valid_profile, short_readings)
        self.assertIn("Insufficient reading history", str(ctx.exception))

    def test_missing_baseline_field_rejected(self):
        """Missing patient profile fields must raise ValueError rather than filling defaults."""
        incomplete_profile = self.valid_profile.copy()
        del incomplete_profile["baseline_hba1c"]
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(incomplete_profile, self.valid_readings)
        self.assertIn("Missing required baseline profile field: 'baseline_hba1c'", str(ctx.exception))

    def test_invalid_baseline_values_rejected(self):
        """Unrealistic or negative clinical fields must be rejected."""
        bad_profile = self.valid_profile.copy()
        bad_profile["bmi"] = -5.0
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(bad_profile, self.valid_readings)
        self.assertIn("Invalid BMI", str(ctx.exception))

    def test_disordered_timestamps_rejected(self):
        """Non-chronological readings must raise ValueError."""
        scrambled_readings = self.valid_readings.copy()
        # Swap rows 2 and 3
        idx = scrambled_readings.index.tolist()
        idx[2], idx[3] = idx[3], idx[2]
        scrambled_readings = scrambled_readings.reindex(idx)
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(self.valid_profile, scrambled_readings)
        self.assertIn("chronological order", str(ctx.exception))

    def test_duplicate_timestamps_rejected(self):
        """Duplicate timestamps must be rejected."""
        dup_readings = self.valid_readings.copy()
        dup_readings.loc[1, "timestamp"] = dup_readings.loc[0, "timestamp"]
        with self.assertRaises(ValueError) as ctx:
            self.engine.validate_inputs(self.valid_profile, dup_readings)
        self.assertIn("Duplicate timestamps", str(ctx.exception))

    def test_what_if_simulation_immutability(self):
        """What-if simulation must not mutate the original input DataFrame."""
        orig_glucose_copy = self.valid_readings["glucose_mg_dl"].tolist()
        what_if_res = self.engine.simulate_what_if(
            self.valid_profile,
            self.valid_readings,
            hypothetical_delta_glucose=-25.0,
            hypothetical_delta_steps=400,
            scenario_description="Test 20-min Post-Meal Walk"
        )
        # Original DataFrame must be exactly unaltered
        self.assertEqual(
            self.valid_readings["glucose_mg_dl"].tolist(),
            orig_glucose_copy,
            "Source DataFrame was mutated by what-if simulation!"
        )
        self.assertTrue(what_if_res["is_hypothetical_simulation"])
        self.assertIn("HYPOTHETICAL SIMULATION NOTICE", what_if_res["simulation_notice"])


if __name__ == "__main__":
    unittest.main()
