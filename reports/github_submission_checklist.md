# TwinSense AI — GitHub Submission Readiness Checklist

**Document Version:** 1.0.0  
**Audit Date:** October 2026  
**Repository Path:** `C:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI`  
**Target Environment:** Public GitHub Repository  

---

## 1. Executive Summary

This audit checklist certifies the readiness of **TwinSense AI** (Healthcare Digital Twin Prototype) for public GitHub publication. All files, dependencies, documentation, data schemas, and safety guardrails have been audited against open-source best practices, security standards, and academic demonstration requirements.

| Audit Category | Status | Notes |
| :--- | :---: | :--- |
| **Files & Repository Structure** | ✅ PASSED | Clean modular structure; all essential files present |
| **Sensitive Data & Secrets** | ✅ PASSED | Zero API keys, passwords, or PII detected; 100% synthetic |
| **Local File Exclusion (.gitignore)** | ✅ PASSED | Caches, runtime SQLite DB, and OS files excluded |
| **Dependency Integrity** | ✅ PASSED | Minimal, compatible, verified via AST scan and `pip check` |
| **README & Setup Instructions** | ✅ PASSED | Step-by-step PowerShell commands verified against repo |
| **Model & Clinical Disclaimers** | ✅ PASSED | Hypoglycemia zero-support and non-clinical status disclosed |
| **License Status** | ✅ PASSED | MIT License established and created at repository root |

---

## 2. Inventory: Files Intended for GitHub

The following 29 files comprise the complete project codebase and are intended to be tracked in Git and published to GitHub:

| File Path | Approximate Size | Category | Description / Purpose |
| :--- | :---: | :--- | :--- |
| [README.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/README.md) | ~25 KB | Documentation | Root project guide, architecture, setup, and disclaimers |
| [LICENSE](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/LICENSE) | ~1 KB | Legal | Standard MIT Open Source License agreement |
| [.gitignore](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/.gitignore) | ~700 B | Configuration | Git exclusion rules for Python, DBs, caches, and IDEs |
| [requirements.txt](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/requirements.txt) | ~200 B | Configuration | Pinned minimum dependencies for runtime and testing |
| [data/raw/patient_profiles.csv](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/data/raw/patient_profiles.csv) | ~800 B | Dataset | Baseline clinical profiles for 10 synthetic patients |
| [data/raw/glucose_timeseries.csv](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/data/raw/glucose_timeseries.csv) | ~1.59 MB | Dataset | 20,160 rows of 5-min continuous glucose & activity data |
| [data/processed/training_dataset.csv](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/data/processed/training_dataset.csv) | ~2.82 MB | Dataset | 20,020 leak-free engineered feature-target rows |
| [models/feature_columns.json](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/models/feature_columns.json) | ~320 B | Artifact | Schema list of 11 exact input feature column names |
| [models/random_forest_risk_model.joblib](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/models/random_forest_risk_model.joblib) | ~2.15 MB | Artifact | Serialized trained Random Forest classifier (depth 8) |
| [src/data_generator.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/src/data_generator.py) | ~15 KB | Source Code | Deterministic multi-patient synthetic physiology generator |
| [src/feature_engineering.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/src/feature_engineering.py) | ~16 KB | Source Code | Past-only rolling window aggregations and EHR merging |
| [src/train.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/src/train.py) | ~19 KB | Source Code | Model training, chronological split, 45m embargo |
| [src/twin_engine.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/src/twin_engine.py) | ~15 KB | Source Code | Digital Twin inference engine and what-if simulation |
| [app/main.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/main.py) | ~8 KB | Backend | FastAPI application, CORS middleware, lifespan events |
| [app/database.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/database.py) | ~6 KB | Backend | SQLite connection management and idempotent CSV loader |
| [app/schemas.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/schemas.py) | ~5 KB | Backend | Pydantic v2 data models for API requests and responses |
| [app/services.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/services.py) | ~8 KB | Backend | Database query layer and prediction persistence service |
| [app/static/index.html](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/static/index.html) | ~22 KB | Frontend | Semantic HTML5 dashboard, clinical theme, SVG chart |
| [app/static/style.css](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/static/style.css) | ~21 KB | Frontend | Responsive CSS3 styles, glassmorphism, risk indicators |
| [app/static/app.js](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/app/static/app.js) | ~27 KB | Frontend | Vanilla JavaScript controller, native SVG chart renderer |
| [tests/test_twin_engine.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/tests/test_twin_engine.py) | ~7 KB | Testing | 10 unit tests for TwinEngine logic, bounds, and immutability |
| [tests/test_api.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/tests/test_api.py) | ~9 KB | Testing | 12 integration tests using isolated temporary SQLite DB |
| [tests/live_api_check.py](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/tests/live_api_check.py) | ~11 KB | Testing | Live HTTP verification against running local server |
| [reports/system_architecture.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/system_architecture.md) | ~12 KB | Report | Technical architecture specification and data flow |
| [reports/system_architecture.mmd](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/system_architecture.mmd) | ~7 KB | Report | Standalone Mermaid diagram source code |
| [reports/evaluation_report.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/evaluation_report.md) | ~5 KB | Report | Detailed model metrics, confusion matrix, limitations |
| [reports/model_evaluation.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/model_evaluation.md) | ~22 KB | Report | Extended comparative evaluation (Random Forest vs Baseline) |
| [reports/final_test_report.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/final_test_report.md) | ~12 KB | Report | Step 8 test execution log (22/22 unit & API checks) |
| [reports/github_submission_checklist.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/github_submission_checklist.md) | This file | Report | GitHub submission audit and pre-flight verification |

---

## 3. Inventory: Files That Must Remain Local

The following files and directories must NOT be committed to Git. They are covered by [.gitignore](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/.gitignore):

| File / Pattern | Reason for Exclusion |
| :--- | :--- |
| `data/twinsense.db` | Local SQLite database (~4.1 MB) containing local runtime session state and prediction logs. It is automatically initialized and seeded idempotently on server startup from raw CSVs. |
| `app/__pycache__/` | Compiled Python bytecode (`.pyc`). Machine-specific and auto-regenerated. |
| `src/__pycache__/` | Compiled Python bytecode (`.pyc`). |
| `tests/__pycache__/` | Compiled Python bytecode (`.pyc`). |
| `.pytest_cache/` | Pytest session cache and node IDs. Local test runner artifact. |
| `.venv/` or `venv/` | Python virtual environments containing local binary wheels and site-packages. |
| `.vscode/` or `.idea/` | User-specific IDE configurations, local breakpoints, and workspace caches. |
| `*.log` | Runtime debug logs generated by server or test runs. |
| `scratch/` | Temporary working scripts or intermediate data dumps. |
| `.env` / `*.key` / `*.pem` | Local environment variables or potential credential files. |

---

## 4. Sensitive-Data Audit & Privacy Verification

A rigorous multi-pass automated scan was executed across all text and code files in the repository:

- [x] **API Keys & Tokens:** Scanned for patterns matching OpenAI (`sk-...`), Google AI (`AIza...`), GitHub tokens (`ghp_...`), AWS credentials, and generic bearer tokens. **Zero matches detected.**
- [x] **Passwords & Secrets:** Scanned for hardcoded `password = "..."`, `secret = "..."`, or private RSA/SSH keys. **Zero matches detected.**
- [x] **Protected Health Information (PHI) & PII:** 
  - Verified `data/raw/patient_profiles.csv`: Contains exactly 10 synthetic patients named `SYNTH_PAT_001` through `SYNTH_PAT_010`.
  - No real human names, dates of birth, social security numbers, email addresses, phone numbers, or clinical facility identifiers are present.
  - Every profile and reading row carries an explicit column `is_synthetic = True` and `data_source = synthetic_simulation_twin_v1`.
- [x] **Network Call Inspection:**
  - Audited `app/static/app.js`: Uses relative base path `const API_BASE = ""` with zero outbound external calls to third-party CDNs, external LLM endpoints, or tracking trackers.
  - Audited `app/main.py`: Local CORS restricted to `localhost` and `127.0.0.1`.
- [x] **File Size Verification:**
  - The largest file to be tracked is `data/processed/training_dataset.csv` (2.82 MB), followed by `models/random_forest_risk_model.joblib` (2.15 MB).
  - All files are well below GitHub's 100 MB hard limit and below the 50 MB soft warning threshold. No Git LFS configuration is strictly required.

---

## 5. README & Setup Reproducibility Audit

The root [README.md](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/README.md) has been reviewed and updated to ensure that any developer cloning the project on Windows can reproduce the entire workflow from scratch:

- [x] **Windows PowerShell Commands:** All commands use standard PowerShell syntax (e.g. `python -m venv .venv`, `.\.venv\Scripts\Activate.ps1`, `python -m pip install -r requirements.txt`).
- [x] **Deterministic Pipeline Flow:**
  1. `python src/data_generator.py` (generates raw CSVs)
  2. `python src/feature_engineering.py` (generates `training_dataset.csv`)
  3. `python src/train.py` (evaluates baseline vs Random Forest, serializes model)
  4. `python -m app.database` (initializes local SQLite tables)
  5. `python -m uvicorn app.main:app --reload` (starts local server on port 8000)
- [x] **Testing Commands Verified:**
  - `python -m pytest` executes 22 automated tests (10 TwinEngine tests + 12 API route tests) in ~26 seconds.
  - `python tests/live_api_check.py` verifies live end-to-end integration when the server is active.
- [x] **API Documentation:** Comprehensive table of all 7 REST endpoints with HTTP methods, paths, and response summaries.
- [x] **Swagger UI Link:** Highlights `http://127.0.0.1:8000/docs` for interactive exploration.

---

## 6. Mandatory Disclosures & Model Limitations

To maintain academic and scientific integrity, the following limitations are explicitly documented in the README, API schemas, and UI headers:

1. **100% Synthetic Data Limitation:**
   - All physiological signals are generated using a simplified mathematical model incorporating circadian baselines, postprandial Gaussian meal curves, and linear step decay.
   - It **does not simulate true endocrinological dynamics** such as subcutaneous insulin absorption kinetics, gastroparesis, counter-regulatory hormone surges (glucagon, epinephrine, cortisol), or acute physiological stress.
2. **Zero Hypoglycemia Support (Class 1):**
   - The synthetic dataset generator produced zero readings below 70 mg/dL across all 20,160 readings because simulated patients had moderate-to-high baseline HbA1c ($6.7\% - 10.0\%$) and regular meal schedules without insulin over-bolusing.
   - As an honest empirical consequence, the trained Random Forest classifier **has zero training and evaluation support for Class 1 (Hypoglycemia)** and currently operates as a binary classifier (In-Range vs Hyperglycemia).
   - This limitation is prominently surfaced in the frontend UI, API responses (`hypoglycemia_limitation`), and technical reports.
3. **Medical Safety Disclaimer:**
   - TwinSense AI is an educational student research prototype. It is **not clinically approved by the FDA, CE, CDSCO, or any regulatory body**.
   - It must never be used for diagnosis, clinical management, or calculating insulin dosages.

---

## 7. Remaining Pre-Publishing Checklist (User Action Items)

Before publishing to GitHub, the repository maintainer should perform the following sequence:

- [x] **Step 1: Open-Source License Established**
  - Selected: **MIT License** (permits academic reuse, explicitly disclaims warranty and liability).
  - Status: Generated at [LICENSE](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/LICENSE).
- [ ] **Step 2: Initialize Git Repository (if not already done)**
  ```powershell
  cd "C:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI"
  git init
  ```
- [ ] **Step 3: Verify Ignored Files**
  ```powershell
  git status
  ```
  *Confirm that `data/twinsense.db`, `__pycache__`, and `.pytest_cache` are NOT listed in untracked files.*
- [ ] **Step 4: Stage and Create Initial Commit**
  ```powershell
  git add .
  git commit -m "feat: initial commit of TwinSense AI healthcare digital twin prototype"
  ```
- [ ] **Step 5: Link GitHub Remote & Push**
  ```powershell
  git branch -M main
  git remote add origin https://github.com/<your-username>/TwinSense-AI.git
  git push -u origin main
  ```

---

*Checklist compiled and verified for TwinSense AI — Ready for final pre-flight review.*
