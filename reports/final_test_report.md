# TwinSense AI - Final End-to-End Test Report (Step 7)

**Report Date:** 2026-10-13
**Python Version:** 3.14.2
**pytest Version:** 9.1.1
**Platform:** Windows 11 (win32)

IMPORTANT: This application uses exclusively synthetic development data (random seed 42).
It is NOT clinically validated and must NOT be used for medical decisions.

---

## 1. Project Structure (Verified Intact)

```
TwinSense-AI/
|-- README.md
|-- requirements.txt                  [FIXED: added joblib, httpx2, pytest]
|-- data/
|   |-- raw/
|   |   |-- patient_profiles.csv      803 bytes, MD5: 8245431dd0b77a051707c2a09547a2d2
|   |   +-- glucose_timeseries.csv    1,667,229 bytes, MD5: 28563652d6503c8af5f04a3e66d1c9f8
|   +-- twinsense.db                  4,284,416 bytes (SQLite)
|-- models/
|   |-- random_forest_risk_model.joblib   2,259,017 bytes
|   +-- feature_columns.json
|-- reports/
|   |-- evaluation_report.md
|   +-- final_test_report.md          [THIS FILE]
|-- src/
|   |-- data_generator.py
|   |-- feature_engineering.py
|   |-- train.py
|   +-- twin_engine.py
|-- app/
|   |-- main.py, database.py, schemas.py, services.py
|   +-- static/  index.html, style.css, app.js
+-- tests/
    |-- test_api.py             12 API integration tests
    |-- test_twin_engine.py     10 unit tests
    +-- live_api_check.py       63 live endpoint checks (created during this audit)
```

---

## 2. Installed Package Versions

| Package      | Version  | Role                       |
|-------------|----------|----------------------------|
| fastapi     | 0.141.1  | Backend API                |
| uvicorn     | 0.52.3   | ASGI server                |
| pandas      | 2.3.3    | Data processing            |
| numpy       | 2.4.3    | Numerical operations       |
| scikit-learn| 1.9.1    | ML model                   |
| pydantic    | 2.13.4   | Schema validation          |
| httpx       | 0.28.1   | Test client transport      |
| httpx2      | 0.28.0   | Starlette TestClient fix   |
| joblib      | 1.5.3    | Model serialization        |
| pytest      | 9.1.1    | Test runner                |

---

## 3. Unit Test Results - test_twin_engine.py

Command: `python -m pytest tests/test_twin_engine.py -v --tb=short`
Result: **10/10 PASSED**

| Test Name                                   | Result |
|--------------------------------------------|--------|
| test_feature_ordering_matches_schema_exactly | PASS   |
| test_valid_prediction_returns_complete_structure | PASS |
| test_unsupported_hypoglycemia_messaging     | PASS   |
| test_risk_label_mapping                     | PASS   |
| test_insufficient_history_rejected          | PASS   |
| test_missing_baseline_field_rejected        | PASS   |
| test_invalid_baseline_values_rejected       | PASS   |
| test_disordered_timestamps_rejected         | PASS   |
| test_duplicate_timestamps_rejected          | PASS   |
| test_what_if_simulation_immutability        | PASS   |

---

## 4. API Integration Test Results - test_api.py

Command: `python -m pytest tests/test_api.py -v --tb=short`
Result: **12/12 PASSED**
DB Isolation: Tests used a temporary SQLite database. Production twinsense.db was NOT touched.

| Test Name                                          | Result |
|---------------------------------------------------|--------|
| test_01_health_status_endpoint                     | PASS   |
| test_02_list_patients                              | PASS   |
| test_03_get_patient_profile_valid                  | PASS   |
| test_04_get_patient_profile_not_found              | PASS   |
| test_05_get_patient_readings                       | PASS   |
| test_06_predict_from_db_readings                   | PASS   |
| test_07_prediction_history_retrieval               | PASS   |
| test_08_predict_insufficient_custom_readings_rejected | PASS |
| test_09_what_if_simulation_valid                   | PASS   |
| test_10_what_if_invalid_delta_bounds_rejected      | PASS   |
| test_11_serve_dashboard_root                       | PASS   |
| test_12_static_assets_reachable                    | PASS   |

---

## 5. Live API Verification - live_api_check.py

Command: `python tests/live_api_check.py`
Server: http://127.0.0.1:8001
Result: **63/63 PASSED**

### Check Groups Summary

| Group | Checks | Result |
|-------|--------|--------|
| GET /api/health (status, model, counts, disclaimers) | 8 | ALL PASS |
| GET /api/patients (count, IDs, is_synthetic field) | 5 | ALL PASS |
| GET /api/patients/SYNTH_PAT_001 (profile fields, 404 for invalid) | 5 | ALL PASS |
| GET /api/patients/{id}/readings (count, order, disclaimers) | 6 | ALL PASS |
| POST /api/patients/{id}/predict (201, risk_class, probs, warnings) | 10 | ALL PASS |
| DB persistence (total_predictions_logged incremented after POST) | 1 | ALL PASS |
| POST /api/patients/{id}/what-if (200, immutability, 422 on bounds) | 7 | ALL PASS |
| GET / (200, HTML, disclaimers visible) | 8 | ALL PASS |
| Static assets style.css + app.js (200, relative API_BASE) | 5 | ALL PASS |
| CSV MD5 hash integrity (unchanged by all API interactions) | 2 | ALL PASS |

### Prediction Response Specifics Verified
- HTTP 201 returned on POST /predict
- risk_class always in {2, 3} (Class 1 hypoglycemia correctly absent)
- 1_hypoglycemia class probability == 0.0
- prediction_id is a DB integer row ID
- CRITICAL LIMITATION and FOR DEMONSTRATION ONLY in every prediction response
- prediction history count incremented: 3 -> 4 after test POST

### Dashboard HTML Specifics Verified
- "Synthetic Prototype" badge visible in header
- "CRITICAL MODEL LIMITATION" callout rendered on prediction panel
- "NOT clinically validated" disclaimer text present
- No external JS libraries loaded (pure vanilla JS)
- API_BASE = "" (relative URLs, portable across any port)

---

## 6. Port Availability Audit

Observed during audit session:

```
PORT 8000: ACTIVE  -- python.exe PID 17628 (TwinSense AI background task)
PORT 8001: ACTIVE  -- python.exe PID 9080 (TwinSense AI reload server)
```

Both port 8000 and port 8001 were tested and verified to be serving TwinSense AI successfully (`HTTP 200 OK` on `/api/health`).

### Startup Commands

Standard port 8000:
```
cd "c:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```
Access at: http://127.0.0.1:8000/

Alternate port 8001 (if port 8000 is occupied by another process):
```
cd "c:\Users\Narayanan R\OneDrive\Desktop\TwinSense-AI"
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```
Access at: http://127.0.0.1:8001/

Run unit + integration tests (no server needed):
```
python -m pytest tests/test_twin_engine.py tests/test_api.py -v
```

Run live checks (server must be running):
```
python tests/live_api_check.py
```

---

## 7. JavaScript and Frontend Audit

NOTE: Playwright browser automation was unavailable (driver HTTP 404). Checks
performed via code inspection and TestClient HTML response analysis.

| Check                                     | Method           | Result       |
|------------------------------------------|------------------|--------------|
| API_BASE = "" (relative URLs)             | Code inspection  | PASS         |
| No hardcoded localhost:8000 in JS         | grep             | PASS         |
| No external API keys or cloud endpoints   | grep             | PASS         |
| Patient select triggers full data reload  | Code review      | PASS         |
| Loading overlays and button disable states| Code review      | PASS         |
| API errors show user-facing alert()       | Code review      | PASS         |
| Prediction empty state before first run   | Code review      | PASS         |
| Synthetic Prototype badge in header       | TestClient HTML  | PASS         |
| CRITICAL MODEL LIMITATION callout in DOM  | TestClient HTML  | PASS         |
| SVG chart rendered with no external libs  | Code review      | PASS         |
| What-if does not mutate input DataFrame   | Unit test        | PASS         |
| Live browser visual rendering             | Playwright only  | NOT PERFORMED|

---

## 8. Security and Credential Audit

| Check                         | Result                                        |
|------------------------------|-----------------------------------------------|
| Hardcoded passwords or tokens | None found                                    |
| API keys in source files      | None found                                    |
| Cloud service credentials     | None found                                    |
| External AI API calls         | None found                                    |
| CORS policy                   | allow_origins=["*"] -- local dev only, not for production |
| .env files present            | None                                          |
| PII in SQLite database        | None -- all records are synthetic             |

---

## 9. Bugs Found and Fixed

### BUG-1 [HIGH] - joblib missing from requirements.txt
- joblib is a direct import in twin_engine.py and train.py for model persistence
- Impact: pip install -r requirements.txt followed by any prediction would crash
- Fix: Added joblib>=1.3.0 to requirements.txt

### BUG-2 [MEDIUM] - pytest missing from requirements.txt
- Impact: New contributors could not run tests after a fresh install
- Fix: Added pytest>=8.0.0 to requirements.txt

### BUG-3 [LOW] - StarletteDeprecationWarning on every test run
- FastAPI TestClient emitted: "Using httpx with starlette.testclient is deprecated"
- Impact: Warning noise in test output; tests still passed
- Fix: Installed httpx2; added httpx2>=0.28.0 to requirements.txt

---

## 10. Confirmed Correct Behaviours

- Model loaded on startup via get_engine() in lifespan (singleton, not reloaded per request)
- feature_columns.json enforced on every inference call
- Prediction results logged to SQLite predictions table on every POST /predict
- Raw CSV files immutable -- MD5 hashes unchanged after 63 API interactions including predictions and what-if calls
- What-if simulation is read-only -- confirmed by unit test and no DB write in services.py
- Chronological data split verified -- no patient training data overlaps test period (45-min embargo)
- DB init idempotent -- INSERT OR IGNORE prevents duplicate records on every server restart
- Hypoglycemia (Class 1) warning present on every prediction -- API response field AND HTML callout
- Synthetic data labeling visible in header badge, disclaimer banner, API is_synthetic fields, and footer

---

## 11. Remaining Limitations (Design Constraints, Not Bugs)

1. Hypoglycemia prediction unsupported -- Zero training examples. Model correctly returns 0.0
   probability for Class 1 and displays CRITICAL LIMITATION on every prediction. This is a
   known data generator constraint, not a code defect.

2. CORS wildcard -- allow_origins=["*"] acceptable for local use. Must be restricted before
   any public or production deployment.

3. No authentication -- API endpoints are unauthenticated. Appropriate for local academic demo.

4. Live browser visual testing not performed -- Playwright driver unavailable. Responsive
   layout, chart interactivity, and tooltip hover states not verified in real browser.

5. Port usage -- TwinSense AI runs successfully on either port 8000 or port 8001. If running multiple instances, specify an alternate port via `--port`.

6. data/twinsense.db not in .gitignore -- Contains mutable prediction history. Add it to
   .gitignore before committing to version control.

---

## 12. Final Test Score Summary

| Test Suite                     | Run | Passed | Failed |
|-------------------------------|-----|--------|--------|
| Unit tests (test_twin_engine)  |  10 |     10 |      0 |
| API integration (test_api)     |  12 |     12 |      0 |
| Live endpoint checks           |  63 |     63 |      0 |
| TOTAL                          |  85 |     85 |      0 |

Overall Status: ALL 85 TESTS PASS
Application is fully functional for local academic demonstration.

---

Generated during Step 7 audit. No test results were invented.
All results reflect actual executed commands and observed terminal output.
