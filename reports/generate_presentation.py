"""
TwinSense AI - Professional Presentation Generator
==================================================
Builds a 12-slide presentation in both PowerPoint (.pptx) and PDF (.pdf)
formats adhering to the project submission requirements, clinical disclaimers,
and technical specifications.
"""

import math
from pathlib import Path

# --- python-pptx imports ---
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

# --- reportlab imports ---
from reportlab.lib import colors
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor

# -------------------------------------------------------------
# Color Palette (Dark Midnight / Purple / Teal Theme)
# -------------------------------------------------------------
HEX_BG = "#090617"           # Midnight dark background
HEX_CARD = "#17112B"         # Card background
HEX_BORDER = "#2E2452"       # Card border
HEX_ACCENT_PURPLE = "#A855F7"# Primary purple / lavender
HEX_ACCENT_TEAL = "#06B6D4"  # Primary teal / cyan
HEX_ACCENT_GREEN = "#10D6A0" # Positive green
HEX_ACCENT_ROSE = "#FF4385"  # Alert pink/rose
HEX_ACCENT_AMBER = "#F59E0B" # Warning amber
HEX_TEXT_WHITE = "#FFFFFF"   # Bright text
HEX_TEXT_MUTED = "#94A3B8"   # Secondary text
HEX_TEXT_BODY = "#E2E8F0"    # Normal body text

RGB_BG = RGBColor(9, 6, 23)
RGB_CARD = RGBColor(23, 17, 43)
RGB_BORDER = RGBColor(46, 36, 82)
RGB_ACCENT_PURPLE = RGBColor(168, 85, 247)
RGB_ACCENT_TEAL = RGBColor(6, 182, 212)
RGB_ACCENT_GREEN = RGBColor(16, 214, 160)
RGB_ACCENT_ROSE = RGBColor(255, 67, 133)
RGB_ACCENT_AMBER = RGBColor(245, 158, 11)
RGB_TEXT_WHITE = RGBColor(255, 255, 255)
RGB_TEXT_MUTED = RGBColor(148, 163, 184)
RGB_TEXT_BODY = RGBColor(226, 232, 240)


# -------------------------------------------------------------
# 12 Slide Data Definitions
# -------------------------------------------------------------
SLIDES_DATA = [
    {
        "slide_num": 1,
        "title": "TwinSense AI",
        "subtitle": "Predictive Healthcare Digital Twin Prototype for Continuous Glycemic Risk Estimation",
        "category": "PROJECT SUBMISSION",
        "tag": "ACADEMIC INNOVATION",
        "cards": [
            {
                "col": "left",
                "title": "Core Digital Twin Concept",
                "badge": "In-Silico Simulation",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• In-Silico Patient Avatar: Unifies static EHR baselines with high-frequency dynamic CGM telemetry.",
                    "• 45-Minute Horizon: Forward-looking risk classification (In-Range vs. Hyperglycemia).",
                    "• Counterfactual Sandbox: Non-destructive 'What-If' lifestyle and activity simulation.",
                    "• Explainable AI: Automated physiological risk factor attribution.",
                    "• Local-First Privacy: 100% offline-capable, zero external cloud dependencies."
                ]
            },
            {
                "col": "right",
                "title": "Mandatory Ethical & Clinical Disclaimer",
                "badge": "100% Synthetic Data",
                "badge_col": HEX_ACCENT_ROSE,
                "badge_rgb": RGB_ACCENT_ROSE,
                "lines": [
                    "• FOR RESEARCH & DEMONSTRATION PURPOSES ONLY.",
                    "• 100% Synthetic Data: All profiles and CGM time-series are algorithmically generated.",
                    "• Not Clinically Validated: Not evaluated in clinical trials; NOT approved by FDA/CE/CDSCO.",
                    "• Zero Medical Claims: Must NEVER be used for diagnostic or insulin dosage decisions.",
                    "• Unsupported Hypoglycemia: Model does not detect or predict hypoglycemia (Class 1)."
                ]
            }
        ],
        "footer": "TwinSense AI — Healthcare Digital Twin Prototype | Team & Institution Submission Deck"
    },
    {
        "slide_num": 2,
        "title": "Problem Statement & Clinical Motivation",
        "subtitle": "The challenge of glycemic volatility and the limitations of current CGM alert systems",
        "category": "CLINICAL CONTEXT",
        "tag": "THE CHALLENGE",
        "cards": [
            {
                "col": "left",
                "title": "Glycemic Volatility in Diabetes",
                "badge": "Clinical Urgency",
                "badge_col": HEX_ACCENT_AMBER,
                "badge_rgb": RGB_ACCENT_AMBER,
                "lines": [
                    "• Dynamic Instability: Individuals with Type 1 & Type 2 diabetes suffer rapid glycemic excursions.",
                    "• Acute Risks: Hyperglycemic crises (ketoacidosis, hyperosmolar state) vs. acute hypoglycemic shock.",
                    "• Multi-Factorial Drivers: Volatility is driven by delayed meal absorption, physical exertion, and circadian shifts.",
                    "• Action Delay: Corrective lifestyle or dietary actions are often taken too late after symptoms arise."
                ]
            },
            {
                "col": "right",
                "title": "Standard CGM System Limitations",
                "badge": "Point-in-Time Lag",
                "badge_col": HEX_ACCENT_ROSE,
                "badge_rgb": RGB_ACCENT_ROSE,
                "lines": [
                    "• Point-in-Time Readings: Existing CGMs report current sensor values and basic trend arrows, not 45m forward risk.",
                    "• No Behavioral Sandbox: Patients cannot safely test 'what if I walk 1,000 steps?' in advance.",
                    "• Black-Box Alerts: Standard threshold alarms lack explainable contributing physiological factors.",
                    "• Need for In-Silico Testing: A software digital twin provides an exploratory space without biological risk."
                ]
            }
        ],
        "footer": "TwinSense AI — Problem Statement | Addressing Glycemic Latency via Predictive Modeling"
    },
    {
        "slide_num": 3,
        "title": "Proposed Solution: TwinSense AI",
        "subtitle": "Coupling physiological EHR baselines with wearable telemetry for predictive risk estimation",
        "category": "SOLUTION OVERVIEW",
        "tag": "DIGITAL TWIN",
        "cards": [
            {
                "col": "left",
                "title": "The Digital Twin Architecture",
                "badge": "TwinEngine Core",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• In-Memory Representation: Combines patient EHR profiles (age, BMI, HbA1c) with real-time CGM telemetry.",
                    "• 45-Minute Forward Inference: Classifies future glycemic excursion risk into defined clinical categories.",
                    "• Contributing Factors Panel: Breaks down risk into 15m rate of change, rolling means, and meal events.",
                    "• Strict Temporal Boundaries: Validates chronological ordering and enforces a minimum 30-minute sensor history."
                ]
            },
            {
                "col": "right",
                "title": "Core Capabilities Implemented",
                "badge": "Four Pillars",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "1. 45-Min Forward Risk Classification: Balanced Random Forest trained with a 45m temporal embargo.",
                    "2. What-If Counterfactual Sandbox: Ephemeral in-memory clone evaluating hypothetical activity shifts.",
                    "3. Independent Rule-Based Low Glucose Alert: Immediate trigger when measured reading is strictly < 70 mg/dL.",
                    "4. Downloadable Audit Reports: Clinical summary PDF and tabular CSV generated directly via ReportLab."
                ]
            }
        ],
        "footer": "TwinSense AI — Proposed Solution | Predictive Digital Twin & Counterfactual Exploration"
    },
    {
        "slide_num": 4,
        "title": "Healthcare Use Case & Target Setting",
        "subtitle": "Decision support, behavioral exploration, and clinical research prototyping",
        "category": "APPLICATION DOMAIN",
        "tag": "DECISION SUPPORT",
        "cards": [
            {
                "col": "left",
                "title": "Target Patient Population",
                "badge": "T1D & T2D",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "• Type 1 & Type 2 Diabetes: Focus on individuals utilizing continuous glucose monitoring devices.",
                    "• Clinical Diversity: Evaluated across diverse synthetic profiles (ages 28–64, BMI 22.4–34.2, HbA1c 6.7%–10.0%).",
                    "• High-Frequency Telemetry: CGM sampled at 5-minute continuous intervals alongside heart rate and step counts.",
                    "• Safe Research Testbed: Provides an academic benchmark for physiological modeling and digital twins."
                ]
            },
            {
                "col": "right",
                "title": "Clinical & Behavioral Value Drivers",
                "badge": "Proactive Care",
                "badge_col": HEX_ACCENT_GREEN,
                "badge_rgb": RGB_ACCENT_GREEN,
                "lines": [
                    "• Proactive Lead Time: 45-minute forward window allows early hydration, resting, or light activity.",
                    "• Safe Lifestyle Experimentation: Users evaluate hypothetical step increments without physical danger.",
                    "• Explainable Consultations: PDF clinical reports summarize risk probability distributions for physician reviews.",
                    "• Pure Non-Clinical Guardrails: Never provides insulin dosing; mandates physician consultation."
                ]
            }
        ],
        "footer": "TwinSense AI — Healthcare Use Case | Safe Decision Support & Exploratory Sandboxes"
    },
    {
        "slide_num": 5,
        "title": "End-to-End System Architecture",
        "subtitle": "Decoupled batch training pipeline and low-latency local runtime microservice",
        "category": "SYSTEM ENGINEERING",
        "tag": "TWO-PHASE DESIGN",
        "cards": [
            {
                "col": "left",
                "title": "Phase 1: Offline Batch Pipeline",
                "badge": "Data & ML",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Synthetic Generator: src/data_generator.py creates raw patient profiles and 20,160 CGM readings.",
                    "• Feature Pipeline: src/feature_engineering.py computes past-only rolling metrics and drops lookahead leaks.",
                    "• Model Training: src/train.py partitions data with a 45m embargo buffer and trains Random Forest.",
                    "• Artifact Serialization: Persists models/random_forest_risk_model.joblib and feature_columns.json."
                ]
            },
            {
                "col": "right",
                "title": "Phase 2: Online Runtime Sandbox",
                "badge": "Local ASGI Server",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "• Client Dashboard: Vanilla HTML5, CSS3, ES6 JS with pure native SVG telemetry charting (zero CDNs).",
                    "• FastAPI Backend: Typed asynchronous REST API (port 8000) with Pydantic v2 schemas.",
                    "• Local Relational DB: SQLite3 (data/twinsense.db) storing patients, telemetry, audit logs, and sessions.",
                    "• Security: RFC 9106 Argon2id password hashing, HttpOnly session cookies, and CSRF protection."
                ]
            }
        ],
        "footer": "TwinSense AI — System Architecture | Specification Document: reports/system_architecture_diagram.pdf"
    },
    {
        "slide_num": 6,
        "title": "Synthetic Dataset & Feature Engineering",
        "subtitle": "Deterministic simulation, past-only rolling features, and the 45-minute embargo protocol",
        "category": "DATA SCIENCE",
        "tag": "LEAK-FREE PIPELINE",
        "cards": [
            {
                "col": "left",
                "title": "Deterministic Synthetic Generator",
                "badge": "100% Synthetic",
                "badge_col": HEX_ACCENT_AMBER,
                "badge_rgb": RGB_ACCENT_AMBER,
                "lines": [
                    "• Multi-Patient Cohort: 10 clinically diverse synthetic patients (SYNTH_PAT_001 to 010).",
                    "• Longitudinal Scope: 7 continuous simulated days at 5-minute sampling intervals (20,160 total rows).",
                    "• Physiological Bound Validation: Strictly checked [40.0, 400.0] mg/dL, strictly monotonic timestamps.",
                    "• Zero Real-Patient Data: Generated via mathematical circadian and postprandial clearance heuristics."
                ]
            },
            {
                "col": "right",
                "title": "11-Dimensional Feature Pipeline",
                "badge": "Embargo Buffer",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Rolling Glucose Features: 15m and 30m rolling means, 15m rate of change (mg/dL per 15 min).",
                    "• Dynamic Activity Telemetry: 30-minute accumulated step count, 30-minute mean heart rate.",
                    "• Static EHR Phenotype: Age, BMI, baseline HbA1c, diabetes type (T1D/T2D), and diagnosis duration.",
                    "• 45-Min Embargo Protocol: Drops 9 consecutive samples at split boundaries to eliminate temporal leakage.",
                    "• Processed Dataset: 20,020 leak-free feature-target pairs in data/processed/training_dataset.csv."
                ]
            }
        ],
        "footer": "TwinSense AI — Data Pipeline | Rigorous Chronological Splitting with Embargo Buffers"
    },
    {
        "slide_num": 7,
        "title": "Random Forest Model & 45-Minute Prediction",
        "subtitle": "Balanced multi-class ensemble modeling evaluated against an unlearned majority baseline",
        "category": "MACHINE LEARNING",
        "tag": "45-MIN HORIZON",
        "cards": [
            {
                "col": "left",
                "title": "Model Architecture & Training",
                "badge": "Random Forest",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "• Algorithm: Balanced RandomForestClassifier (n_estimators=100, max_depth=8, class_weight='balanced').",
                    "• Chronological Partitioning: First 80% of patient timelines for training, final 20% for untouched testing.",
                    "• Benchmark Comparison: Benchmarked against an unlearned DummyClassifier(strategy='most_frequent').",
                    "• Feature Schema Enforcement: Strict 11-feature ordered contract guaranteed via feature_columns.json."
                ]
            },
            {
                "col": "right",
                "title": "Clinical Risk Class Definitions",
                "badge": "3 Target Classes",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Class 1: Hypoglycemia (< 70 mg/dL) — CRITICAL LIMITATION: 0 samples in synthetic data.",
                    "• Class 2: In-Range / Normal Glycemia (70 – 180 mg/dL) — 1,756 test samples.",
                    "• Class 3: Hyperglycemia (> 180 mg/dL) — 2,164 test samples.",
                    "• Prediction Output: Calibrated categorical probabilities, forward target timestamp (+45m), and factors."
                ]
            }
        ],
        "footer": "TwinSense AI — Model Architecture | Chronological Evaluation with Scikit-Learn"
    },
    {
        "slide_num": 8,
        "title": "Actual Evaluation Results & Limitations",
        "subtitle": "Documented benchmark performance and transparent disclosure of the hypoglycemia limitation",
        "category": "BENCHMARK METRICS",
        "tag": "HONEST DISCLOSURE",
        "cards": [
            {
                "col": "left",
                "title": "Held-Out Test Set Performance (N=3,920)",
                "badge": "89.29% Accuracy",
                "badge_col": HEX_ACCENT_GREEN,
                "badge_rgb": RGB_ACCENT_GREEN,
                "lines": [
                    "• Overall Accuracy: 89.29% (vs. Majority Baseline: 55.20%, +34.08% improvement).",
                    "• Macro F1-Score (Active Classes): 0.8917 (vs. Majority Baseline: 0.3557, +0.5360 improvement).",
                    "• Class 2 (In-Range): Precision 88.00%, Recall 88.10%, F1-Score 0.8805 (1,547 correct / 1,756).",
                    "• Class 3 (Hyperglycemia): Precision 90.33%, Recall 90.25%, F1-Score 0.9029 (1,953 correct / 2,164).",
                    "• Validated on untouched chronological holdout data with a 45-minute embargo buffer."
                ]
            },
            {
                "col": "right",
                "title": "The Hypoglycemia (Class 1) Limitation",
                "badge": "Zero Support",
                "badge_col": HEX_ACCENT_ROSE,
                "badge_rgb": RGB_ACCENT_ROSE,
                "lines": [
                    "• Zero Class 1 Samples: Because synthetic data had elevated baselines, 0 hypoglycemia events were simulated.",
                    "• Unsupported Model Scope: The model CANNOT detect, predict, or rule out hypoglycemia.",
                    "• Honest UI Policy: Class 1 probability is explicitly displayed as 'Not supported' (NEVER '0%').",
                    "• Warning Banner: 'Hypoglycemia prediction is not supported by the current model' in all reports & panels.",
                    "• Pure Synthetic Data: Metrics reflect synthetic simulation and DO NOT imply clinical efficacy."
                ]
            }
        ],
        "footer": "TwinSense AI — Evaluation & Limitations | Reference: reports/evaluation_report.md"
    },
    {
        "slide_num": 9,
        "title": "Dashboard Interface & Implemented Features",
        "subtitle": "Native web client, real-time SVG charting, and full audit trail capabilities",
        "category": "FRONTEND & UX",
        "tag": "LIVE DASHBOARD",
        "cards": [
            {
                "col": "left",
                "title": "Interactive Client Capabilities",
                "badge": "Zero Dependencies",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "• Patient Phenotype Selector: Switch between 10 synthetic patients; profiles update dynamically.",
                    "• Native SVG CGM Chart: Mathematical coordinate renderer with color-coded target zones (zero chart.js).",
                    "• 45-Min Forward Forecast Panel: Visual risk badges, probability distributions, and clinical factors.",
                    "• What-If Counterfactual Controls: Interactive sliders for Delta Glucose and Delta Activity.",
                    "• Low-Glucose Safety Alert: Prominent banner fires immediately if measured glucose is < 70 mg/dL."
                ]
            },
            {
                "col": "right",
                "title": "Backend Services & Audit Trail",
                "badge": "Enterprise Ready",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Argon2id Security: Session-based login/registration with secure HttpOnly cookies and CSRF tokens.",
                    "• Downloadable PDF Report: Professional clinical summary PDF generated via ReportLab.",
                    "• Downloadable CSV Report: Full tabular audit export containing timestamps, features, and probabilities.",
                    "• Historical Predictions API: SQLite audit trail tracking every prediction run for traceability.",
                    "• Live Web App: Accessible locally at http://127.0.0.1:8000/ with interactive Swagger docs at /docs."
                ]
            }
        ],
        "footer": "TwinSense AI — Dashboard & UX | 100% Self-Contained Native Web Client"
    },
    {
        "slide_num": 10,
        "title": "Safety Alerts & What-If Simulation",
        "subtitle": "Rule-based emergency protection and non-destructive counterfactual exploration",
        "category": "SAFETY & SANDBOX",
        "tag": "GUARDRAILS",
        "cards": [
            {
                "col": "left",
                "title": "Independent Low-Glucose Safety Alert",
                "badge": "Strictly Rule-Based",
                "badge_col": HEX_ACCENT_ROSE,
                "badge_rgb": RGB_ACCENT_ROSE,
                "lines": [
                    "• Trigger: Fires strictly when measured observed glucose reading is < 70 mg/dL.",
                    "• Independent of ML: Activates immediately upon patient selection without running a model forecast.",
                    "• Measured Readings Only: Hypothetical what-if slider values NEVER trigger this alert.",
                    "• Strict Safety Wording: Advises immediate medical help if symptoms occur; ZERO dosing terms.",
                    "• Reset on Patient Switch: Automatically updates or clears when switching patient records."
                ]
            },
            {
                "col": "right",
                "title": "What-If Counterfactual Sandbox",
                "badge": "In-Memory Copy",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Ephemeral Telemetry Clones: Modifies an in-memory clone without mutating database or CSVs.",
                    "• Evaluates Dual Perturbations: Delta Glucose (-50 to +50 mg/dL) and Delta Steps (0 to +1,500).",
                    "• Side-by-Side Comparison: Visualizes observed baseline vs. simulated hypothetical forward risk.",
                    "• Clear Simulation Labeling: Hypothetical values carry a prominent '(Simulated)' badge.",
                    "• Zero Reassurance: Maintains all disclaimers and displays Class 1 as 'Not supported'."
                ]
            }
        ],
        "footer": "TwinSense AI — Safety & What-If | Decoupled Rule Alerts & Non-Destructive In-Memory Clones"
    },
    {
        "slide_num": 11,
        "title": "Technology Stack & Verification Suite",
        "subtitle": "Production-grade Python ecosystem validated by 123 automated test cases",
        "category": "ENGINEERING RIGOR",
        "tag": "123 TESTS PASSING",
        "cards": [
            {
                "col": "left",
                "title": "Core Technical Stack",
                "badge": "Modern Python",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "• Backend & API: FastAPI >=0.110.0, Uvicorn >=0.28.0, Pydantic v2 >=2.6.0.",
                    "• Machine Learning: Scikit-Learn >=1.4.0, Pandas >=2.2.0, NumPy >=1.26.0, Joblib >=1.3.0.",
                    "• Security & DB: Argon2-cffi >=25.1.0, Python Built-in SQLite3, CSRF Protection.",
                    "• Reporting: ReportLab >=4.0.0 (Clinical PDF Synthesis), pypdf >=5.0.0.",
                    "• Frontend: Semantic HTML5, CSS3 Variables, ES6 JavaScript, Pure Native SVG."
                ]
            },
            {
                "col": "right",
                "title": "Verification & Quality Assurance",
                "badge": "100% Pass Rate",
                "badge_col": HEX_ACCENT_GREEN,
                "badge_rgb": RGB_ACCENT_GREEN,
                "lines": [
                    "• Pytest Suite: 123 automated test cases covering API, TwinEngine, Auth, Safety, and Reports.",
                    "• Immutability Checks: Tests confirm what-if simulations leave underlying state unaltered.",
                    "• Embargo Verification: Asserts zero temporal target leakage across chronological splits.",
                    "• Safety Unit Tests: Asserts boundary alerts (69.9 vs 70.0 mg/dL) and absence of dosing terms.",
                    "• Cryptographic Integrity: SHA-256 hashes of datasets and models validated bit-for-bit unchanged."
                ]
            }
        ],
        "footer": "TwinSense AI — Quality Assurance | 123 Passed Tests in ~10.6s | Verified Cryptographic Hashes"
    },
    {
        "slide_num": 12,
        "title": "Conclusion & Future Research Roadmap",
        "subtitle": "Key contributions of the TwinSense AI prototype and next engineering frontiers",
        "category": "SUMMARY & FUTURE",
        "tag": "CONCLUSION",
        "cards": [
            {
                "col": "left",
                "title": "Key Project Achievements",
                "badge": "Validated Prototype",
                "badge_col": HEX_ACCENT_PURPLE,
                "badge_rgb": RGB_ACCENT_PURPLE,
                "lines": [
                    "• Proof-of-Concept Digital Twin: Proved feasibility of coupling EHR baselines with CGM telemetry.",
                    "• Leak-Free Machine Learning: Demonstrated rigorous 45-minute embargo buffer implementation.",
                    "• Exploratory Sandbox: Delivered interactive, non-destructive counterfactual what-if simulation.",
                    "• Safety by Design: Built decoupled rule-based low-glucose alerts and transparent limitation notices.",
                    "• Enterprise Local Architecture: Implemented full Argon2id authentication and ReportLab PDF reporting."
                ]
            },
            {
                "col": "right",
                "title": "Future Research Horizons",
                "badge": "Next Steps",
                "badge_col": HEX_ACCENT_TEAL,
                "badge_rgb": RGB_ACCENT_TEAL,
                "lines": [
                    "1. Hypoglycemia Simulation: Model missed meals, insulin stacking, and strenuous exercise.",
                    "2. Open Simulators: Integrate with established UVA/Padova simulators (e.g., simglucose).",
                    "3. Real Clinical Benchmarking: Validate against de-identified clinical datasets (OhioT1DM / Tidepool).",
                    "4. Deep Recurrent Architectures: Experiment with Temporal Fusion Transformers (TFT) and LSTMs.",
                    "5. Pharmacokinetic Modeling: Incorporate active insulin-on-board (IOB) clearance equations."
                ]
            }
        ],
        "footer": "TwinSense AI — Developed for Academic Innovation & Healthcare Engineering Demonstration"
    }
]


# -------------------------------------------------------------
# PowerPoint (.pptx) Generator
# -------------------------------------------------------------
def generate_pptx(output_path: Path):
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank_layout = prs.slide_layouts[6] # Blank slide
    
    for slide_data in SLIDES_DATA:
        slide = prs.slides.add_slide(blank_layout)
        
        # 1. Background Fill
        bg = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, 0, 0, Inches(13.333), Inches(7.5))
        bg.fill.solid()
        bg.fill.fore_color.rgb = RGB_BG
        bg.line.color.rgb = RGB_BG
        
        # 2. Header Strip Container
        header_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.5), Inches(0.35), Inches(12.333), Inches(1.1))
        header_box.fill.solid()
        header_box.fill.fore_color.rgb = RGB_CARD
        header_box.line.color.rgb = RGB_BORDER
        header_box.line.width = Pt(1.2)
        
        # Header Category Pill
        cat_pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.7), Inches(0.48), Inches(1.8), Inches(0.28))
        cat_pill.fill.solid()
        cat_pill.fill.fore_color.rgb = RGBColor(30, 20, 60)
        cat_pill.line.color.rgb = RGB_ACCENT_PURPLE
        cat_pill.line.width = Pt(1)
        tf_cat = cat_pill.text_frame
        tf_cat.word_wrap = True
        tf_cat.margin_left = tf_cat.margin_right = tf_cat.margin_top = tf_cat.margin_bottom = 0
        p_cat = tf_cat.paragraphs[0]
        p_cat.text = slide_data["category"]
        p_cat.font.size = Pt(8.5)
        p_cat.font.bold = True
        p_cat.font.color.rgb = RGB_ACCENT_PURPLE
        p_cat.alignment = PP_ALIGN.CENTER
        
        # Slide Tag (Right side of header)
        tag_pill = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(10.7), Inches(0.48), Inches(1.9), Inches(0.28))
        tag_pill.fill.solid()
        tag_pill.fill.fore_color.rgb = RGBColor(20, 30, 50)
        tag_pill.line.color.rgb = RGB_ACCENT_TEAL
        tag_pill.line.width = Pt(1)
        tf_tag = tag_pill.text_frame
        tf_tag.word_wrap = True
        tf_tag.margin_left = tf_tag.margin_right = tf_tag.margin_top = tf_tag.margin_bottom = 0
        p_tag = tf_tag.paragraphs[0]
        p_tag.text = slide_data["tag"]
        p_tag.font.size = Pt(8.5)
        p_tag.font.bold = True
        p_tag.font.color.rgb = RGB_ACCENT_TEAL
        p_tag.alignment = PP_ALIGN.CENTER
        
        # Header Text (Title + Subtitle)
        tb_head = slide.shapes.add_textbox(Inches(0.7), Inches(0.78), Inches(9.8), Inches(0.6))
        tf_head = tb_head.text_frame
        tf_head.word_wrap = True
        tf_head.margin_left = tf_head.margin_right = tf_head.margin_top = tf_head.margin_bottom = 0
        
        p_title = tf_head.paragraphs[0]
        p_title.text = f"{slide_data['slide_num']}. {slide_data['title']}"
        p_title.font.size = Pt(16.5)
        p_title.font.bold = True
        p_title.font.color.rgb = RGB_TEXT_WHITE
        
        p_sub = tf_head.add_paragraph()
        p_sub.text = slide_data["subtitle"]
        p_sub.font.size = Pt(9.5)
        p_sub.font.italic = True
        p_sub.font.color.rgb = RGB_TEXT_MUTED
        
        # 3. Two Content Cards (Left & Right)
        card_w = Inches(5.98)
        card_h = Inches(5.0)
        card_y = Inches(1.6)
        
        for idx, card in enumerate(slide_data["cards"]):
            cx = Inches(0.5) if idx == 0 else Inches(6.85)
            
            # Card background shape
            c_box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx, card_y, card_w, card_h)
            c_box.fill.solid()
            c_box.fill.fore_color.rgb = RGB_CARD
            c_box.line.color.rgb = RGB_BORDER
            c_box.line.width = Pt(1.2)
            
            # Card Header Pill
            c_badge = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, cx + Inches(0.3), card_y + Inches(0.25), Inches(2.2), Inches(0.32))
            c_badge.fill.solid()
            c_badge.fill.fore_color.rgb = RGBColor(18, 14, 34)
            c_badge.line.color.rgb = card["badge_rgb"]
            c_badge.line.width = Pt(1.0)
            tf_b = c_badge.text_frame
            tf_b.word_wrap = True
            tf_b.margin_left = tf_b.margin_right = tf_b.margin_top = tf_b.margin_bottom = 0
            p_b = tf_b.paragraphs[0]
            p_b.text = card["badge"]
            p_b.font.size = Pt(8.5)
            p_b.font.bold = True
            p_b.font.color.rgb = card["badge_rgb"]
            p_b.alignment = PP_ALIGN.CENTER
            
            # Card Title
            tb_ctitle = slide.shapes.add_textbox(cx + Inches(0.3), card_y + Inches(0.68), card_w - Inches(0.6), Inches(0.4))
            tf_ctitle = tb_ctitle.text_frame
            tf_ctitle.word_wrap = True
            tf_ctitle.margin_left = tf_ctitle.margin_right = tf_ctitle.margin_top = tf_ctitle.margin_bottom = 0
            p_ctitle = tf_ctitle.paragraphs[0]
            p_ctitle.text = card["title"]
            p_ctitle.font.size = Pt(13.0)
            p_ctitle.font.bold = True
            p_ctitle.font.color.rgb = RGB_TEXT_WHITE
            
            # Dividing Line
            c_line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, cx + Inches(0.3), card_y + Inches(1.15), card_w - Inches(0.6), Inches(0.015))
            c_line.fill.solid()
            c_line.fill.fore_color.rgb = RGB_BORDER
            c_line.line.color.rgb = RGB_BORDER
            
            # Bullet Lines
            tb_lines = slide.shapes.add_textbox(cx + Inches(0.3), card_y + Inches(1.25), card_w - Inches(0.6), card_h - Inches(1.4))
            tf_lines = tb_lines.text_frame
            tf_lines.word_wrap = True
            tf_lines.margin_left = tf_lines.margin_right = tf_lines.margin_top = tf_lines.margin_bottom = 0
            
            for line_idx, line in enumerate(card["lines"]):
                p_l = tf_lines.paragraphs[0] if line_idx == 0 else tf_lines.add_paragraph()
                p_l.text = line
                p_l.font.size = Pt(9.5)
                p_l.space_after = Pt(8)
                if "CRITICAL LIMITATION" in line or "100% Synthetic" in line or "Not Clinically Validated" in line or "ZERO" in line:
                    p_l.font.bold = True
                    p_l.font.color.rgb = RGB_ACCENT_ROSE
                elif "89.29%" in line or "0.8917" in line:
                    p_l.font.bold = True
                    p_l.font.color.rgb = RGB_ACCENT_GREEN
                elif line.startswith("• "):
                    p_l.font.color.rgb = RGB_TEXT_BODY
                else:
                    p_l.font.color.rgb = RGB_TEXT_MUTED
                    
        # 4. Footer Bar
        tb_foot = slide.shapes.add_textbox(Inches(0.5), Inches(6.8), Inches(12.333), Inches(0.35))
        tf_foot = tb_foot.text_frame
        tf_foot.word_wrap = True
        tf_foot.margin_left = tf_foot.margin_right = tf_foot.margin_top = tf_foot.margin_bottom = 0
        p_foot = tf_foot.paragraphs[0]
        p_foot.text = slide_data["footer"]
        p_foot.font.size = Pt(8.0)
        p_foot.font.color.rgb = RGB_TEXT_MUTED
        p_foot.alignment = PP_ALIGN.CENTER

    prs.save(str(output_path))
    print(f"Successfully generated PowerPoint presentation at: {output_path}")


# -------------------------------------------------------------
# PDF Presentation Generator (ReportLab)
# -------------------------------------------------------------
def generate_pdf(output_path: Path):
    W = 960.0  # 16:9 widescreen in points (13.333 in)
    H = 540.0  # (7.5 in)
    
    c = canvas.Canvas(str(output_path), pagesize=(W, H))
    
    for slide_data in SLIDES_DATA:
        # 1. Background
        c.setFillColor(HexColor(HEX_BG))
        c.rect(0, 0, W, H, fill=1, stroke=0)
        
        # 2. Header Container
        c.setFillColor(HexColor(HEX_CARD))
        c.setStrokeColor(HexColor(HEX_BORDER))
        c.setLineWidth(1)
        c.roundRect(30, H - 95, W - 60, 75, 6, stroke=1, fill=1)
        
        # Category Pill
        c.setFillColor(HexColor("#1E143C"))
        c.setStrokeColor(HexColor(HEX_ACCENT_PURPLE))
        c.setLineWidth(0.8)
        c.roundRect(45, H - 42, 120, 16, 4, stroke=1, fill=1)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(HexColor(HEX_ACCENT_PURPLE))
        c.drawCentredString(105, H - 31, slide_data["category"])
        
        # Tag Pill
        c.setFillColor(HexColor("#142036"))
        c.setStrokeColor(HexColor(HEX_ACCENT_TEAL))
        c.roundRect(W - 175, H - 42, 130, 16, 4, stroke=1, fill=1)
        c.setFont("Helvetica-Bold", 7.5)
        c.setFillColor(HexColor(HEX_ACCENT_TEAL))
        c.drawCentredString(W - 110, H - 31, slide_data["tag"])
        
        # Header Text
        c.setFont("Helvetica-Bold", 15)
        c.setFillColor(HexColor(HEX_TEXT_WHITE))
        c.drawString(45, H - 65, f"{slide_data['slide_num']}. {slide_data['title']}")
        
        c.setFont("Helvetica-Oblique", 8.5)
        c.setFillColor(HexColor(HEX_TEXT_MUTED))
        c.drawString(45, H - 82, slide_data["subtitle"])
        
        # 3. Two Content Cards
        card_w = (W - 80) / 2.0
        card_h = H - 145
        card_y = 35
        
        for idx, card in enumerate(slide_data["cards"]):
            cx = 30 if idx == 0 else 30 + card_w + 20
            
            # Card background
            c.setFillColor(HexColor(HEX_CARD))
            c.setStrokeColor(HexColor(HEX_BORDER))
            c.setLineWidth(1.2)
            c.roundRect(cx, card_y, card_w, card_h, 8, stroke=1, fill=1)
            
            # Card Badge Pill
            b_col = HexColor(card["badge_col"])
            c.setFillColor(HexColor("#120E22"))
            c.setStrokeColor(b_col)
            c.setLineWidth(0.8)
            c.roundRect(cx + 18, card_y + card_h - 32, 130, 18, 4, stroke=1, fill=1)
            c.setFont("Helvetica-Bold", 7.5)
            c.setFillColor(b_col)
            c.drawCentredString(cx + 83, card_y + card_h - 20, card["badge"])
            
            # Card Title
            c.setFont("Helvetica-Bold", 12)
            c.setFillColor(HexColor(HEX_TEXT_WHITE))
            c.drawString(cx + 18, card_y + card_h - 52, card["title"])
            
            # Dividing Line
            c.setStrokeColor(HexColor(HEX_BORDER))
            c.setLineWidth(0.8)
            c.line(cx + 18, card_y + card_h - 60, cx + card_w - 18, card_y + card_h - 60)
            
            # Lines
            curr_y = card_y + card_h - 78
            for line in card["lines"]:
                c.setFont("Helvetica", 8.0)
                if "CRITICAL LIMITATION" in line or "100% Synthetic" in line or "Not Clinically Validated" in line or "ZERO" in line:
                    c.setFont("Helvetica-Bold", 8.0)
                    c.setFillColor(HexColor(HEX_ACCENT_ROSE))
                elif "89.29%" in line or "0.8917" in line:
                    c.setFont("Helvetica-Bold", 8.0)
                    c.setFillColor(HexColor(HEX_ACCENT_GREEN))
                elif line.startswith("• "):
                    c.setFillColor(HexColor(HEX_TEXT_BODY))
                else:
                    c.setFillColor(HexColor(HEX_TEXT_MUTED))
                
                # Simple text wrapping for PDF lines
                if len(line) > 65:
                    part1 = line[:65]
                    part2 = "   " + line[65:]
                    c.drawString(cx + 18, curr_y, part1)
                    curr_y -= 12
                    c.drawString(cx + 18, curr_y, part2)
                else:
                    c.drawString(cx + 18, curr_y, line)
                curr_y -= 15
                
        # 4. Footer Bar
        c.setFont("Helvetica", 7.0)
        c.setFillColor(HexColor(HEX_TEXT_MUTED))
        c.drawCentredString(W / 2.0, 18, slide_data["footer"])
        
        c.showPage()
        
    c.save()
    print(f"Successfully generated PDF presentation at: {output_path}")


def main():
    out_pptx = Path("reports/TwinSense_AI_Presentation.pptx")
    out_pdf = Path("reports/TwinSense_AI_Presentation.pdf")
    
    out_pptx.parent.mkdir(parents=True, exist_ok=True)
    generate_pptx(out_pptx)
    generate_pdf(out_pdf)


if __name__ == "__main__":
    main()
