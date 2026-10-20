# TwinSense AI: Problem Statement, Technical Scope & Evaluation Summary

**Document Reference:** `docs/problem_statement.md`  
**Project:** TwinSense AI  
**Data Regime:** 100% Synthetic Multi-Patient Simulation  
**Status:** Pre-Clinical Academic Research Prototype  

---

## Problem Statement

People with diabetes experience rapid glucose fluctuations that can lead to hyperglycemia or hypoglycemia. A current glucose reading alone does not show where glucose is heading, which makes early detection of risky changes difficult and delays corrective action.

---

## Proposed Solution

TwinSense AI is a prototype that analyzes recent glucose history to estimate glucose risk 45 minutes ahead using machine learning. Its dashboard visualizes glucose trends, shows class probabilities with contributing factors, and lets users explore hypothetical what-if scenarios on a patient's digital twin.

---

## How It Differs from Existing CGM Alerts

Commercial Continuous Glucose Monitoring (CGM) systems already offer predictive alerts and directional trend indicators that warn patients of impending high or low glucose. TwinSense AI does not claim superior predictive accuracy, clinical utility, or therapeutic benefit over certified medical devices. Rather, its differences are strictly confined to software-level prototype capabilities implemented in its codebase:
1. **Interactive Counterfactual "What-If" Simulation:** An exploratory sandbox that allows users to evaluate hypothetical adjustments (such as simulated changes in recent glucose or physical step counts) on an in-memory telemetry clone without altering actual records.
2. **Explainable Contributing Factors:** An automated explanation panel listing key physiological observations (e.g., 15-minute rate of change, 30-minute rolling glucose average, baseline HbA1c, and recorded meal activity) associated with the prediction.
3. **Displayed Class Probabilities:** Direct visibility into the model's categorical probability distribution across risk classes rather than binary alarm thresholding.
4. **Explicit Uncertainty & Safety Warnings:** Hardcoded state checks that mark predictions as unreliable when sensor history is insufficient, timestamps are disordered, or telemetry values fall outside physiological bounds, paired with persistent safety disclaimers.

---

## Digital Twin

In this codebase, a "digital twin" refers specifically to an in-memory computational representation instantiated by `TwinEngine` (`src/twin_engine.py`) that couples a patient's static clinical profile (age, BMI, baseline HbA1c, diabetes duration) with their recent window of dynamic time-series readings (at least 30 minutes of 5-minute CGM, heart rate, step count, and meal event data). This representation transforms raw telemetry into an 11-dimensional feature vector used by a trained machine learning classifier to estimate categorical risk 45 minutes ahead. Additionally, it provides an isolated, read-only interface (`simulate_what_if`) where hypothetical perturbations can be evaluated on a telemetry copy without mutating baseline data or database records.

---

## Evaluation

### Evaluation Protocol & Provenance
- **Evaluation Command Executed:**  
  ```bash
  python -c "
  import joblib
  from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
  from src.train import load_and_validate_dataset, partition_chronological_with_embargo, TARGET_CLASSES

  df, feature_cols, target_col = load_and_validate_dataset()
  train_df, test_df = partition_chronological_with_embargo(df)
  X_test, y_test = test_df[feature_cols], test_df[target_col]
  model = joblib.load('models/random_forest_risk_model.joblib')
  y_pred = model.predict(X_test)

  print('ACCURACY:', accuracy_score(y_test, y_pred))
  print('MACRO F1:', f1_score(y_test, y_pred, average='macro', zero_division=0))
  print('CONFUSION MATRIX:\n', confusion_matrix(y_test, y_pred, labels=TARGET_CLASSES))
  print('TEST COUNTS:\n', y_test.value_counts())
  print('REPORT:\n', classification_report(y_test, y_pred, labels=TARGET_CLASSES, zero_division=0))
  "
  ```
- **Data Source Files:** `data/processed/training_dataset.csv`, `models/random_forest_risk_model.joblib`, and `reports/evaluation_report.md`.
- **Partitioning Method:** Strict chronological 80/20 per-patient split with an **embargo buffer of 45 minutes (9 consecutive 5-minute samples per patient)** dropped at the partition boundary to eliminate temporal lookahead leakage.
- **Sample Counts:** 16,010 training samples; 3,920 held-out test samples; 90 embargo boundary samples dropped.

### Test Set Class Distribution

| Class Label | Risk Category | Definition | Test Count | Test Share (%) |
| :---: | :--- | :--- | :---: | :---: |
| **Class 1** | Hypoglycemia | $<70\text{ mg/dL}$ | **0** | **0.00%** |
| **Class 2** | In-Range | $70\text{--}180\text{ mg/dL}$ | 1,756 | 44.80% |
| **Class 3** | Hyperglycemia | $>180\text{ mg/dL}$ | 2,164 | 55.20% |
| **Total** | | | **3,920** | **100.00%** |

*Note: The training partition similarly contains 0 Class 1 samples, 6,653 Class 2 samples (41.56%), and 9,357 Class 3 samples (58.44%).*

### Overall Performance on Held-Out Test Set
- **Overall Accuracy:** **89.29%** (`0.892857...`) (vs. unlearned `DummyClassifier` majority-class baseline: 55.20%)
- **Macro F1-Score (Active Classes 2 & 3):** **0.8917** (`0.891695...`)
- **Macro Average F1 (Across All 3 Classes, including Unsupported Class 1):** **0.5945** (due to 0.0 precision/recall on Class 1)

### Per-Class Detailed Performance

| Class | Risk Category | Precision | Recall | F1-Score | Support (Samples) |
| :---: | :--- | :---: | :---: | :---: | :---: |
| **Class 1** | Hypoglycemia ($<70\text{ mg/dL}$) | **0.0000** | **0.0000** | **0.0000** | **0** *(Unsupported)* |
| **Class 2** | In-Range ($70\text{--}180\text{ mg/dL}$) | 0.8800 | 0.8810 | 0.8805 | 1,756 |
| **Class 3** | Hyperglycemia ($>180\text{ mg/dL}$) | 0.9033 | 0.9025 | 0.9029 | 2,164 |

### Confusion Matrix (Held-Out Test Set, N = 3,920)

*Rows indicate Actual Class; Columns indicate Predicted Class:*

```text
Actual \ Predicted      Class 1 (Hypo)   Class 2 (In-Range)   Class 3 (Hyper)
Class 1 (Hypo)                0                   0                  0
Class 2 (In-Range)            0                1,547                209
Class 3 (Hyper)               0                  211              1,953
```

### Critical Statement on Hypoglycemia (Class 1)
Class 1 (hypoglycemia) contains **zero training examples** and **zero test examples** in the synthetic dataset. As a result, all performance metrics (precision, recall, F1-score) for Class 1 are **undefined and unsupported**. In operation, the model functions strictly as a binary classifier between In-Range (Class 2) and Hyperglycemia (Class 3).

---

## Scope and Safety

> [!CAUTION]
> **SYNTHETIC DATA — NOT CLINICALLY VALIDATED.**  
> This prototype must not be used for diagnosis, treatment, insulin dosing, or medical decisions. Hypoglycemia prediction is unsupported because the training dataset contains zero Class 1 examples. A displayed 0% probability does not mean hypoglycemia is impossible or ruled out.

1. **Academic and Educational Scope Only:** TwinSense AI is an engineering proof-of-concept exploring digital twin architecture and time-series feature engineering. It has not received clearance or certification from any health regulatory agency (such as the US FDA, European CE mark, or Indian CDSCO).
2. **No Clinical Guarantees:** Predictions are statistical risk estimates derived from synthetic mathematical formulas. They must never override actual fingerstick or CGM readings, physical symptoms, or professional medical advice.
3. **No Medication or Dosing Guidance:** The system does not compute, recommend, or suggest insulin boluses, basal adjustments, oral medications, or carbohydrate rescue therapies.
4. **Mandatory Reliance on Direct Measurement:** When blood glucose feels abnormal or alarms sound on certified hardware, users must rely on certified diagnostic tools and emergency clinical protocols.

---

## Known Limitations

1. **Exclusively Synthetic Data:** All patient baselines and time-series telemetry were generated using mathematical simulations (`src/data_generator.py`). They do not reproduce true human biological complexity, sensor calibration drift, compression artifacts, skin temperature effects, or acute illnesses.
2. **Complete Absence of Hypoglycemia (Class 1):** Because synthetic generation was parameterized around elevated HbA1c ($6.7\%\text{--}10.0\%$) without simulated insulin over-administration, glucose readings never fell below $70\text{ mg/dL}$. The model cannot detect, alert, or differentiate hypoglycemic risk.
3. **Class Imbalance in Active Categories:** The active dataset is skewed toward Hyperglycemia ($58.44\%$ train, $55.20\%$ test) relative to In-Range ($41.56\%$ train, $44.80\%$ test).
4. **Omission of Pharmacokinetic Insulin Modeling:** The feature engineering and predictive models do not incorporate active insulin-on-board (IOB) kinetics, basal infusion rates, or carbohydrate absorption rates.
5. **Simplified What-If Heuristics:** The counterfactual simulation adjusts only the final observation point linearly (e.g., modifying steps or glucose values) rather than executing multi-compartmental physiological dynamic simulations over time.
6. **No Real-World Prospective Validation:** The model has never been tested against clinical benchmarks (e.g., OhioT1DM or Tidepool datasets) or evaluated in clinical environments.
