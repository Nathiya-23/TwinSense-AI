# TwinSense AI - Model Training & Evaluation Report

**Generated Date:** 2026-10-13 20:26:06  
**Model Architecture:** Random Forest Classifier (`n_estimators=100`, `max_depth=8`)  
**Baseline Model:** Dummy Classifier (`strategy="most_frequent"`)  

---

## ⚠️ Important Scientific & Ethical Disclaimer
This evaluation reflects performance **strictly on synthetic development data** generated via mathematical heuristic simulations. 
- It does **not** demonstrate real-world human clinical accuracy.
- It is **not** validated for clinical decision-making or therapy adjustment.
- Real continuous glucose dynamics involve biological mechanisms (e.g., insulin absorption kinetics, gastroparesis, counter-regulatory hormone secretions) not captured in this prototype.

---

## 1. Dataset Partitioning & Time-Series Embargo
To prevent lookahead bias and data leakage, data was split **chronologically per patient** rather than randomly shuffled:
- **Training Partition (80% chronological history):** 16,010 records
- **Test Partition (Final 20% chronological history):** 3,920 records
- **Embargo Dropped (Boundary Buffer):** 90 records (45 minutes / 9 steps per patient)
- **Leakage Verification:** 100% verified. Every patient's training observations end at least 45 minutes before their test period begins.

---

## 2. Target Class Distribution & Critical Observation

| Class | Description | Train Set Count (Share) | Test Set Count (Share) |
| :--- | :--- | :--- | :--- |
| **Class 1** | Hypoglycemia (<70 mg/dL) | **0 (0.00%)** | **0 (0.00%)** |
| **Class 2** | In-Range (70-180 mg/dL) | 6,653 (41.56%) | 1,756 (44.80%) |
| **Class 3** | Hyperglycemia (>180 mg/dL) | 9,357 (58.44%) | 2,164 (55.20%) |

### ⚠️ Critical Finding Regarding Hypoglycemia (Class 1)
- **Observed Limitation:** Class 1 (Hypoglycemia) contains **0 examples** in both the training set and the test set.
- **Root Cause:** The synthetic data generator was configured with baseline patient HbA1c values ($6.7\% - 10.0\%$) and standard meal spikes, causing glucose to fluctuate strictly within normal and hyperglycemic ranges.
- **Consequence:** The model **cannot learn or predict hypoglycemia** from this current training dataset. It is currently operating as a binary classifier between In-Range (Class 2) and Hyperglycemia (Class 3).
- **Recommended Next Step for Synthetic Generator:** Introduce acute downward glucose perturbations in `src/data_generator.py`—such as simulated insulin over-bolusing, delayed/skipped meals, or intense prolonged physical exercise—to synthesize realistic hypoglycemia episodes before retraining.

---

## 3. Baseline vs. Random Forest Performance (Test Set)

| Metric | Dummy Baseline (Most Frequent) | Random Forest Classifier | Delta Improvement |
| :--- | :--- | :--- | :--- |
| **Overall Accuracy** | 55.20% | **89.29%** | **++34.08%** |
| **Macro F1-Score** | 0.3557 | **0.8917** | **++0.5360** |

---

## 4. Per-Class Detailed Classification Report (Random Forest)

| Class | Precision | Recall | F1-Score | Support |
| :--- | :--- | :--- | :--- | :--- |
| **Class 1 (Hypoglycemia)** | 0.0000 | 0.0000 | 0.0000 | 0 |
| **Class 2 (In-Range)** | 0.8800 | 0.8810 | 0.8805 | 1756 |
| **Class 3 (Hyperglycemia)** | 0.9033 | 0.9025 | 0.9029 | 2164 |

---

## 5. Confusion Matrix (Untouched Chronological Test Set)

*Labels: [Class 1: Hypo, Class 2: In-Range, Class 3: Hyper]*

```text
Actual \ Predicted     Hypo (1)    In-Range (2)   Hyper (3)
Hypo (1)                 0            0              0
In-Range (2)             0            1547           209
Hyper (3)                0            211            1953
```

---

## 6. Top Feature Importances (Random Forest)

```text
{
  "current_glucose_mg_dl": 0.3094,
  "glucose_mean_past_15m": 0.2348,
  "glucose_mean_past_30m": 0.201,
  "baseline_hba1c": 0.1512,
  "bmi": 0.0321,
  "diabetes_duration_years": 0.0222,
  "steps_sum_past_15m": 0.0129,
  "age": 0.0123,
  "glucose_change_past_15m": 0.0113,
  "heart_rate_mean_past_15m": 0.0113,
  "current_meal_event": 0.0014
}
```

---

## 7. Artifacts Saved
- **Model Binary:** `C:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI\models\random_forest_risk_model.joblib`
- **Feature Schema:** `C:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI\models\feature_columns.json`
- **Evaluation Report:** `C:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI\reports\evaluation_report.md`
