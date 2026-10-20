"""
TwinSense AI - FastAPI Backend Application
==========================================

Local REST API serving Digital Twin risk estimates and telemetry.
Designed strictly for academic innovation prototype evaluation.
"""

from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Query, Path as FastPath, status, Depends, Request, HTTPException
from fastapi.responses import JSONResponse, FileResponse, Response, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.database import init_db, populate_from_csv_if_empty, get_db_connection, DB_PATH
from app.schemas import (
    HealthResponse,
    PatientListItem,
    PatientProfile,
    ReadingsResponse,
    ReadingItem,
    PredictRequest,
    PredictResponse,
    PredictionHistoryResponse,
    PredictionHistoryItem,
    WhatIfRequest,
    WhatIfResponse,
    RegisterRequest,
    LoginRequest,
    AuthSuccessResponse,
    LogoutResponse,
    CurrentUserResponse,
    UserResponse,
    SuggestionsResponse
)
from app.auth import (
    get_current_user,
    get_current_user_optional,
    register_user,
    authenticate_user,
    create_session,
    delete_session,
    set_auth_cookies,
    clear_auth_cookies,
    SESSION_COOKIE_NAME
)
from app import services
from app import reports as report_gen
from app.suggestions import get_suggestions_for_risk_class
from src.twin_engine import (
    get_engine,
    UNSUPPORTED_HYPOGLYCEMIA_WARNING,
    CLINICAL_PROTOTYPE_DISCLAIMER
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application startup: Ensures local SQLite database is created and safely populated.
    """
    init_db()
    populate_from_csv_if_empty()
    # Eagerly load model
    get_engine()
    yield


app = FastAPI(
    title="TwinSense AI - Healthcare Digital Twin API",
    description=(
        "Local REST API providing 45-minute continuous glucose risk estimates for simulated diabetic patients. "
        "Strictly a research prototype using synthetic development data. Not clinically validated."
    ),
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for local development and dashboard communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

STATIC_DIR = Path(__file__).resolve().parent / "static"
INDEX_HTML = STATIC_DIR / "index.html"
LOGIN_HTML = STATIC_DIR / "login.html"
REGISTER_HTML = STATIC_DIR / "register.html"

# Mount static directory for stylesheets, scripts, and assets
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# -------------------------------------------------------------
# Frontend Routes
# -------------------------------------------------------------
@app.get("/", include_in_schema=False)
def serve_dashboard(request: Request):
    """
    Serves the frontend TwinSense AI HTML dashboard for authenticated users.
    Redirects unauthenticated users to /login.
    """
    user = get_current_user_optional(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    if not INDEX_HTML.exists():
        return JSONResponse({"status": "Dashboard asset missing"}, status_code=404)
    return FileResponse(INDEX_HTML)


@app.get("/login", include_in_schema=False)
def serve_login(request: Request):
    """
    Serves the TwinSense AI login page.
    Redirects already authenticated users directly to the dashboard.
    """
    user = get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not LOGIN_HTML.exists():
        return JSONResponse({"status": "Login page asset missing"}, status_code=404)
    return FileResponse(LOGIN_HTML)


@app.get("/register", include_in_schema=False)
def serve_register(request: Request):
    """
    Serves the TwinSense AI registration page.
    Redirects already authenticated users directly to the dashboard.
    """
    user = get_current_user_optional(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    if not REGISTER_HTML.exists():
        return JSONResponse({"status": "Registration page asset missing"}, status_code=404)
    return FileResponse(REGISTER_HTML)


# -------------------------------------------------------------
# Authentication & Session Endpoints
# -------------------------------------------------------------
@app.post("/api/auth/register", response_model=AuthSuccessResponse, status_code=status.HTTP_201_CREATED, tags=["Authentication"])
def register_account(request_data: RegisterRequest, response: Response):
    """
    Registers a new user with Argon2id password hashing and logs them in.
    Rejects duplicate email addresses and enforces password criteria.
    Sets secure HttpOnly session cookie and returns user details with CSRF token.
    """
    user = register_user(
        full_name=request_data.full_name,
        email=request_data.email,
        password=request_data.password,
        confirm_password=request_data.confirm_password
    )
    session = create_session(user["id"])
    set_auth_cookies(response, session["session_id"], session["csrf_token"])

    return AuthSuccessResponse(
        status="success",
        message="Account created successfully.",
        user=UserResponse(**user),
        csrf_token=session["csrf_token"]
    )


@app.post("/api/auth/login", response_model=AuthSuccessResponse, tags=["Authentication"])
def login_account(request_data: LoginRequest, response: Response):
    """
    Authenticates user credentials and starts a secure server-managed session.
    Sets secure HttpOnly session cookie and CSRF cookie.
    Returns safe generic error on invalid credentials without revealing email existence.
    """
    user = authenticate_user(request_data.email, request_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email address or password. Please verify your credentials."
        )

    session = create_session(user["id"])
    set_auth_cookies(response, session["session_id"], session["csrf_token"])

    return AuthSuccessResponse(
        status="success",
        message="Login successful.",
        user=UserResponse(**user),
        csrf_token=session["csrf_token"]
    )


@app.post("/api/auth/logout", response_model=LogoutResponse, tags=["Authentication"])
def logout_account(request: Request, response: Response):
    """
    Terminates the active session in SQLite and clears authentication cookies.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if not session_id:
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            session_id = auth_header[7:].strip()

    if session_id:
        delete_session(session_id)

    clear_auth_cookies(response)
    return LogoutResponse(status="success", message="Successfully logged out.")


@app.get("/logout", include_in_schema=False)
def logout_get_redirect(request: Request):
    """
    Convenience browser redirect endpoint to log out and return to the login screen.
    """
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    if session_id:
        delete_session(session_id)

    redirect = RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    clear_auth_cookies(redirect)
    return redirect


@app.get("/api/auth/me", response_model=CurrentUserResponse, tags=["Authentication"])
def get_current_user_profile(request: Request):
    """
    Returns profile information and CSRF token for the currently authenticated user.
    Returns authenticated=False if no valid session exists.
    """
    user = get_current_user_optional(request)
    if not user:
        return CurrentUserResponse(authenticated=False, user=None, csrf_token=None)

    return CurrentUserResponse(
        authenticated=True,
        user=UserResponse(id=user["id"], email=user["email"], full_name=user["full_name"]),
        csrf_token=user["csrf_token"]
    )


# -------------------------------------------------------------
# 1. Health & Status
# -------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse, tags=["System Health"])
def get_health_status():
    """
    Verifies model loading state, database connectivity, and record counts.
    """
    engine = get_engine()
    model_loaded = (engine.model is not None)

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM patients")
    total_patients = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM readings")
    total_readings = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM predictions")
    total_predictions = cursor.fetchone()[0]
    conn.close()

    return HealthResponse(
        status="HEALTHY",
        model_loaded=model_loaded,
        database_connected=True,
        total_patients=total_patients,
        total_readings=total_readings,
        total_predictions_logged=total_predictions,
        hypoglycemia_limitation=getattr(engine, "hypoglycemia_warning", UNSUPPORTED_HYPOGLYCEMIA_WARNING),
        clinical_disclaimer=CLINICAL_PROTOTYPE_DISCLAIMER,
        active_model_version=getattr(engine, "active_model_version", "v1")
    )


# -------------------------------------------------------------
# 2. Patients Endpoints
# -------------------------------------------------------------
@app.get("/api/patients", response_model=List[PatientListItem], tags=["Patients"])
def list_patients():
    """
    Lists all available synthetic patients along with their most recent telemetry status.
    """
    return services.get_all_patients()


@app.get("/api/patients/{patient_id}", response_model=PatientProfile, tags=["Patients"])
def get_patient(
    patient_id: str = FastPath(..., description="Synthetic patient identifier (e.g. SYNTH_PAT_001)")
):
    """
    Fetches the static EHR baseline profile for a specific patient.
    """
    return services.get_patient_profile(patient_id)


# -------------------------------------------------------------
# 3. Telemetry Readings
# -------------------------------------------------------------
@app.get("/api/patients/{patient_id}/readings", response_model=ReadingsResponse, tags=["Telemetry"])
def get_patient_readings(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    limit: int = Query(50, ge=6, le=500, description="Number of recent readings to fetch")
):
    """
    Returns recent continuous glucose monitoring and wearable readings in chronological order.
    """
    readings = services.get_recent_readings(patient_id, limit=limit)
    return ReadingsResponse(
        patient_id=patient_id,
        count=len(readings),
        readings=[ReadingItem(**r) for r in readings],
        is_synthetic=True,
        clinical_disclaimer=CLINICAL_PROTOTYPE_DISCLAIMER
    )


# -------------------------------------------------------------
# 4. Predictions & Inference
# -------------------------------------------------------------
@app.post("/api/patients/{patient_id}/predict", response_model=PredictResponse, status_code=status.HTTP_201_CREATED, tags=["Digital Twin Inference"])
def predict_patient_risk_endpoint(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    request: PredictRequest = PredictRequest()
):
    """
    Executes a 45-minute forward glucose risk forecast using TwinEngine.
    If custom readings are omitted in the body, uses the patient's latest readings from SQLite.
    Logs prediction event to SQLite history.
    """
    custom_list = [r.model_dump() for r in request.readings] if request.readings else None
    result = services.predict_for_patient(patient_id, custom_readings=custom_list)
    return PredictResponse(**result)


@app.get("/api/patients/{patient_id}/predictions", response_model=PredictionHistoryResponse, tags=["Digital Twin Inference"])
def get_patient_predictions(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    limit: int = Query(20, ge=1, le=100, description="Max history entries to return")
):
    """
    Retrieves logged prediction history for the specified patient.
    """
    history = services.get_prediction_history(patient_id, limit=limit)
    return PredictionHistoryResponse(
        patient_id=patient_id,
        count=len(history),
        predictions=[PredictionHistoryItem(**h) for h in history],
        hypoglycemia_limitation=UNSUPPORTED_HYPOGLYCEMIA_WARNING,
        clinical_disclaimer=CLINICAL_PROTOTYPE_DISCLAIMER
    )


# -------------------------------------------------------------
# 5. What-If Counterfactual Simulation
# -------------------------------------------------------------
@app.post("/api/patients/{patient_id}/what-if", response_model=WhatIfResponse, tags=["What-If Simulation"])
def what_if_simulation_endpoint(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    request: WhatIfRequest = ...
):
    """
    Simulates a hypothetical change in glucose trajectory or recent step activity
    and contrasts against observed model prediction without mutating database records.
    """
    result = services.what_if_for_patient(
        patient_id=patient_id,
        hypothetical_delta_glucose=request.hypothetical_delta_glucose,
        hypothetical_delta_steps=request.hypothetical_delta_steps,
        scenario_description=request.scenario_description
    )
    return WhatIfResponse(**result)


# -------------------------------------------------------------
# 5.5. General Wellness Suggestions
# -------------------------------------------------------------
@app.get("/api/suggestions", response_model=SuggestionsResponse, tags=["Suggestions"])
def get_general_suggestions(
    risk_class: Optional[int] = Query(None, description="Predicted risk class integer"),
    glucose: Optional[float] = Query(None, description="Optional current observed glucose in mg/dL")
):
    """
    Returns rule-based, non-clinical wellness suggestions.
    If risk_class is omitted or unreviewed, returns the graceful fallback.
    No model inference or prediction creation is triggered.
    """
    return get_suggestions_for_risk_class(risk_class, current_glucose=glucose)


@app.get("/api/suggestions/{risk_class}", response_model=SuggestionsResponse, tags=["Suggestions"])
def get_class_suggestions(
    risk_class: int = FastPath(..., description="Predicted risk class integer (e.g. 1, 2, 3)"),
    glucose: Optional[float] = Query(None, description="Optional current observed glucose in mg/dL")
):
    """
    Returns rule-based, non-clinical wellness suggestions for the specified risk class.
    No model inference or prediction creation is triggered.
    """
    return get_suggestions_for_risk_class(risk_class, current_glucose=glucose)


# -------------------------------------------------------------
# 6. Report Export Endpoints (CSV & PDF)
# -------------------------------------------------------------
@app.get(
    "/api/patients/{patient_id}/report/csv",
    tags=["Report Export"],
    summary="Download CSV prediction report for a patient",
)
def download_csv_report(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    prediction_id: Optional[int] = Query(None, description="Specific prediction ID (defaults to latest)"),
):
    """
    Generates and returns a downloadable UTF-8 CSV file containing the patient's
    most recent (or specified) prediction and all mandatory safety disclaimers.
    No new model inference is triggered.
    """
    profile = services.get_patient_profile(patient_id)
    prediction = report_gen.get_latest_prediction_for_patient(
        patient_id, prediction_id=prediction_id
    )
    csv_text = report_gen.generate_csv_report(profile, prediction)
    filename = report_gen.safe_report_filename(patient_id, "csv")
    return Response(
        content=csv_text.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Patient": patient_id,
        },
    )


@app.get(
    "/api/patients/{patient_id}/report/pdf",
    tags=["Report Export"],
    summary="Download PDF prediction report for a patient",
)
def download_pdf_report(
    patient_id: str = FastPath(..., description="Synthetic patient identifier"),
    prediction_id: Optional[int] = Query(None, description="Specific prediction ID (defaults to latest)"),
):
    """
    Generates and returns a downloadable PDF report with dark-purple/violet branding,
    class probabilities, contributing factors, and mandatory safety disclaimers.
    No new model inference is triggered.
    """
    profile = services.get_patient_profile(patient_id)
    prediction = report_gen.get_latest_prediction_for_patient(
        patient_id, prediction_id=prediction_id
    )
    try:
        pdf_bytes = report_gen.generate_pdf_report(profile, prediction)
    except ImportError as exc:
        return JSONResponse(
            status_code=503,
            content={
                "detail": (
                    "PDF generation requires the 'reportlab' package. "
                    f"Install it with: pip install reportlab>=4.0.0  ({exc})"
                )
            },
        )
    filename = report_gen.safe_report_filename(patient_id, "pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-Patient": patient_id,
        },
    )
