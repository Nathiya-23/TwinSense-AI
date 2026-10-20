"""
TwinSense AI - Pydantic Request & Response Schemas
==================================================

Defines strict type validation, numeric ranges, and metadata responses.
All schemas reinforce the non-clinical synthetic nature of the application.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


# -------------------------------------------------------------
# Health Status
# -------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    database_connected: bool
    total_patients: int
    total_readings: int
    total_predictions_logged: int
    hypoglycemia_limitation: str
    clinical_disclaimer: str
    safety_warning: str = "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions."
    hypoglycemia_message: str = "Hypoglycemia prediction is not supported by the current model."
    active_model_version: str = "v1"



# -------------------------------------------------------------
# Patient Profiles
# -------------------------------------------------------------
class PatientProfile(BaseModel):
    patient_id: str
    age: int = Field(..., ge=1, le=125)
    bmi: float = Field(..., ge=10.0, le=75.0)
    diabetes_type: str
    baseline_hba1c: float = Field(..., ge=3.5, le=25.0)
    diabetes_duration_years: int = Field(..., ge=0, le=90)
    is_synthetic: bool = True
    data_source: str


class PatientListItem(BaseModel):
    patient_id: str
    age: int
    bmi: float
    diabetes_type: str
    baseline_hba1c: float
    diabetes_duration_years: int
    latest_reading_timestamp: Optional[str] = None
    latest_glucose_mg_dl: Optional[float] = None
    is_synthetic: bool = True


# -------------------------------------------------------------
# Wearable Readings
# -------------------------------------------------------------
class ReadingItem(BaseModel):
    timestamp: str
    glucose_mg_dl: float = Field(..., ge=30.0, le=500.0)
    heart_rate: int = Field(..., ge=40, le=220)
    steps: int = Field(..., ge=0, le=5000)
    meal_event: int = Field(..., ge=0, le=1)


class ReadingsResponse(BaseModel):
    patient_id: str
    count: int
    readings: List[ReadingItem]
    is_synthetic: bool = True
    clinical_disclaimer: str


# -------------------------------------------------------------
# Prediction Request & Response
# -------------------------------------------------------------
class PredictRequest(BaseModel):
    readings: Optional[List[ReadingItem]] = Field(
        None,
        description="Optional list of at least 6 recent 5-min readings. If omitted, latest readings from SQLite are used."
    )


# -------------------------------------------------------------
# General Wellness Suggestions
# -------------------------------------------------------------
class SuggestionsResponse(BaseModel):
    risk_class: Optional[int] = None
    risk_label: str
    is_elevated_risk: bool = False
    suggestions: List[str]
    escalation_line: Optional[str] = None
    hypoglycemia_note: str
    disclaimer: str
    why_am_i_seeing_this: Optional[str] = None


class PredictResponse(BaseModel):
    prediction_id: int
    patient_id: str
    current_timestamp: str
    predicted_target_timestamp: str
    prediction_horizon_minutes: int
    current_glucose_mg_dl: float
    predicted_risk_class: int
    risk_label: str
    class_probabilities: Dict[str, float]
    key_contributing_factors: List[str]
    hypoglycemia_limitation: str
    clinical_disclaimer: str
    safety_warning: str = "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions."
    hypoglycemia_message: str = "Hypoglycemia prediction is not supported by the current model."
    unreliable_prediction_message: str = "Unable to provide a reliable prediction. Check the latest glucose reading and seek appropriate medical guidance."
    is_current_glucose_in_target: Optional[bool] = True
    current_glucose_caution: Optional[str] = None
    is_stale: Optional[bool] = False
    suggestions: Optional[SuggestionsResponse] = None
    active_model_version: Optional[str] = "v1"
    hypoglycemia_supported: bool = False
    hypoglycemia_display_probability: str = "Not supported"
    low_glucose_safety_alert: Optional[str] = None


# -------------------------------------------------------------
# Prediction History
# -------------------------------------------------------------
class PredictionHistoryItem(BaseModel):
    id: int
    patient_id: str
    prediction_timestamp: str
    reading_timestamp: str
    predicted_target_timestamp: str
    prediction_horizon_minutes: int
    current_glucose_mg_dl: float
    predicted_risk_class: int
    risk_label: str
    probabilities: Dict[str, float]
    key_contributing_factors: List[str]
    safety_warning: str = "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions."


class PredictionHistoryResponse(BaseModel):
    patient_id: str
    count: int
    predictions: List[PredictionHistoryItem]
    hypoglycemia_limitation: str
    clinical_disclaimer: str
    safety_warning: str = "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions."


# -------------------------------------------------------------
# What-If Simulation
# -------------------------------------------------------------
class WhatIfRequest(BaseModel):
    hypothetical_delta_glucose: float = Field(
        0.0,
        ge=-150.0,
        le=150.0,
        description="Hypothetical instantaneous glucose shift in mg/dL (e.g. -20 for physical activity drop)."
    )
    hypothetical_delta_steps: int = Field(
        0,
        ge=0,
        le=5000,
        description="Hypothetical additional steps in previous 15 minutes (e.g. 300 for a post-meal walk)."
    )
    scenario_description: str = Field(
        "Post-Meal Activity Simulation",
        max_length=120,
        description="User-facing label for the scenario."
    )


class WhatIfResponse(BaseModel):
    patient_id: str
    scenario_description: str
    is_hypothetical_simulation: bool
    hypothetical_adjustments: Dict[str, Any]
    observed_result: Dict[str, Any]
    hypothetical_result: Dict[str, Any]
    risk_status_changed: bool
    simulation_notice: str
    hypoglycemia_limitation: str
    clinical_disclaimer: str
    safety_warning: str = "AI predictions are estimates, not guarantees. Actual glucose levels may change unexpectedly. Do not rely on this prediction alone for medical decisions."
    hypoglycemia_message: str = "Hypoglycemia prediction is not supported by the current model."


# -------------------------------------------------------------
# Authentication & User Management
# -------------------------------------------------------------
class RegisterRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=100, description="User's full name")
    email: str = Field(..., max_length=255, description="Valid email address")
    password: str = Field(..., min_length=8, max_length=128, description="Password (at least 8 chars)")
    confirm_password: str = Field(..., min_length=8, max_length=128, description="Password confirmation")


class LoginRequest(BaseModel):
    email: str = Field(..., max_length=255, description="Registered email address")
    password: str = Field(..., min_length=1, max_length=128, description="Account password")


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: str


class AuthSuccessResponse(BaseModel):
    status: str
    message: str
    user: UserResponse
    csrf_token: Optional[str] = None


class LogoutResponse(BaseModel):
    status: str
    message: str


class CurrentUserResponse(BaseModel):
    authenticated: bool
    user: Optional[UserResponse] = None
    csrf_token: Optional[str] = None

