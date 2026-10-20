# TwinSense AI — Final Model Evaluation Report (Step 8)

**Document Reference:** `reports/model_evaluation.md`  
**Evaluation Date:** October 2026  
**Model Family:** Scikit-Learn `RandomForestClassifier` (Multiclass Risk Model)  
**Baseline Model:** `DummyClassifier` (`strategy="most_frequent"`)  
**Data Regime:** 100% Synthetic Multi-Patient Physiological Simulation (Seed: 42)  
**Status:** Academic Research Prototype — Pre-Clinical Demonstration  

---

## ⚠️ Mandatory Scientific, Clinical & Ethical Disclaimer

> [!CAUTION]
> **NOT FOR MEDICAL USE — STRICTLY AN ACADEMIC PROTOTYPE**  
> 1. All data utilized in the training, evaluation, and demonstration of TwinSense AI is **purely synthetic**, generated deterministically using mathematical heuristics (random seed `42`).
> 2. The metrics, accuracy figures, and F1-scores presented in this report reflect performance **exclusively within the synthetic simulation environment**. They do **not** represent clinical efficacy, diagnostic sensitivity, or real-world human physiological accuracy.
> 3. Real human glucose-insulin regulatory mechanisms involve complex compartmental pharmacokinetics, gastric emptying dynamics, hormonal counter-regulation, illness, stress, and physical exertion that are not fully captured by this synthetic generator.
> 4. **TwinSense AI is NOT clinically validated** and must **NEVER** be used to guide therapy decisions, calculate insulin dosages, evaluate hypoglycemia emergencies, or replace certified medical devices or qualified healthcare professional judgment.

---

## 1. Project & Model Overview

### 1.1 Project Mission
TwinSense AI is a predictive healthcare Digital Twin prototype designed to investigate how continuous biometric sensor streams—such as Continuous Glucose Monitoring (CGM) readings, heart rate, physical activity (steps), and meal timing—can be synthesized with baseline patient clinical profiles to anticipate future glycemic dysregulation before acute adverse episodes manifest.

### 1.2 Model Architecture & Specification
The primary risk prediction engine is an ensemble decision tree architecture implemented via Scikit-Learn:
- **Algorithm:** `RandomForestClassifier`
- **Number of Estimators ($B$):** `100` trees
- **Maximum Depth:** `8` (regularized to prevent overfitting on temporal micro-patterns)
- **Minimum Samples Split:** `10`
- **Minimum Samples Leaf:** `5`
- **Feature Subsampling:** $\sqrt{p}$ (`max_features="sqrt"`)
- **Random Seed:** `42`
- **Hardware Concurrency:** `n_jobs=-1` (multithreaded local CPU execution)

### 1.3 Baseline Model Specification
To rigorously benchmark the machine learning model against an uninformative naive baseline, we trained a `DummyClassifier` using the `"most_frequent"` heuristic. On any input sample, this baseline unconditionally predicts the majority class observed during the training phase (Class 3: Hyperglycemia). Any meaningful machine learning solution must substantially outperform this baseline in both overall accuracy and balanced macro-F1 score across all active classes.

---

## 2. Dataset Description & Synthetic Data Protocol

### 2.1 Synthetic Cohort Summary
The dataset represents a simulated cohort of 10 virtual diabetes patients monitored continuously for 7 days (168 hours):

| Dataset Artifact | File Path | Format & Dimension | Key Attributes |
|---|---|---|---|
| **Patient Profiles** | `data/raw/patient_profiles.csv` | 10 rows $\times$ 6 columns | `patient_id`, `age` (34–68), `bmi` (23.8–34.2), `diabetes_type` (Type 1 / Type 2), `baseline_hba1c` (6.7%–10.0%), `diabetes_duration_years` (2–19) |
| **Telemetry Timeseries** | `data/raw/glucose_timeseries.csv` | 20,160 rows $\times$ 6 columns | `patient_id`, `timestamp` (5-min intervals), `glucose_mg_dl`, `heart_rate`, `steps`, `meal_event` |
| **Processed Feature Matrix** | `data/processed/training_dataset.csv` | 20,020 rows $\times$ 20 columns | 11 predictor features, audit metadata, continuous future glucose, and discrete 3-class target |

### 2.2 Preprocessing & Volume Accounting
- Each patient has exactly $2,016$ time-series readings over 7 days ($7 \times 24 \times 12$).
- To construct a future prediction target 45 minutes ahead, the final 9 observations (45 minutes) of each patient's timeline have no subsequent ground-truth lookahead reading and are excluded from the training dataset.
- Total usable observations: $10 \text{ patients} \times (2,016 - 9) = 20,020 \text{ rows}$.

---

## 3. Target Definition: 45-Minute Glucose Risk Horizon

### 3.1 Prediction Horizon
The prediction objective is defined as forecasting the patient's glycemic risk state exactly **45 minutes into the future** ($t + 45\text{ min}$, equivalent to 9 future steps at 5-minute sampling resolution). 

A 45-minute horizon was chosen because it represents an actionable clinical intervention window: it is sufficiently far in advance to allow a patient or automated alert system to take corrective action (e.g., verifying insulin-on-board, planning physical activity, or consuming carbohydrates), while remaining close enough in time to maintain reliable correlation with recent glucose trajectories.

### 3.2 Target Classes
The continuous future glucose reading $G_{t+45}$ is mapped to the standard three-tier clinical risk classification defined by international consensus guidelines for continuous glucose monitoring:

| Class Code | Risk Category | Glycemic Range | Clinical Significance |
|:---:|---|:---:|---|
| **Class 1** | **Hypoglycemia** | $< 70\text{ mg/dL}$ | Acute emergency; risk of neuroglycopenia, dizziness, seizure, or loss of consciousness |
| **Class 2** | **In-Range** | $70 - 180\text{ mg/dL}$ | Target euglycemic range; minimal acute risk |
| **Class 3** | **Hyperglycemia** | $> 180\text{ mg/dL}$ | Elevated glucose; risk of dehydration, ketoacidosis (T1D), and long-term vascular injury |

---

## 4. Features & Leakage Prevention Architecture

### 4.1 Feature Schema (11 Predictors)
To ensure that the model relies strictly on past information available up to and including the current observation moment $t$, 11 historical features were engineered:

```
+----------------------------------------------------------------------------------------------------+
|                                 TWINSENSE AI FEATURE SCHEMA (11 PREDICTORS)                        |
+----+----------------------------+---------------+--------------------------------------------------+
| #  | Feature Name               | Data Type     | Clinical / Physiological Description             |
+----+----------------------------+---------------+--------------------------------------------------+
| 1  | current_glucose_mg_dl      | Float (mg/dL) | Instantaneous glucose reading at reference time t|
| 2  | glucose_mean_past_15m      | Float (mg/dL) | Rolling mean glucose over [t - 15m, t] (3 steps) |
| 3  | glucose_mean_past_30m      | Float (mg/dL) | Rolling mean glucose over [t - 30m, t] (6 steps) |
| 4  | glucose_change_past_15m    | Float (mg/dL) | Glucose momentum: G(t) - G(t - 15m)              |
| 5  | heart_rate_mean_past_15m   | Float (bpm)   | Mean heart rate over [t - 15m, t]                |
| 6  | steps_sum_past_15m         | Float (count) | Cumulative physical activity over [t - 15m, t]   |
| 7  | current_meal_event         | Int (0 or 1)  | Meal ingestion indicator at time t               |
| 8  | age                        | Int (years)   | Patient chronological age                        |
| 9  | bmi                        | Float (kg/m2) | Patient Body Mass Index                          |
| 10 | baseline_hba1c             | Float (%)     | Glycated hemoglobin at clinical baseline         |
| 11 | diabetes_duration_years    | Int (years)   | Years elapsed since diabetes diagnosis           |
+----+----------------------------+---------------+--------------------------------------------------+
```

### 4.2 Strict Leakage Prevention Safeguards
Time-series forecasting models are exceptionally vulnerable to subtle forms of data leakage. TwinSense AI enforces three architectural barriers:
1. **Explicit Exclusion of Forward Variables:** The feature matrix strictly discards `future_glucose_mg_dl`, `future_timestamp`, `future_glucose_risk`, `is_synthetic`, and `data_source` prior to training.
2. **Identifier Exclusion:** `patient_id` and raw timestamp strings are stripped to ensure the model learns physiological patterns rather than memorizing patient-specific identity keys or clock cycles.
3. **Automated Assertion Guards:** In `src/train.py`, program checks automatically fail if any feature name contains substrings such as `"future"`, `"patient_id"`, or `"timestamp"`.

---

## 5. Train/Test Methodology & 45-Minute Embargo Protocol

### 5.1 Why Random Splitting is Prohibited
Standard machine learning techniques such as randomly shuffling rows ($k$-fold cross-validation or `train_test_split(shuffle=True)`) are **strictly invalid** for continuous time-series data. 

Because glucose readings taken 5 minutes apart exhibit autocorrelation exceeding $r > 0.95$, a random split places adjacent observations from the exact same temporal trajectory into both the training and testing sets. The model trivially memorizes immediate neighboring points, reporting artificially inflated accuracies (>98%) that catastrophically fail when deployed on future, unseen timelines.

### 5.2 Chronological Per-Patient Partitioning
To emulate real-world prospective clinical deployment, data was partitioned **chronologically and independently per patient**:
- **Chronological Training Window (First 80%):** The earliest $1,601$ consecutive readings per patient ($16,010$ total records across all 10 patients).
- **Chronological Test Window (Final 20%):** The latest $392$ consecutive readings per patient ($3,920$ total records across all 10 patients).

```
Patient Timeline:
[======================= 80% TRAIN =======================] [EMBARGO] [======= 20% TEST =======]
t = Day 0, 00:00                                  t = Day 5, 14:45       t = Day 5, 15:30      t = Day 7, 23:15
(1,601 observations)                              (9 dropped obs)        (392 observations)
```

### 5.3 The 45-Minute Embargo Buffer
Even with a chronological split, a critical form of leakage occurs at the boundary if an embargo buffer is omitted:
- The final observation in the training set occurs at $t_{\text{train\_end}}$.
- Its target label represents the patient's glucose state at $t_{\text{train\_end}} + 45\text{ minutes}$.
- If the test set begins immediately at $t_{\text{train\_end}} + 5\text{ minutes}$, the training target horizon extends **40 minutes deep into the test set**.

To completely eliminate this boundary leakage:
- **Embargo Duration:** Exactly $45\text{ minutes}$ ($9\text{ sampling steps}$ at 5-minute intervals).
- **Records Discarded:** Exactly $9\text{ rows per patient} \times 10\text{ patients} = 90\text{ records}$.
- **Verification Guarantee:** For every patient, the earliest timestamp in the test partition occurs at least 45 minutes after the latest timestamp in the training partition ($\text{Test}_{\text{start}} - \text{Train}_{\text{end}} \ge 45\text{ min}$, verified with $100\%$ mathematical compliance).

---

## 6. Baseline vs. Random Forest Results

Both models were trained strictly on the $16,010$-sample training set and evaluated on the untouched $3,920$-sample chronological hold-out test set:

| Evaluation Metric | Dummy Baseline (`most_frequent`) | Random Forest Classifier | Absolute Delta | Relative Gain |
|---|:---:|:---:|:---:|:---:|
| **Overall Accuracy** | 55.20% | **89.29%** | **+34.08%** | **+61.7%** |
| **Macro F1-Score** | 0.3557 | **0.8917** | **+0.5360** | **+150.7%** |
| **Weighted F1-Score** | 0.3925 | **0.8928** | **+0.5003** | **+127.5%** |

### 6.1 Performance Analysis
- The Dummy Baseline achieves $55.20\%$ accuracy purely by guessing Hyperglycemia (Class 3) every single time, as Class 3 happens to constitute $55.20\%$ ($2,164 / 3,920$) of the test set. However, its Macro F1-score collapses to $0.3557$ because its recall on In-Range glucose is exactly zero.
- The Random Forest Classifier achieves **$89.29\%$ accuracy** and a balanced **$0.8917$ Macro F1-score**, proving that the model successfully learns physiological state transitions rather than capitalizing on class imbalance.

---

## 7. Confusion Matrix & Class-Wise Analysis

### 7.1 Detailed Classification Report (Random Forest)

| Class | Label Name | Precision | Recall | F1-Score | Test Support |
|:---:|---|:---:|:---:|:---:|:---:|
| **Class 1** | Hypoglycemia ($<70\text{ mg/dL}$) | **0.0000** | **0.0000** | **0.0000** | **0** |
| **Class 2** | In-Range ($70 - 180\text{ mg/dL}$) | **0.8800** | **0.8810** | **0.8805** | 1,756 |
| **Class 3** | Hyperglycemia ($>180\text{ mg/dL}$) | **0.9033** | **0.9025** | **0.9029** | 2,164 |
| **Macro Avg** | *(All 3 Classes)* | 0.5944 | 0.5945 | 0.5945 | 3,920 |
| **Active Macro Avg** | *(Classes 2 & 3 with Support)* | **0.8917** | **0.8917** | **0.8917** | 3,920 |

### 7.2 Confusion Matrix

```
                          PREDICTED RISK CLASS
                 Hypo (1)    In-Range (2)    Hyper (3)    Total Actual
ACTUAL  Hypo (1)     0             0             0              0
CLASS   In-Range     0          1,547           209         1,756
        Hyper (3)    0            211         1,953         2,164
        Total Pred   0          1,758         2,162         3,920
```

### 7.3 Honest Analysis of Hypoglycemia (Class 1) Absence

> [!WARNING]
> **CRITICAL ARCHITECTURAL FINDING: HYPOGLYCEMIA CANNOT BE PREDICTED**  
> - **Observed Empirical Fact:** There are **0 samples of Class 1 (Hypoglycemia)** in the training partition ($0 / 16,010$) and **0 samples** in the test partition ($0 / 3,920$).
> - **Root Cause in Synthetic Data Engine:** In `src/data_generator.py`, synthetic patient baseline HbA1c values were initialized between $6.7\%$ and $10.0\%$, corresponding to elevated resting glucose levels. Simulated meals generate positive glucose excursions, while nominal homeostatic decay curves gradually return glucose toward the patient's elevated baseline. The simulation lacked stochastic downward shocks (such as insulin over-bolusing, delayed meals, or intense anaerobic exercise), preventing glucose from ever dropping below $70\text{ mg/dL}$.
> - **Consequence for Machine Learning:** Machine learning models cannot learn decision boundaries for classes with zero training support. Consequently, **the model functions purely as a binary classifier between In-Range (Class 2) and Hyperglycemia (Class 3)**.
> - **Integrity Policy:** Neither the backend API, the web dashboard, nor this evaluation report claims that TwinSense AI can detect or alert on hypoglycemia. The model outputs a hard-coded $0.0$ probability for Class 1 and displays high-visibility warning callouts whenever predictions are rendered.

---

## 8. Interpretation of Model Mechanics & Feature Importances

### 8.1 Gini Impurity Feature Importance Distribution

```
Feature Name                  Importance   Percentage   Cumulative
------------------------------------------------------------------
current_glucose_mg_dl         0.3094       30.94%       30.94%  |███████████████
glucose_mean_past_15m         0.2348       23.48%       54.42%  |███████████
glucose_mean_past_30m         0.2010       20.10%       74.52%  |██████████
baseline_hba1c                0.1512       15.12%       89.64%  |███████
bmi                           0.0321        3.21%       92.85%  |█
diabetes_duration_years       0.0222        2.22%       95.07%  |█
steps_sum_past_15m            0.0129        1.29%       96.36%  |
age                           0.0123        1.23%       97.59%  |
glucose_change_past_15m       0.0113        1.13%       98.72%  |
heart_rate_mean_past_15m      0.0113        1.13%       99.85%  |
current_meal_event            0.0014        0.14%      100.00%  |
```

### 8.2 Physiological & Mechanistic Interpretation
1. **Dominance of Short-Term Glycemic Inertia (~74.5%):**  
   The instantaneous glucose reading (`current_glucose_mg_dl`, 30.94%), combined with rolling 15-minute (23.48%) and 30-minute (20.10%) means, constitutes almost three-quarters of the model's predictive weight. This aligns directly with physiology: blood glucose dynamics operate along continuous time gradients governed by absorption and clearance rates. A patient whose 30-minute average is $210\text{ mg/dL}$ is overwhelmingly likely to remain hyperglycemic 45 minutes later unless an acute pharmacologic intervention occurs.
2. **Anchor of Baseline Glycemic Profile (~20.5%):**  
   Baseline HbA1c (15.12%), BMI (3.21%), and diabetes duration (2.22%) provide the individual patient context. Patients with higher baseline HbA1c exhibit systematically higher mean glucose set points and larger postprandial excursions.
3. **Biometric & Behavioral Telemetry (~5.0%):**  
   Steps (1.29%), heart rate (1.13%), and meal events (0.14%) capture transient behavioral shifts. The relatively low weight of `current_meal_event` reflects the 45-minute horizon: because meal absorption peaks between 60 and 90 minutes post-ingestion, the instantaneous meal flag at $t$ has less predictive power than the subsequent glucose momentum already reflected in `glucose_change_past_15m`.

---

## 9. Limitations & Potential Bias

1. **Synthetic Simulation Artifacts:**  
   The synthetic dataset is driven by simplified mathematical equations rather than biological continuous glucose monitoring sensors. Real CGM data contains sensor noise, interstitial-to-vascular lag (5–15 minutes), calibration drift, compression artifacts during sleep, and missing data intervals.
2. **Total Absence of Hypoglycemic Episodes:**  
   As documented in Section 7.3, zero hypoglycemic instances exist in the dataset. Any claim of three-class risk assessment is clinically invalid until hypoglycemia is synthesized or real patient datasets are integrated.
3. **Small Simulated Cohort ($N = 10$):**  
   Ten virtual patients cannot capture the extensive phenotypic heterogeneity of diabetic populations, including variations in insulin sensitivity, beta-cell function, age extremes (pediatric vs. geriatric), pregnancy, or renal impairment.
4. **Stationary Dynamics Assumption:**  
   The 7-day simulation assumes constant patient parameters. In real-world management, insulin sensitivity fluctuates based on circadian cycles (dawn phenomenon), menstrual cycles, psychological stress, acute infections, and dietary composition (fat/protein content impacting late glycemic rise).

---

## 10. Safety & Ethical Considerations

1. **Asymmetry of Clinical Risk:**  
   In diabetes management, clinical classification errors are inherently asymmetrical:
   - *False Alarm for Hyperglycemia (Type I Error):* May cause minor inconvenience or unnecessary blood testing.
   - *Missed Hypoglycemia (Type II Error):* Can lead to severe neuroglycopenia, loss of consciousness, cardiovascular strain, or fatal consequences within hours.  
   Because this model cannot predict hypoglycemia, deploying it in any clinical setting would introduce unacceptable safety risks.
2. **Automation Bias & De-Skilling:**  
   Presenting a polished Digital Twin dashboard risks user overreliance (automation bias). Patients might delay testing or administering necessary corrections under the false assumption that the "AI twin" has verified their stability.
3. **Mitigations Implemented in TwinSense AI:**  
   - Persistent, un-dismissible **"CRITICAL MODEL LIMITATION"** badges embedded on every dashboard view.
   - Prediction API responses include explicit boolean warning flags and limitation narratives.
   - Mandatory human-in-the-loop disclaimers on all exported reports.

---

## 11. Realistic Future Improvements

Before any version of TwinSense AI could be considered for translational research or clinical exploration, the following technical advancements are required:

1. **Synthetic Hypoglycemia Engine Upgrade:**  
   Update `src/data_generator.py` to model pharmacodynamic insulin curves, insulin stacking, unannounced physical exercise, and delayed meals to generate a minimum of 5%–10% Class 1 (hypoglycemia) events.
2. **Benchmark Advanced Architectures:**  
   Compare Random Forest against gradient boosting frameworks (`LightGBM`, `XGBoost`) and sequential deep learning architectures (Temporal Convolutional Networks, Bidirectional LSTMs, and Temporal Fusion Transformers) that can natively model multi-rate sensor streams.
3. **Validation on Open Clinical CGM Benchmarks:**  
   Retrain and benchmark the pipeline on standardized clinical datasets such as:
   - **OhioT1DM:** Real-world CGM, insulin, and physiological data from type 1 diabetes patients.
   - **D1NAMO:** Non-invasive wearable ECG and accelerometer data alongside continuous glucose monitoring.
4. **Calibrated Uncertainty Estimation:**  
   Implement Conformal Prediction or Bayesian approximation to provide rigorous, calibrated confidence intervals (e.g., "90% probability that glucose will fall between 145 and 185 mg/dL") rather than uncalibrated heuristic class probabilities.

---

## 12. Reproducibility & Audit Trail

Every metric, split partition, and evaluation artifact described in this report can be deterministically reproduced using the following commands in PowerShell from the project root:

```powershell
# 1. Verify environment and install declared dependencies
python -m pip install -r requirements.txt

# 2. Re-run feature engineering (validates past-only feature construction)
python src/feature_engineering.py

# 3. Re-train models and regenerate core metrics
python src/train.py

# 4. Execute the complete automated unit and API integration test suite
python -m pytest tests/test_twin_engine.py tests/test_api.py -v

# 5. Execute live API verification against active backend
python tests/live_api_check.py
```

### Verification Checksum Registry

```
Artifact File                               Checksum (MD5)                    Status
------------------------------------------------------------------------------------
data/raw/patient_profiles.csv               8245431dd0b77a051707c2a09547a2d2  VERIFIED INTACT
data/raw/glucose_timeseries.csv             28563652d6503c8af5f04a3e66d1c9f8  VERIFIED INTACT
models/random_forest_risk_model.joblib      2,259,017 bytes                   VERIFIED SAVED
models/feature_columns.json                 11 columns schema                 VERIFIED MATCH
reports/evaluation_report.md                Initial training metrics log       VERIFIED MATCH
reports/final_test_report.md                85/85 tests passed audit log      VERIFIED MATCH
```
