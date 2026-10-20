# TwinSense AI — System Architecture Specification

**Document Reference:** `reports/system_architecture.md`  
**Diagram Source:** [reports/system_architecture.mmd](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/system_architecture.mmd)  
**System Classification:** Local-First, Zero-Cloud, Explaining Predictive Digital Twin  
**Data Regime:** 100% Synthetic Multi-Patient Physiological Simulation  

---

## 1. Visual Architecture Diagram

```mermaid
flowchart TB
    %% =========================================================================
    %% STYLING DIRECTIVES
    %% =========================================================================
    classDef offlineBox fill:#1e293b,stroke:#3b82f6,stroke-width:2px,color:#f8fafc;
    classDef runtimeBox fill:#0f172a,stroke:#06b6d4,stroke-width:2px,color:#f8fafc;
    classDef dataStore fill:#334155,stroke:#94a3b8,stroke-width:1.5px,color:#f1f5f9;
    classDef computeNode fill:#1e3a5f,stroke:#38bdf8,stroke-width:1.5px,color:#f8fafc;
    classDef uiNode fill:#0d2847,stroke:#10b981,stroke-width:2px,color:#f8fafc;
    classDef modelNode fill:#431407,stroke:#f97316,stroke-width:2px,color:#ffedd5;
    classDef warningNode fill:#450a0a,stroke:#ef4444,stroke-width:2px,color:#fee2e2;

    %% =========================================================================
    %% SUBGRAPH 1: OFFLINE TRAINING & DATA PIPELINE
    %% =========================================================================
    subgraph OFFLINE_PIPELINE ["PHASE 1: OFFLINE DATA & TRAINING PIPELINE (BATCH EXECUTION)"]
        direction TB

        DGEN["Synthetic Data Generator<br/><code>src/data_generator.py</code><br/><i>Seed: 42, 10 Patients, 7 Days</i>"]:::computeNode
        
        subgraph RAW_DATA ["Raw Synthetic CSV Storage (Local Filesystem)"]
            P_CSV[("<code>data/raw/patient_profiles.csv</code><br/>10 Synthetic Patients"):::dataStore]
            G_CSV[("<code>data/raw/glucose_timeseries.csv</code><br/>20,160 Sensor Readings"):::dataStore]
        end

        FEAT_ENG["Feature Engineering Pipeline<br/><code>src/feature_engineering.py</code><br/><i>11 Past-Only Features, 45m Horizon</i>"]:::computeNode
        
        PROC_CSV[("<code>data/processed/training_dataset.csv</code><br/>20,020 Rows (Leak-Free)"):::dataStore]

        TRAIN_SCRIPT["Model Training & Evaluation<br/><code>src/train.py</code><br/><i>Chronological Split + 45m Embargo</i>"]:::computeNode

        subgraph TRAIN_OUTPUTS ["Persisted Model Artifacts & Evaluation"]
            RF_MODEL[("Random Forest Classifier<br/><code>models/random_forest_risk_model.joblib</code><br/><i>100 Trees, Depth 8</i>"):::modelNode]
            FEAT_JSON[("Feature Schema JSON<br/><code>models/feature_columns.json</code><br/><i>11 Enforced Predictors</i>"):::dataStore]
            EVAL_REP[("Evaluation Reports<br/><code>reports/evaluation_report.md</code><br/><code>reports/model_evaluation.md</code>"):::dataStore]
        end

        DGEN -->|"Deterministic Generation"| P_CSV
        DGEN -->|"Deterministic Generation"| G_CSV
        P_CSV -->|"Join Baseline"| FEAT_ENG
        G_CSV -->|"Rolling Windows"| FEAT_ENG
        FEAT_ENG -->|"Export Processed"| PROC_CSV
        PROC_CSV -->|"Train (80%) / Test (20%)"| TRAIN_SCRIPT
        TRAIN_SCRIPT -->|"Serialize Model"| RF_MODEL
        TRAIN_SCRIPT -->|"Export Schema"| FEAT_JSON
        TRAIN_SCRIPT -->|"Log Metrics"| EVAL_REP
    end

    %% =========================================================================
    %% SUBGRAPH 2: RUNTIME PREDICTION & SIMULATION PIPELINE
    %% =========================================================================
    subgraph RUNTIME_PIPELINE ["PHASE 2: RUNTIME PREDICTION & INTERACTIVE TWIN (LOCAL SERVER)"]
        direction TB

        subgraph FRONTEND ["Client Browser Interface (Vanilla Web Technologies)"]
            DASH_UI["Interactive Dashboard<br/><code>app/static/index.html</code><br/><i>Navy/Teal Theme, SVG Glucose Chart</i>"]:::uiNode
            DASH_JS["Client Controller<br/><code>app/static/app.js</code><br/><i>Relative API_BASE, No External CDN</i>"]:::uiNode
            DASH_CSS["Responsive Styles<br/><code>app/static/style.css</code><br/><i>Modern Glassmorphism & Layout</i>"]:::uiNode
        end

        subgraph BACKEND ["FastAPI Backend (Local ASGI Server: Port 8000 / 8001)"]
            direction TB
            API_MAIN["FastAPI Application Core<br/><code>app/main.py</code><br/><i>Lifespan Manager, Static Serving</i>"]:::computeNode
            API_ROUTER["REST API Endpoints<br/><code>/api/health</code> | <code>/api/patients</code><br/><code>/api/predict</code> | <code>/api/what-if</code>"]:::computeNode
            API_SCHEMAS["Pydantic Schemas<br/><code>app/schemas.py</code><br/><i>Strict Request/Response Validation</i>"]:::computeNode
            API_SERVICES["Database Services<br/><code>app/services.py</code><br/><i>Repository & Query Layer</i>"]:::computeNode
        end

        subgraph STORAGE ["Local Relational Store (SQLite)"]
            SQLITE_DB[("Local SQLite Database<br/><code>data/twinsense.db</code><br/><i>Idempotent Seeding from CSVs</i>"):::dataStore]
            TBL_PAT["Table: <code>patients</code>"]:::dataStore
            TBL_READ["Table: <code>telemetry_readings</code>"]:::dataStore
            TBL_PRED["Table: <code>predictions</code><br/><i>Historical Prediction Audit Log</i>"]:::dataStore
        end

        subgraph ENGINE ["TwinSense AI Engine Core (In-Memory Inference)"]
            TWIN_CORE["TwinEngine Singleton<br/><code>src/twin_engine.py</code><br/><i>Past-Only Windowing & Verification</i>"]:::computeNode
            WHAT_IF["What-If Counterfactual Simulator<br/><i>In-Memory Perturbation (Read-Only)</i>"]:::computeNode
            SAFETY_GUARD["Clinical Safety Guardrails<br/><i>Hypoglycemia Zero-Prob Warning<br/>Synthetic Data Disclaimer Tagging</i>"]:::warningNode
        end

        %% Frontend connections
        DASH_UI <--> DASH_JS
        DASH_UI --- DASH_CSS
        DASH_JS <==>|"HTTP / JSON (REST Requests)"| API_ROUTER

        %% Backend routing & schemas
        API_MAIN --> API_ROUTER
        API_ROUTER --- API_SCHEMAS
        API_ROUTER --> API_SERVICES

        %% Services to SQLite
        API_SERVICES <-->|"Query Patient Profiles & Telemetry"| SQLITE_DB
        API_SERVICES -->|"Log Validated Predictions"| TBL_PRED
        SQLITE_DB --- TBL_PAT
        SQLITE_DB --- TBL_READ
        SQLITE_DB --- TBL_PRED

        %% CSV initial seed to SQLite (idempotent on startup)
        P_CSV -.->|"Idempotent Init (INSERT OR IGNORE)"| SQLITE_DB
        G_CSV -.->|"Idempotent Init (INSERT OR IGNORE)"| SQLITE_DB

        %% Backend to Engine
        API_ROUTER ==>|"Patient History & Baseline"| TWIN_CORE
        API_ROUTER ==>|"Scenario Parameters"| WHAT_IF

        %% Engine to Artifacts
        FEAT_JSON ==>|"Feature Schema Validation"| TWIN_CORE
        RF_MODEL ==>|"scikit-learn predict_proba()"| TWIN_CORE

        %% Engine internal logic
        TWIN_CORE --> WHAT_IF
        TWIN_CORE --> SAFETY_GUARD
        SAFETY_GUARD -->|"Verified Prediction Response"| API_ROUTER
    end

    %% Apply visual classes to major subgraphs
    class OFFLINE_PIPELINE offlineBox;
    class RUNTIME_PIPELINE runtimeBox;
```

---

## 2. Architectural Subsystems Breakdown

### 2.1 Subsystem 1: Offline Training & Data Pipeline
The offline pipeline is executed strictly during batch data preparation and model retraining. It possesses zero dependencies on the live FastAPI web service:
1. **Synthetic Data Engine (`src/data_generator.py`):** Uses mathematical heuristics and fixed pseudo-random seeds (`seed=42`) to produce raw synthetic patient profiles and CGM/sensor readings.
2. **Feature Engineering Engine (`src/feature_engineering.py`):** Ingests raw CSVs, merges patient baselines, extracts rolling historical features over 15-minute and 30-minute past windows, creates the 45-minute forward prediction target, and strips all forward-looking identifiers to export `data/processed/training_dataset.csv`.
3. **Model Training & Evaluation (`src/train.py`):** Executes per-patient chronological splitting, enforces the 45-minute boundary embargo, fits the `RandomForestClassifier`, verifies feature orders, and persists model weights to `models/random_forest_risk_model.joblib` and the schema to `models/feature_columns.json`.

### 2.2 Subsystem 2: Runtime Prediction & Interactive Twin
The live pipeline operates as a local-first, low-latency microservice providing real-time digital twin analytics:
1. **Client Interface (`app/static/`):** Built with semantic HTML5, Vanilla CSS, and pure JavaScript. Displays time-series SVG visualizations, patient phenotype cards, and interactive what-if adjustment controls. Operates via relative API endpoints (`API_BASE = ""`) to remain independent of port configurations.
2. **FastAPI Web Service (`app/main.py`, `app/schemas.py`, `app/services.py`):** Asynchronous ASGI server providing typed endpoints for health checks, patient profiles, continuous telemetry queries, inference execution, and counterfactual simulation.
3. **SQLite Local Store (`data/twinsense.db`):** Stores patient records, telemetry, and append-only prediction audit logs. Seeded idempotently on application startup from the raw synthetic CSVs via `INSERT OR IGNORE`.
4. **TwinSense Engine Core (`src/twin_engine.py`):** In-memory singleton initialized during application startup. Validates inbound feature payloads against `feature_columns.json`, queries the loaded Random Forest model, computes counterfactual what-if deltas without mutating storage, and injects clinical safety disclaimers and zero-probability hypoglycemia guardrails into every output.

---

## 3. Data Flow & Boundary Isolation

| Pipeline Boundary | Data Source | Data Destination | Mutability Policy |
|---|---|---|---|
| **CSV to Processed** | `data/raw/*.csv` | `data/processed/*.csv` | Read-only raw CSVs; regenerated on demand |
| **Processed to Model** | `data/processed/*.csv` | `models/*.joblib`, `*.json` | Training phase only |
| **Startup Seeding** | `data/raw/*.csv` | `data/twinsense.db` | Read-only from CSV; idempotent DB insert |
| **Inference Query** | `app/static/` | `app/main.py` -> `src/twin_engine.py` | Transient memory processing |
| **Audit Logging** | `src/twin_engine.py` | `data/twinsense.db` (`predictions` table) | Append-only insert |
| **What-If Simulation** | `app/static/` | `src/twin_engine.py` | Strictly ephemeral; zero writes to DB or CSV |

---

## 4. How to Export the Mermaid Diagram (PNG / PDF / SVG)

The diagram source is stored as an editable Mermaid document at [reports/system_architecture.mmd](file:///c:/Users/Narayanan%20R/OneDrive/Desktop/TwinSense-AI/reports/system_architecture.mmd). Because automated headless Chromium dependencies (`@mermaid-js/mermaid-cli` / `puppeteer`) are not bundled with local Python environments, use any of the following standard methods to generate high-resolution PNG or PDF files:

### Method 1: Mermaid Live Editor (Zero Installation, Recommended)
1. Open [https://mermaid.live](https://mermaid.live) in any modern browser.
2. Copy the entire contents of `reports/system_architecture.mmd` and paste into the Code editor panel.
3. Click the **Actions** dropdown at the bottom left:
   - Select **Download PNG** (choose 2x or 3x for high-resolution publications).
   - Or select **Download SVG** for vector graphics.
4. Save the downloaded file to `reports/system_architecture.png`.

### Method 2: Mermaid CLI (`@mermaid-js/mermaid-cli`)
If Node.js and Google Chrome / Chromium are available locally:
```powershell
# Install the Mermaid command-line utility globally
npm install -g @mermaid-js/mermaid-cli

# Export to high-resolution PNG (scale factor 3)
mmdc -i reports/system_architecture.mmd -o reports/system_architecture.png -s 3

# Export to vector PDF
mmdc -i reports/system_architecture.mmd -o reports/system_architecture.pdf
```

### Method 3: Visual Studio Code Extension
1. Install the extension **Markdown Preview Mermaid Support** (by Matt Bierner) or **Mermaid Chart**.
2. Open `reports/system_architecture.md` and press `Ctrl+Shift+V` to open Markdown Preview.
3. Right-click the rendered diagram and select **Save image as...** or print the preview to PDF (`Ctrl+P` -> Save as PDF).
