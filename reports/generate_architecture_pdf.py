"""
TwinSense AI - Professional System Architecture Diagram Generator
===================================================================
Generates a publication-quality, landscape vector PDF diagram of the complete
TwinSense AI system architecture, including offline training and runtime pipelines.
"""

from pathlib import Path
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# ----------------------------------------------------------------------
# Page Dimensions & Palette
# ----------------------------------------------------------------------
PAGE_WIDTH = 1224.0   # 17 inches (Standard Tabloid / Engineering Landscape)
PAGE_HEIGHT = 792.0   # 11 inches

# Deep tech / clinical theme palette
C_BG = HexColor("#0A0B14")            # Canvas background (midnight dark)
C_SURFACE = HexColor("#111322")       # Large subsystem container background
C_SURFACE_BORDER = HexColor("#222744") # Subsystem border
C_HEADER_BG = HexColor("#181B30")     # Header background

# Node colors
C_NODE_BG = HexColor("#16192E")       # Standard component node
C_NODE_BORDER = HexColor("#2F365F")   # Node border
C_ACCENT_BLUE = HexColor("#3B82F6")   # Data / Pipeline blue
C_ACCENT_CYAN = HexColor("#06B6D4")   # Runtime / API cyan
C_ACCENT_PURPLE = HexColor("#A855F7") # Digital Twin / Engine purple
C_ACCENT_ORANGE = HexColor("#F97316") # ML Model / Storage orange
C_ACCENT_GREEN = HexColor("#10B981")  # Frontend / User green
C_ACCENT_ROSE = HexColor("#F43F5E")   # Safety / Alert rose-red

# Text colors
C_TEXT_WHITE = HexColor("#FFFFFF")
C_TEXT_PRIMARY = HexColor("#F1F5F9")
C_TEXT_MUTED = HexColor("#94A3B8")
C_TEXT_SUBTLE = HexColor("#64748B")
C_CODE_BG = HexColor("#0D0E1A")


def draw_arrow(c, x1, y1, x2, y2, color=C_ACCENT_BLUE, line_width=1.5, label=None, label_side="top"):
    """Draws a crisp directed arrow with an arrowhead and optional label."""
    c.setStrokeColor(color)
    c.setLineWidth(line_width)
    c.line(x1, y1, x2, y2)
    
    # Calculate arrowhead
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    head_len = 7.0
    arrow_angle = math.pi / 7.0
    
    left_x = x2 - head_len * math.cos(angle - arrow_angle)
    left_y = y2 - head_len * math.sin(angle - arrow_angle)
    right_x = x2 - head_len * math.cos(angle + arrow_angle)
    right_y = y2 - head_len * math.sin(angle + arrow_angle)
    
    p = c.beginPath()
    p.moveTo(x2, y2)
    p.lineTo(left_x, left_y)
    p.lineTo(right_x, right_y)
    p.close()
    c.setFillColor(color)
    c.drawPath(p, fill=1, stroke=0)
    
    if label:
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(color)
        mx = (x1 + x2) / 2.0
        my = (y1 + y2) / 2.0
        if label_side == "top":
            c.drawCentredString(mx, my + 4, label)
        elif label_side == "bottom":
            c.drawCentredString(mx, my - 10, label)
        elif label_side == "right":
            c.drawString(mx + 6, my - 3, label)
        elif label_side == "left":
            c.drawRightString(mx - 6, my - 3, label)


def draw_card(c, x, y, w, h, title, subtitle=None, badge=None, badge_color=C_ACCENT_BLUE, items=None, border_color=C_NODE_BORDER, bg_color=C_NODE_BG):
    """Draws a structured architectural card component."""
    # Outer box
    c.setFillColor(bg_color)
    c.setStrokeColor(border_color)
    c.setLineWidth(1.2)
    c.roundRect(x, y, w, h, 6, stroke=1, fill=1)
    
    # Header row
    curr_y = y + h - 16
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(C_TEXT_WHITE)
    c.drawString(x + 10, curr_y, title)
    
    if badge:
        c.setFont("Helvetica-Bold", 7)
        badge_w = c.stringWidth(badge, "Helvetica-Bold", 7) + 10
        bx = x + w - badge_w - 8
        by = curr_y - 3
        c.setFillColor(HexColor("#1A2035"))
        c.setStrokeColor(badge_color)
        c.setLineWidth(0.8)
        c.roundRect(bx, by, badge_w, 13, 3, stroke=1, fill=1)
        c.setFillColor(badge_color)
        c.drawString(bx + 5, by + 3.5, badge)
        
    curr_y -= 13
    if subtitle:
        c.setFont("Helvetica-Oblique", 7.5)
        c.setFillColor(C_TEXT_MUTED)
        c.drawString(x + 10, curr_y, subtitle)
        curr_y -= 10
        
    # Dividing line
    c.setStrokeColor(HexColor("#262C4C"))
    c.setLineWidth(0.6)
    c.line(x + 10, curr_y + 4, x + w - 10, curr_y + 4)
    curr_y -= 6
    
    # Content items
    if items:
        for it in items:
            c.setFont("Helvetica", 7.5)
            c.setFillColor(C_TEXT_PRIMARY)
            # Check for bullet or code tag
            if it.startswith("• "):
                c.drawString(x + 10, curr_y, it)
            elif it.startswith("> "):
                c.setFont("Helvetica-Bold", 7.2)
                c.setFillColor(badge_color)
                c.drawString(x + 10, curr_y, it[2:])
            elif it.startswith("[code] "):
                c.setFont("Courier", 7.0)
                c.setFillColor(HexColor("#38BDF8"))
                c.drawString(x + 12, curr_y, it[7:])
            else:
                c.drawString(x + 10, curr_y, it)
            curr_y -= 11


def generate_architecture_pdf(output_path: Path):
    """Renders the comprehensive TwinSense AI Architecture Diagram PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(output_path), pagesize=(PAGE_WIDTH, PAGE_HEIGHT))
    
    # -------------------------------------------------------------
    # 1. Main Background & Header
    # -------------------------------------------------------------
    c.setFillColor(C_BG)
    c.rect(0, 0, PAGE_WIDTH, PAGE_HEIGHT, fill=1, stroke=0)
    
    # Top banner bar
    c.setFillColor(C_HEADER_BG)
    c.setStrokeColor(C_SURFACE_BORDER)
    c.setLineWidth(1)
    c.rect(20, PAGE_HEIGHT - 65, PAGE_WIDTH - 40, 50, fill=1, stroke=1)
    
    # Header Title
    c.setFont("Helvetica-Bold", 16)
    c.setFillColor(C_TEXT_WHITE)
    c.drawString(35, PAGE_HEIGHT - 38, "TwinSense AI — System Architecture Specification")
    
    c.setFont("Helvetica", 8.5)
    c.setFillColor(C_TEXT_MUTED)
    c.drawString(35, PAGE_HEIGHT - 52, "Predictive Healthcare Digital Twin Prototype  |  100% Synthetic Multi-Patient Simulation  |  Local-First Zero-Cloud Architecture")
    
    # Badges on top right
    meta_badges = [
        ("FastAPI 0.110+", C_ACCENT_CYAN),
        ("Scikit-Learn 1.4+", C_ACCENT_ORANGE),
        ("Argon2id Auth", C_ACCENT_PURPLE),
        ("ReportLab PDF", C_ACCENT_BLUE),
        ("123 Pytest Passing", C_ACCENT_GREEN),
        ("MIT License", HexColor("#EAB308"))
    ]
    bx = PAGE_WIDTH - 35
    for tag, col in reversed(meta_badges):
        c.setFont("Helvetica-Bold", 7.5)
        bw = c.stringWidth(tag, "Helvetica-Bold", 7.5) + 12
        bx -= bw
        c.setFillColor(HexColor("#12162A"))
        c.setStrokeColor(col)
        c.setLineWidth(1)
        c.roundRect(bx, PAGE_HEIGHT - 47, bw, 18, 4, stroke=1, fill=1)
        c.setFillColor(col)
        c.drawString(bx + 6, PAGE_HEIGHT - 35.5, tag)
        bx -= 8

    # -------------------------------------------------------------
    # 2. Phase Subsystem Container Frames
    # -------------------------------------------------------------
    # Left Frame: Phase 1 (Offline Batch Pipeline)
    P1_X = 20
    P1_Y = 25
    P1_W = 345
    P1_H = PAGE_HEIGHT - 100
    
    c.setFillColor(C_SURFACE)
    c.setStrokeColor(C_ACCENT_BLUE)
    c.setLineWidth(1.5)
    c.roundRect(P1_X, P1_Y, P1_W, P1_H, 8, stroke=1, fill=1)
    
    # Phase 1 Subsystem Header
    c.setFillColor(HexColor("#1A2444"))
    c.roundRect(P1_X + 2, P1_Y + P1_H - 28, P1_W - 4, 26, 6, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_ACCENT_BLUE)
    c.drawString(P1_X + 12, P1_Y + P1_H - 18, "PHASE 1: OFFLINE DATA & TRAINING PIPELINE (BATCH)")

    # Right Frame: Phase 2 (Runtime Online Service)
    P2_X = 380
    P2_Y = 25
    P2_W = PAGE_WIDTH - P2_X - 20
    P2_H = PAGE_HEIGHT - 100
    
    c.setFillColor(C_SURFACE)
    c.setStrokeColor(C_ACCENT_CYAN)
    c.setLineWidth(1.5)
    c.roundRect(P2_X, P2_Y, P2_W, P2_H, 8, stroke=1, fill=1)
    
    # Phase 2 Subsystem Header
    c.setFillColor(HexColor("#102B3B"))
    c.roundRect(P2_X + 2, P2_Y + P2_H - 28, P2_W - 4, 26, 6, stroke=0, fill=1)
    c.setFont("Helvetica-Bold", 10)
    c.setFillColor(C_ACCENT_CYAN)
    c.drawString(P2_X + 12, P2_Y + P2_H - 18, "PHASE 2: ONLINE RUNTIME PREDICTION & INTERACTIVE TWIN (LOCAL SERVER)")

    # -------------------------------------------------------------
    # 3. Phase 1 Cards (Offline Pipeline)
    # -------------------------------------------------------------
    # Card 1.1: Synthetic Data Generator
    draw_card(
        c, P1_X + 12, P1_Y + P1_H - 150, P1_W - 24, 110,
        title="1. Synthetic Patient Data Generator",
        subtitle="src/data_generator.py (Deterministic Simulation)",
        badge="Seeded: 42",
        badge_color=C_ACCENT_BLUE,
        items=[
            "• Models 10 clinically diverse patients (T1D & T2D)",
            "• 7 days continuous CGM @ 5-min intervals (20,160 readings)",
            "• Physiological range enforcement: [40.0, 400.0] mg/dL",
            "> Output Raw Datasets:",
            "[code] data/raw/patient_profiles.csv (10 profiles)",
            "[code] data/raw/glucose_timeseries.csv (20,160 rows)"
        ]
    )

    # Arrow 1.1 -> 1.2
    draw_arrow(c, P1_X + P1_W / 2, P1_Y + P1_H - 150, P1_X + P1_W / 2, P1_Y + P1_H - 175, color=C_ACCENT_BLUE)

    # Card 1.2: Feature Engineering & Preprocessing
    draw_card(
        c, P1_X + 12, P1_Y + P1_H - 325, P1_W - 24, 140,
        title="2. Preprocessing & Feature Engineering",
        subtitle="src/feature_engineering.py (Past-Only Windows)",
        badge="11 Features",
        badge_color=C_ACCENT_CYAN,
        items=[
            "• Joins static EHR baselines (Age, BMI, HbA1c, Duration)",
            "• Extracts past-only rolling features (15m/30m means, RoC)",
            "• Activity telemetry: 30m step sum, 30m mean heart rate",
            "• Target formulation: Glucose state at t + 45 minutes",
            "> Temporal Leakage Prevention Protocol:",
            "• Chronological 80/20 partition per patient",
            "• 45-minute embargo buffer dropped at partition boundary",
            "[code] data/processed/training_dataset.csv (20,020 rows)"
        ]
    )

    # Arrow 1.2 -> 1.3
    draw_arrow(c, P1_X + P1_W / 2, P1_Y + P1_H - 325, P1_X + P1_W / 2, P1_Y + P1_H - 350, color=C_ACCENT_BLUE)

    # Card 1.3: Model Training & Evaluation
    draw_card(
        c, P1_X + 12, P1_Y + P1_H - 505, P1_W - 24, 145,
        title="3. Random Forest Model Training",
        subtitle="src/train.py (Chronological Split + Embargo)",
        badge="89.29% Acc",
        badge_color=C_ACCENT_ORANGE,
        items=[
            "• Model: Balanced RandomForestClassifier (100 trees, depth 8)",
            "• Benchmark: DummyClassifier (most frequent baseline)",
            "• Macro F1 on active classes: 0.8917 (vs Baseline: 0.3557)",
            "• Accuracy: 89.29% on untouched holdout test set (N=3,920)",
            "> Honest Limitation Guardrail:",
            "• Class 1 (Hypoglycemia) support: 0 samples in train & test",
            "• Preserves zero-reassurance constraint & warning policy"
        ]
    )

    # Arrow 1.3 -> 1.4
    draw_arrow(c, P1_X + P1_W / 2, P1_Y + P1_H - 505, P1_X + P1_W / 2, P1_Y + P1_H - 530, color=C_ACCENT_ORANGE)

    # Card 1.4: Saved Model Artifacts & Schemas
    draw_card(
        c, P1_X + 12, P1_Y + 15, P1_W - 24, 115,
        title="4. Persisted Model & Schema Artifacts",
        subtitle="models/ & reports/ (Serialized Assets)",
        badge="Joblib / JSON",
        badge_color=C_ACCENT_ORANGE,
        items=[
            "> Persisted Trained Artifacts:",
            "[code] models/random_forest_risk_model.joblib",
            "[code] models/feature_columns.json (Strict 11 features)",
            "> Audited Documentation:",
            "[code] reports/evaluation_report.md (Metrics & matrices)",
            "[code] reports/model_evaluation.md (Comparative audit)"
        ]
    )

    # -------------------------------------------------------------
    # 4. Phase 2 Cards (Online Runtime Pipeline)
    # -------------------------------------------------------------
    # Let's organize Phase 2 into 3 functional columns:
    # Col A: Frontend UI & Client Authentication (Left)
    # Col B: FastAPI Backend Core & Relational Storage (Middle)
    # Col C: TwinEngine Digital Twin, Safety, & Export Services (Right)
    
    COL_GAP = 16
    COL_W = (P2_W - 48) / 3.0
    
    COL1_X = P2_X + 16
    COL2_X = COL1_X + COL_W + COL_GAP
    COL3_X = COL2_X + COL_W + COL_GAP
    
    # --- Column A: Frontend & Client Authentication ---
    
    # Card 2.1: Authentication & User Management (Login/Register)
    draw_card(
        c, COL1_X, P2_Y + P2_H - 185, COL_W, 145,
        title="9. Login & Registration System",
        subtitle="app/auth.py & app/static/ (Security Layer)",
        badge="Argon2id",
        badge_color=C_ACCENT_PURPLE,
        items=[
            "• RFC 9106 Argon2id password hashing (salted)",
            "• Never stores or returns plaintext passwords",
            "• Server-managed secure sessions in SQLite",
            "• HttpOnly twinsense_session cookie (SameSite)",
            "• Double-submit twinsense_csrf token protection",
            "• Non-revealing error messages against user enum",
            "[code] /login.html  |  /register.html  |  /api/auth/*"
        ]
    )

    # Arrow 2.1 <-> 2.2
    draw_arrow(c, COL1_X + COL_W / 2, P2_Y + P2_H - 185, COL1_X + COL_W / 2, P2_Y + P2_H - 215, color=C_ACCENT_GREEN)

    # Card 2.2: Interactive HTML5/CSS/JS Dashboard
    draw_card(
        c, COL1_X, P2_Y + 15, COL_W, P2_H - 240,
        title="10. HTML/CSS/JavaScript Dashboard",
        subtitle="app/static/ (Pure Native Web Client)",
        badge="Vanilla JS & SVG",
        badge_color=C_ACCENT_GREEN,
        items=[
            "> Self-Contained Frontend (Zero External CDNs):",
            "• index.html: Semantic UI with glassmorphic cards",
            "• style.css: Modern clinical violet/teal theme",
            "• app.js: Pure ES6 controller, native SVG chart engine",
            "> Interactive Core Capabilities:",
            "• Patient Selector: Switch profiles (PAT_001 - 010)",
            "• High-Frequency CGM Chart: Real-time SVG time-series",
            "• 45-Min Forward Forecast Panel: In-Range vs Hyper",
            "• What-If Counterfactual Sandbox: Delta sliders",
            "• Clinical Explanations: Key contributing factors",
            "• Real-time Low-Glucose Rule Alert (< 70 mg/dL)",
            "• Persistent Disclaimers: Non-clinical synthetic data",
            "• One-Click Clinical Report Download (CSV / PDF)"
        ]
    )

    # --- Column B: FastAPI Backend & SQLite Relational Store ---

    # Card 2.3: FastAPI Backend Application
    draw_card(
        c, COL2_X, P2_Y + P2_H - 275, COL_W, 235,
        title="5. FastAPI Backend Application",
        subtitle="app/main.py, schemas.py, services.py",
        badge="Port 8000 / ASGI",
        badge_color=C_ACCENT_CYAN,
        items=[
            "> Application Core & Lifespan Manager:",
            "• Idempotent startup seeder from raw CSV data",
            "• Static file mounting for dashboard & auth pages",
            "• CORS middleware restricted to local origins",
            "> Typed REST API Routes (Pydantic v2):",
            "[code] GET  /api/health (System status & warnings)",
            "[code] GET  /api/patients (List 10 profiles)",
            "[code] GET  /api/patients/{id}/readings (Telemetry)",
            "[code] POST /api/patients/{id}/predict (45m Inference)",
            "[code] POST /api/patients/{id}/what-if (Simulation)",
            "[code] GET  /api/patients/{id}/predictions (Audit log)",
            "[code] GET  /api/patients/{id}/report/csv (Export)",
            "[code] GET  /api/patients/{id}/report/pdf (Export)"
        ]
    )

    # Arrow 2.3 -> 2.4
    draw_arrow(c, COL2_X + COL_W / 2, P2_Y + P2_H - 275, COL2_X + COL_W / 2, P2_Y + P2_H - 305, color=C_ACCENT_CYAN)

    # Card 2.4: SQLite Relational Database Store
    draw_card(
        c, COL2_X, P2_Y + 15, COL_W, P2_H - 330,
        title="6. SQLite Local Relational Store",
        subtitle="data/twinsense.db (Zero-Cloud Local DB)",
        badge="SQLite3",
        badge_color=C_ACCENT_ORANGE,
        items=[
            "> Relational Schema Tables:",
            "• patients: 10 synthetic baseline EHR records",
            "• telemetry_readings: 20,160 5-min sensor records",
            "• users: Registered clinician/researcher credentials",
            "• sessions: Active server-side sessions with expiry",
            "• predictions: Append-only forecast audit log",
            "> Operational Guarantees:",
            "• Idempotent CSV population on cold start",
            "• Indexed foreign keys (patient_id, timestamp)",
            "• What-if simulation does NOT write to database",
            "• Safe local storage without external network calls"
        ]
    )

    # --- Column C: TwinEngine Digital Twin, Safety, & Reports ---

    # Card 2.5: TwinEngine & Counterfactual Simulation
    draw_card(
        c, COL3_X, P2_Y + P2_H - 200, COL_W, 160,
        title="7. TwinEngine Digital Twin Core",
        subtitle="src/twin_engine.py (In-Memory Engine)",
        badge="Singleton",
        badge_color=C_ACCENT_PURPLE,
        items=[
            "> In-Memory Digital Twin Representation:",
            "• Couples static EHR profile with dynamic CGM stream",
            "• Validates temporal ordering & min 30m sensor window",
            "• Evaluates Random Forest model via scikit-learn",
            "> What-If Counterfactual Sandbox:",
            "• Ephemeral in-memory telemetry clone (Zero DB write)",
            "• Evaluates Delta Glucose (-50 to +50 mg/dL)",
            "• Evaluates Delta Activity (0 to +1,500 steps)",
            "• Generates side-by-side observed vs simulated risk"
        ]
    )

    # Arrow 2.5 -> 2.6
    draw_arrow(c, COL3_X + COL_W / 2, P2_Y + P2_H - 200, COL3_X + COL_W / 2, P2_Y + P2_H - 225, color=C_ACCENT_ROSE)

    # Card 2.6: Safety Alerts & Suggestions Module
    draw_card(
        c, COL3_X, P2_Y + P2_H - 375, COL_W, 140,
        title="8. Safety Alerts & Suggestions",
        subtitle="app/suggestions.py & src/twin_engine.py",
        badge="Safety Engine",
        badge_color=C_ACCENT_ROSE,
        items=[
            "> Rule-Based Low-Glucose Safety Alert:",
            "• Trigger: Measured glucose < 70 mg/dL (Rule-based)",
            "• Independent of ML; fires immediately without forecast",
            "• Zero insulin/dosing advice; clear emergency guidance",
            "> Transparent Model Limitation Warnings:",
            "• 'Hypoglycemia prediction is not supported by model'",
            "• Class 1 displayed as 'Not supported' (never 0%)",
            "> Contextual Lifestyle & Clinician Review Suggestions"
        ]
    )

    # Arrow 2.6 -> 2.7
    draw_arrow(c, COL3_X + COL_W / 2, P2_Y + P2_H - 375, COL3_X + COL_W / 2, P2_Y + P2_H - 400, color=C_ACCENT_BLUE)

    # Card 2.7: Report Generation & Export Service
    draw_card(
        c, COL3_X, P2_Y + 15, COL_W, P2_H - 425,
        title="11. Prediction History & Reports",
        subtitle="app/reports.py (Clinical PDF / CSV Export)",
        badge="ReportLab PDF",
        badge_color=C_ACCENT_BLUE,
        items=[
            "> Historical Audit Trail (/api/patients/{id}/predictions):",
            "• Traceable forecast history with timestamps & factors",
            "> CSV Clinical Audit Report (/report/csv):",
            "• Tabular dump of probabilities, features, and alerts",
            "> PDF Clinical Summary Report (/report/pdf):",
            "• Professional ReportLab vector PDF generation",
            "• Patient EHR header, risk breakdown, and alert box",
            "• Prominent non-clinical synthetic data disclaimers"
        ]
    )

    # -------------------------------------------------------------
    # 5. Inter-Subsystem Connecting Arrows
    # -------------------------------------------------------------
    # 1. Model Artifacts (Phase 1) -> TwinEngine (Phase 2)
    # Starts at right of Card 1.4, goes to left of Card 2.5
    art_x = P1_X + P1_W - 12
    art_y = P1_Y + 70
    engine_x = COL3_X
    engine_y = P2_Y + P2_H - 120
    
    # We draw an inter-phase bridge line
    c.setStrokeColor(C_ACCENT_ORANGE)
    c.setLineWidth(1.5)
    c.setDash([4, 3])
    
    # Polyline from Card 1.4 up and across to Card 2.5
    bridge_p = c.beginPath()
    bridge_p.moveTo(art_x, art_y)
    bridge_p.lineTo(art_x + 15, art_y)
    bridge_p.lineTo(art_x + 15, P2_Y + P2_H - 60)
    bridge_p.lineTo(COL3_X + COL_W / 2, P2_Y + P2_H - 60)
    bridge_p.lineTo(COL3_X + COL_W / 2, P2_Y + P2_H - 40)
    c.drawPath(bridge_p, stroke=1, fill=0)
    c.setDash([]) # reset dash
    
    c.setFont("Helvetica-Bold", 8)
    c.setFillColor(C_ACCENT_ORANGE)
    c.drawString(art_x + 22, P2_Y + P2_H - 52, "Trained Model Weights & Feature Schema Loaded on Startup")

    # 2. Frontend (Dashboard) <==> Backend (FastAPI)
    draw_arrow(
        c, COL1_X + COL_W, P2_Y + P2_H - 330, COL2_X, P2_Y + P2_H - 220,
        color=C_ACCENT_GREEN, line_width=1.8, label="HTTP / JSON REST Calls", label_side="top"
    )
    draw_arrow(
        c, COL2_X, P2_Y + P2_H - 240, COL1_X + COL_W, P2_Y + P2_H - 350,
        color=C_ACCENT_CYAN, line_width=1.8, label="Typed API Responses", label_side="bottom"
    )

    # 3. Backend (FastAPI) <==> TwinEngine (Digital Twin Core)
    draw_arrow(
        c, COL2_X + COL_W, P2_Y + P2_H - 130, COL3_X, P2_Y + P2_H - 130,
        color=C_ACCENT_PURPLE, line_width=1.8, label="Inference & What-If", label_side="top"
    )
    draw_arrow(
        c, COL3_X, P2_Y + P2_H - 150, COL2_X + COL_W, P2_Y + P2_H - 150,
        color=C_ACCENT_PURPLE, line_width=1.8, label="Risk Probs & Factors", label_side="bottom"
    )

    # 4. Backend (FastAPI) <==> Reports Exporter
    draw_arrow(
        c, COL2_X + COL_W, P2_Y + 120, COL3_X, P2_Y + 120,
        color=C_ACCENT_BLUE, line_width=1.8, label="Export Request", label_side="top"
    )
    draw_arrow(
        c, COL3_X, P2_Y + 100, COL2_X + COL_W, P2_Y + 100,
        color=C_ACCENT_BLUE, line_width=1.8, label="Binary PDF / CSV Stream", label_side="bottom"
    )

    # 5. Raw CSVs -> SQLite Seeding (idempotent init on startup)
    c.setStrokeColor(HexColor("#475569"))
    c.setLineWidth(1.2)
    c.setDash([3, 3])
    p_seed = c.beginPath()
    p_seed.moveTo(P1_X + P1_W - 12, P1_Y + P1_H - 100)
    p_seed.lineTo(COL2_X + COL_W / 2, P1_Y + P1_H - 100)
    p_seed.lineTo(COL2_X + COL_W / 2, P2_Y + 230)
    c.drawPath(p_seed, stroke=1, fill=0)
    c.setDash([])
    c.setFont("Helvetica-Bold", 7.5)
    c.setFillColor(HexColor("#94A3B8"))
    c.drawString(P1_X + P1_W + 15, P1_Y + P1_H - 95, "Idempotent Database Initialization (Raw CSVs -> SQLite on Startup)")

    # -------------------------------------------------------------
    # 6. Save and Finish PDF
    # -------------------------------------------------------------
    c.showPage()
    c.save()
    print(f"Successfully generated architecture diagram PDF at: {output_path}")


if __name__ == "__main__":
    out_file = Path("reports/system_architecture_diagram.pdf")
    generate_architecture_pdf(out_file)
