"""
TwinSense AI - General Suggestions Module
=========================================

Provides rule-based, non-clinical wellness suggestions based on the
existing predicted risk class from the Digital Twin engine.

CRITICAL DESIGN & SAFETY CONSTRAINTS:
-------------------------------------
- Rule-based only: fixed, human-reviewable mapping from risk class to suggestions.
- Zero LLM calls, zero randomness, zero new machine learning models.
- Never recommends insulin or medication dosing, specific carbohydrate amounts,
  medical diagnoses, or treatment instructions.
- Never guarantees that a patient is clinically safe or that glucose will become normal.
- Uses cautious, informative language ("consider", "you may want to", "general information").
- Elevated risk classes include an explicit escalation line.
- Every response includes the mandatory synthetic prototype disclaimer and
  the fixed hypoglycemia limitation statement.

Requires review by a qualified clinician before any real-world use.
"""

from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------------
# Mandatory Safety Disclaimers & Limitations
# ---------------------------------------------------------------------------

SUGGESTIONS_DISCLAIMER = (
    "SYNTHETIC DATA \u2014 NOT CLINICALLY VALIDATED. "
    "This prototype must not be used for diagnosis, treatment, insulin dosing, or medical decisions."
)

HYPOGLYCEMIA_PANEL_NOTE = (
    "Low-glucose risk is not predicted by this prototype. "
    "A 0% probability does not mean hypoglycemia is impossible. "
    "If you experience symptoms such as shakiness, sweating, confusion, or dizziness, "
    "follow your clinician's guidance and seek medical help."
)

HYPOGLYCEMIA_PANEL_NOTE_V2 = (
    "IMPORTANT (Model v2 — SYNTHETIC ONLY): Hypoglycemia prediction is supported only on synthetic examples "
    "and is NOT clinically validated. A low probability does not rule out hypoglycemia. "
    "If you experience symptoms such as shakiness, sweating, confusion, or dizziness, "
    "follow your clinician's guidance and seek medical help."
)

ESCALATION_LINE = (
    "If you feel unwell or symptoms worsen, contact a healthcare professional or local emergency services."
)

FALLBACK_SUGGESTION = "No suggestions available for this result."

# ---------------------------------------------------------------------------
# Fixed Human-Reviewable Suggestion Mapping
# Requires review by a qualified clinician before any real-world use.
# ---------------------------------------------------------------------------

SUGGESTIONS_MAP: Dict[int, Dict[str, Any]] = {
    # Class 1: Hypoglycemia (<70 mg/dL) [UNSUPPORTED by Model]
    1: {
        "label": "Hypoglycemia (<70 mg/dL) [UNSUPPORTED - Model Cannot Detect]",
        "is_elevated_risk": True,
        "suggestions": [
            "Low-glucose risk is not predicted by this prototype; confirm any suspected low readings immediately with an approved blood glucose meter.",
            "Review any physical sensations you may be experiencing and follow your clinician's personalized instructions for low readings.",
            "If you feel unwell or symptoms worsen, contact a healthcare professional or local emergency services."
        ]
    },

    # Class 2: In-Range Trajectory (70-180 mg/dL)
    2: {
        "label": "Predicted In-Range Trajectory (70-180 mg/dL)",
        "is_elevated_risk": False,
        "suggestions": [
            "Consider maintaining regular hydration and continuing your standard daily wellness routines.",
            "You may want to recheck your glucose level with your usual monitoring method according to your routine schedule.",
            "Review your recent meals and physical activity timeline on the chart to observe how your body typically responds.",
            "Keep in mind that predicted trajectories are mathematical estimates based on synthetic data, not guarantees of future glucose levels.",
            "Consider discussing routine glucose patterns and lifestyle habits with your healthcare provider during your regular appointments."
        ]
    },

    # Class 3: Hyperglycemia Risk (>180 mg/dL)
    3: {
        "label": "Potential Hyperglycemia Risk (>180 mg/dL)",
        "is_elevated_risk": True,
        "suggestions": [
            "Consider drinking water to stay hydrated as part of general wellness support.",
            "You may want to recheck your glucose level with your usual monitoring method to verify the current reading.",
            "Review the upward trend on the historical chart and reflect on recent meals, activity patterns, or stress levels.",
            "Follow your personal diabetes wellness plan as guided by your healthcare provider.",
            "If you feel unwell or symptoms worsen, contact a healthcare professional or local emergency services."
        ]
    }
}


def get_suggestions_for_risk_class(
    risk_class: Optional[int],
    current_glucose: Optional[float] = None,
    model_version: Optional[str] = None
) -> Dict[str, Any]:
    """
    Returns rule-based, non-clinical suggestions for a given predicted risk class.

    Safety characteristics:
    - Pure lookup, no ML inference, no stochastic generation.
    - Always includes the exact disclaimer and hypoglycemia note.
    - Elevated-risk classes (1 and 3) include the escalation line.
    - Missing or unknown classes return the fallback suggestion gracefully.
    """
    try:
        from app.config import is_v2_active
        v2_flag = (model_version == "v2") if model_version else is_v2_active()
    except Exception:
        v2_flag = (model_version == "v2")
    active_hypo_note = HYPOGLYCEMIA_PANEL_NOTE_V2 if v2_flag else HYPOGLYCEMIA_PANEL_NOTE

    # Safe fallback if class is missing or not reviewed
    if risk_class not in SUGGESTIONS_MAP:
        return {
            "risk_class": risk_class,
            "risk_label": "Unknown Class",
            "is_elevated_risk": False,
            "suggestions": [FALLBACK_SUGGESTION],
            "escalation_line": None,
            "hypoglycemia_note": active_hypo_note,
            "disclaimer": SUGGESTIONS_DISCLAIMER,
            "why_am_i_seeing_this": None
        }

    class_info = SUGGESTIONS_MAP[risk_class]
    label = class_info["label"]
    is_elevated = class_info["is_elevated_risk"]
    suggestions_list = list(class_info["suggestions"])

    # Build optional "Why am I seeing this?" line with real values only
    why_line = None
    if current_glucose is not None:
        why_line = (
            f"Why am I seeing this? The forecast estimated Class {risk_class} ({label}) "
            f"based on a current observed glucose of {float(current_glucose):.1f} mg/dL."
        )
    else:
        why_line = f"Why am I seeing this? The forecast estimated Class {risk_class} ({label})."

    return {
        "risk_class": risk_class,
        "risk_label": label,
        "is_elevated_risk": is_elevated,
        "suggestions": suggestions_list,
        "escalation_line": ESCALATION_LINE if is_elevated else None,
        "hypoglycemia_note": active_hypo_note,
        "disclaimer": SUGGESTIONS_DISCLAIMER,
        "why_am_i_seeing_this": why_line
    }
