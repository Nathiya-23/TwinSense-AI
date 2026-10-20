"""
TwinSense AI - Live API Endpoint Verification Script
=====================================================
Tests all API endpoints against the running server.
Reports pass/fail for each check. Not a replacement for
unit tests - verifies actual network/DB integration.
"""

import urllib.request
import urllib.error
import json
import sys
import hashlib
from pathlib import Path

BASE = "http://127.0.0.1:8001"
RESULTS = []

def check(name, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    RESULTS.append((status, name, detail))
    print(f"  [{status}] {name}" + (f" - {detail}" if detail else ""))


def get(endpoint):
    r = urllib.request.urlopen(BASE + endpoint)
    return json.loads(r.read()), r.getcode()


def post(endpoint, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(
        BASE + endpoint, data=data,
        headers={"Content-Type": "application/json"}, method="POST"
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read()), r.getcode()


def expect_4xx(endpoint, payload=None, method="GET"):
    try:
        data = json.dumps(payload).encode() if payload else None
        req = urllib.request.Request(
            BASE + endpoint, data=data,
            headers={"Content-Type": "application/json"} if data else {},
            method=method
        )
        urllib.request.urlopen(req)
        return None, 200
    except urllib.error.HTTPError as e:
        return e.code


print("\n=== TwinSense AI - Live API Verification ===\n")

# ----------------------------------------------------------------
# 1. Health Endpoint
# ----------------------------------------------------------------
print("[1] GET /api/health")
h, code = get("/api/health")
check("HTTP 200 returned", code == 200)
check("status == HEALTHY", h.get("status") == "HEALTHY")
check("model_loaded == True", h.get("model_loaded") is True)
check("database_connected == True", h.get("database_connected") is True)
check("total_patients == 10", h.get("total_patients") == 10)
check("total_readings == 20160", h.get("total_readings") == 20160)
check("hypoglycemia warning present", "CRITICAL LIMITATION" in h.get("hypoglycemia_limitation",""))
check("clinical disclaimer present", "FOR DEMONSTRATION ONLY" in h.get("clinical_disclaimer",""))

# ----------------------------------------------------------------
# 2. Patient List
# ----------------------------------------------------------------
print("\n[2] GET /api/patients")
patients, code = get("/api/patients")
check("HTTP 200 returned", code == 200)
check("Returns 10 patients", len(patients) == 10)
ids = [p["patient_id"] for p in patients]
check("SYNTH_PAT_001 present", "SYNTH_PAT_001" in ids)
check("SYNTH_PAT_010 present", "SYNTH_PAT_010" in ids)
check("All patients have is_synthetic field", all("is_synthetic" in p for p in patients))

# ----------------------------------------------------------------
# 3. Patient Profile - Valid
# ----------------------------------------------------------------
print("\n[3] GET /api/patients/SYNTH_PAT_001")
prof, code = get("/api/patients/SYNTH_PAT_001")
check("HTTP 200 returned", code == 200)
check("patient_id matches", prof.get("patient_id") == "SYNTH_PAT_001")
check("age is integer > 0", isinstance(prof.get("age"), int) and prof["age"] > 0)
check("bmi is float > 0", isinstance(prof.get("bmi"), float) and prof["bmi"] > 0)
check("is_synthetic is True", prof.get("is_synthetic") is True)

# ----------------------------------------------------------------
# 4. Patient Profile - Not Found
# ----------------------------------------------------------------
print("\n[4] GET /api/patients/INVALID_ID_XYZ (expect 404)")
code_404 = expect_4xx("/api/patients/INVALID_ID_XYZ")
check("HTTP 404 returned for unknown patient", code_404 == 404, f"Got {code_404}")

# ----------------------------------------------------------------
# 5. Readings Endpoint
# ----------------------------------------------------------------
print("\n[5] GET /api/patients/SYNTH_PAT_001/readings?limit=24")
readings, code = get("/api/patients/SYNTH_PAT_001/readings?limit=24")
check("HTTP 200 returned", code == 200)
check("patient_id matches", readings.get("patient_id") == "SYNTH_PAT_001")
check("count == 24", readings.get("count") == 24)
check("is_synthetic == True", readings.get("is_synthetic") is True)
check("clinical_disclaimer present", bool(readings.get("clinical_disclaimer")))
# Verify chronological order
timestamps = [r["timestamp"] for r in readings["readings"]]
check("Readings in chronological order", timestamps == sorted(timestamps))

# ----------------------------------------------------------------
# 6. Prediction Endpoint
# ----------------------------------------------------------------
print("\n[6] POST /api/patients/SYNTH_PAT_001/predict")
pred_before_count = h.get("total_predictions_logged", 0)
pred, code = post("/api/patients/SYNTH_PAT_001/predict", {})
check("HTTP 201 returned", code == 201)
check("patient_id matches", pred.get("patient_id") == "SYNTH_PAT_001")
check("risk_class in [2, 3]", pred.get("predicted_risk_class") in [2, 3])
check("prediction_horizon_minutes == 45", pred.get("prediction_horizon_minutes") == 45)
check("prediction_id is integer", isinstance(pred.get("prediction_id"), int))
check("contributing factors >= 4", len(pred.get("key_contributing_factors", [])) >= 4)
check("hypoglycemia_limitation present", "CRITICAL LIMITATION" in pred.get("hypoglycemia_limitation",""))
check("clinical_disclaimer present", "FOR DEMONSTRATION ONLY" in pred.get("clinical_disclaimer",""))
check("class_probabilities has 3 classes", len(pred.get("class_probabilities", {})) == 3)
check("hypo class prob == 0.0", pred.get("class_probabilities",{}).get("1_hypoglycemia") == 0.0)

# ----------------------------------------------------------------
# 7. Prediction History
# ----------------------------------------------------------------
print("\n[7] GET /api/patients/SYNTH_PAT_001/predictions")
hist, code = get("/api/patients/SYNTH_PAT_001/predictions")
check("HTTP 200 returned", code == 200)
check("patient_id matches", hist.get("patient_id") == "SYNTH_PAT_001")
check("count >= 1", hist.get("count", 0) >= 1)
check("hypoglycemia_limitation in history response", "CRITICAL LIMITATION" in hist.get("hypoglycemia_limitation",""))

# ----------------------------------------------------------------
# 8. Prediction Stored in DB (count incremented)
# ----------------------------------------------------------------
print("\n[8] Verifying prediction stored in DB")
h2, _ = get("/api/health")
check("Prediction count incremented after POST", h2.get("total_predictions_logged", 0) > pred_before_count,
      f"{pred_before_count} -> {h2.get('total_predictions_logged')}")

# ----------------------------------------------------------------
# 9. What-If Simulation - Valid
# ----------------------------------------------------------------
print("\n[9] POST /api/patients/SYNTH_PAT_001/what-if (valid)")
wi, code = post("/api/patients/SYNTH_PAT_001/what-if", {
    "hypothetical_delta_glucose": -20.0,
    "hypothetical_delta_steps": 350,
    "scenario_description": "Post-Walk Test"
})
check("HTTP 200 returned", code == 200)
check("patient_id matches", wi.get("patient_id") == "SYNTH_PAT_001")
check("is_hypothetical_simulation == True", wi.get("is_hypothetical_simulation") is True)
check("observed_result present", "observed_result" in wi)
check("hypothetical_result present", "hypothetical_result" in wi)
check("simulation_notice contains HYPOTHETICAL", "HYPOTHETICAL SIMULATION NOTICE" in wi.get("simulation_notice",""))
check("hypoglycemia_limitation present", "CRITICAL LIMITATION" in wi.get("hypoglycemia_limitation",""))

# ----------------------------------------------------------------
# 10. What-If - Invalid delta rejected
# ----------------------------------------------------------------
print("\n[10] POST /api/patients/SYNTH_PAT_001/what-if (out-of-bounds, expect 422)")
code_422 = expect_4xx("/api/patients/SYNTH_PAT_001/what-if",
                      {"hypothetical_delta_glucose": 999.0, "hypothetical_delta_steps": 0, "scenario_description": "Extreme"}, 
                      method="POST")
check("HTTP 422 returned for out-of-bounds delta", code_422 == 422, f"Got {code_422}")

# ----------------------------------------------------------------
# 11. Dashboard Root
# ----------------------------------------------------------------
print("\n[11] GET / (Dashboard HTML)")
r = urllib.request.urlopen(BASE + "/")
html = r.read().decode()
check("HTTP 200 returned", r.getcode() == 200)
check("Content-Type is text/html", "text/html" in r.headers.get("Content-Type",""))
check("TwinSense AI in HTML title", "TwinSense AI" in html)
check("Healthcare Digital Twin in HTML", "Healthcare Digital Twin" in html)
check("Synthetic Prototype notice visible", "Synthetic Prototype" in html)
check("CRITICAL MODEL LIMITATION visible", "CRITICAL MODEL LIMITATION" in html)
check("hypoglycemia warning in HTML", "hypoglycemia" in html.lower())
check("clinical_disclaimer in HTML", "NOT clinically validated" in html or "not clinically validated" in html.lower())

# ----------------------------------------------------------------
# 12. Static Assets
# ----------------------------------------------------------------
print("\n[12] Static Assets")
r_css = urllib.request.urlopen(BASE + "/static/style.css")
check("style.css returns 200", r_css.getcode() == 200)
check("style.css has text/css content-type", "text/css" in r_css.headers.get("Content-Type",""))

r_js = urllib.request.urlopen(BASE + "/static/app.js")
check("app.js returns 200", r_js.getcode() == 200)
js_text = r_js.read().decode()
check("app.js has no hardcoded external API URLs", "https://api." not in js_text and "openai" not in js_text.lower())
check("app.js uses relative API_BASE (empty string)", 'const API_BASE = ""' in js_text)

# ----------------------------------------------------------------
# 13. CSV File Integrity (unchanged after all API calls)
# ----------------------------------------------------------------
print("\n[13] CSV Integrity Check (unchanged by API)")
profiles_hash = hashlib.md5(Path("data/raw/patient_profiles.csv").read_bytes()).hexdigest()
ts_hash = hashlib.md5(Path("data/raw/glucose_timeseries.csv").read_bytes()).hexdigest()
check("patient_profiles.csv hash unchanged", profiles_hash == "8245431dd0b77a051707c2a09547a2d2",
      f"hash={profiles_hash}")
check("glucose_timeseries.csv hash unchanged", ts_hash == "28563652d6503c8af5f04a3e66d1c9f8",
      f"hash={ts_hash}")

# ----------------------------------------------------------------
# Summary
# ----------------------------------------------------------------
print("\n" + "="*50)
passes = sum(1 for r in RESULTS if r[0] == "PASS")
fails  = sum(1 for r in RESULTS if r[0] == "FAIL")
print(f"TOTAL: {passes} PASSED | {fails} FAILED | {len(RESULTS)} CHECKS")
if fails:
    print("\nFailed checks:")
    for s, n, d in RESULTS:
        if s == "FAIL":
            print(f"  - {n} {d}")
sys.exit(0 if fails == 0 else 1)
