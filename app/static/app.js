/**
 * TwinSense AI - Digital Twin Dashboard Application
 * =================================================
 * Pure Vanilla JavaScript & Native SVG Chart Engine.
 * Local API integration with zero external libraries or cloud dependencies.
 */

(function () {
    "use strict";

    // -------------------------------------------------------------
    // Configuration & State
    // -------------------------------------------------------------
    const API_BASE = ""; // Relative paths for same-origin local server
    let state = {
        patients: [],
        activePatientId: null,
        activeProfile: null,
        recentReadings: [],
        activePrediction: null,
        history: [],
        readingsLimit: 48,
        isLoadingReadings: false,
        isPredicting: false,
        isSimulating: false,
        csrfToken: null   // populated after /api/auth/me
    };

    // -------------------------------------------------------------
    // Timestamp Formatting Utilities (Consistent Historical Formatting)
    // -------------------------------------------------------------
    function formatDateTime(rawStr) {
        if (!rawStr) return "--";
        const clean = String(rawStr).replace("T", " ");
        const parts = clean.split(" ");
        if (parts.length >= 2) {
            const date = parts[0];
            const time = parts[1].slice(0, 5); // YYYY-MM-DD HH:MM
            return `${date} ${time}`;
        }
        return clean.slice(0, 16);
    }

    function formatTimeOnly(rawStr) {
        if (!rawStr) return "--";
        const clean = String(rawStr).replace("T", " ");
        const parts = clean.split(" ");
        if (parts.length >= 2) {
            return parts[1].slice(0, 5); // HH:MM
        }
        return clean.slice(0, 5);
    }

    // DOM Element References
    const elements = {
        systemHealthPill: document.getElementById("system-health-pill"),
        healthStatusText: document.getElementById("health-status-text"),
        modelStatusText: document.getElementById("model-status-text"),
        statTotalPatients: document.getElementById("stat-total-patients"),
        statActivePatient: document.getElementById("stat-active-patient"),
        statPatientType: document.getElementById("stat-patient-type"),
        statCurrentGlucose: document.getElementById("stat-current-glucose"),
        statLatestTimestamp: document.getElementById("stat-latest-timestamp"),
        statCurrentRisk: document.getElementById("stat-current-risk"),
        patientSelect: document.getElementById("patient-select"),
        profileAge: document.getElementById("profile-age"),
        profileBmi: document.getElementById("profile-bmi"),
        profileType: document.getElementById("profile-type"),
        profileHba1c: document.getElementById("profile-hba1c"),
        profileDuration: document.getElementById("profile-duration"),
        profileSource: document.getElementById("profile-source"),
        chartReadingsLimit: document.getElementById("chart-readings-limit"),
        btnRefreshTelemetry: document.getElementById("btn-refresh-telemetry"),
        svgChart: document.getElementById("cgm-svg-chart"),
        chartTooltip: document.getElementById("chart-tooltip"),
        chartLoadingOverlay: document.getElementById("chart-loading-overlay"),
        avgHeartRate: document.getElementById("avg-heart-rate"),
        sumSteps: document.getElementById("sum-steps"),
        mealStatusFlag: document.getElementById("meal-status-flag"),
        btnRunPrediction: document.getElementById("btn-run-prediction"),
        predictionEmptyState: document.getElementById("prediction-empty-state"),
        predictionActiveState: document.getElementById("prediction-active-state"),
        predRiskBadge: document.getElementById("pred-risk-badge"),
        predTargetTimestamp: document.getElementById("pred-target-timestamp"),
        probValInrange: document.getElementById("prob-val-inrange"),
        probFillInrange: document.getElementById("prob-fill-inrange"),
        probValHyper: document.getElementById("prob-val-hyper"),
        probFillHyper: document.getElementById("prob-fill-hyper"),
        predFactorsList: document.getElementById("pred-factors-list"),
        whatifForm: document.getElementById("whatif-form"),
        whatifGlucoseSlider: document.getElementById("whatif-glucose-slider"),
        whatifGlucoseVal: document.getElementById("whatif-glucose-val"),
        whatifStepsSlider: document.getElementById("whatif-steps-slider"),
        whatifStepsVal: document.getElementById("whatif-steps-val"),
        whatifDescInput: document.getElementById("whatif-desc-input"),
        btnRunWhatif: document.getElementById("btn-run-whatif"),
        whatifResultContainer: document.getElementById("whatif-result-container"),
        whatifObsGlucose: document.getElementById("whatif-obs-glucose"),
        whatifObsRisk: document.getElementById("whatif-obs-risk"),
        whatifHypGlucose: document.getElementById("whatif-hyp-glucose"),
        whatifHypRisk: document.getElementById("whatif-hyp-risk"),
        historyCountBadge: document.getElementById("history-count-badge"),
        historyTableBody: document.getElementById("history-table-body"),
        // Safety & Emergency UI elements
        kpiGlucoseCaution: document.getElementById("kpi-glucose-caution"),
        kpiStaleTag: document.getElementById("kpi-stale-tag"),
        predictionUnreliableState: document.getElementById("prediction-unreliable-state"),
        unreliablePrimaryMessage: document.getElementById("unreliable-primary-message"),
        unreliableReasonText: document.getElementById("unreliable-reason-text"),
        predCurrentCautionBox: document.getElementById("pred-current-caution-box"),
        predCautionText: document.getElementById("pred-caution-text"),
        predMeasuredGlucose: document.getElementById("pred-measured-glucose"),
        predMeasuredTime: document.getElementById("pred-measured-time"),
        predStaleBadge: document.getElementById("pred-stale-badge"),
        predForecastRange: document.getElementById("pred-forecast-range"),
        btnReportSevereSymptoms: document.getElementById("btn-report-severe-symptoms"),
        severeSymptomsCallout: document.getElementById("severe-symptoms-callout"),
        btnDismissSevereSymptoms: document.getElementById("btn-dismiss-severe-symptoms"),
        // Suggestions Panel UI elements
        suggestionsPanel: document.getElementById("suggestions-panel"),
        suggestionsEmptyState: document.getElementById("suggestions-empty-state"),
        suggestionsActiveState: document.getElementById("suggestions-active-state"),
        suggestionsBadge: document.getElementById("suggestions-badge"),
        suggestionsWhyBox: document.getElementById("suggestions-why-box"),
        suggestionsWhyText: document.getElementById("suggestions-why-text"),
        suggestionsList: document.getElementById("suggestions-list"),
        suggestionsEscalationBox: document.getElementById("suggestions-escalation-box"),
        suggestionsEscalationText: document.getElementById("suggestions-escalation-text")
    };

    // -------------------------------------------------------------
    // API Helper
    // -------------------------------------------------------------
    async function apiRequest(endpoint, options = {}) {
        const method = (options.method || "GET").toUpperCase();
        const extraHeaders = {};

        // Attach CSRF token for state-changing methods when we have one
        if (["POST", "PUT", "DELETE", "PATCH"].includes(method) && state.csrfToken) {
            extraHeaders["X-CSRF-Token"] = state.csrfToken;
        }

        try {
            const response = await fetch(`${API_BASE}${endpoint}`, {
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                    ...extraHeaders
                },
                credentials: "same-origin",
                ...options
            });

            // Redirect to login when session expires or is absent
            if (response.status === 401) {
                window.location.href = "/login";
                return null;
            }

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({}));
                const msg = errorData.detail || `HTTP Error ${response.status}: ${response.statusText}`;
                throw new Error(msg);
            }
            return await response.json();
        } catch (error) {
            console.error(`API Call failed on ${endpoint}:`, error);
            throw error;
        }
    }

    // -------------------------------------------------------------
    // User Profile & Authentication
    // -------------------------------------------------------------
    async function loadUserProfile() {
        try {
            const data = await fetch("/api/auth/me", {
                credentials: "same-origin",
                headers: { "Accept": "application/json" }
            }).then(r => r.json()).catch(() => null);

            if (!data || !data.authenticated) {
                // Not authenticated — redirect to login
                window.location.href = "/login";
                return;
            }

            // Store CSRF token for mutating requests
            state.csrfToken = data.csrf_token || null;

            // Populate user pill in header
            const pill = document.getElementById("user-header-pill");
            const nameEl = document.getElementById("user-display-name");
            const avatarEl = document.getElementById("user-avatar-initials");
            const logoutBtn = document.getElementById("btn-logout");

            if (pill && data.user) {
                const fullName = data.user.full_name || data.user.email || "User";
                const initials = fullName
                    .split(" ")
                    .map(w => w[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase();

                if (nameEl) nameEl.textContent = fullName.split(" ")[0]; // first name only
                if (avatarEl) avatarEl.textContent = initials;
                pill.style.display = "flex";
            }

            // Logout button handler
            if (logoutBtn) {
                logoutBtn.style.display = "flex";
                logoutBtn.addEventListener("click", async function () {
                    try {
                        await fetch("/api/auth/logout", {
                            method: "POST",
                            credentials: "same-origin",
                            headers: {
                                "Content-Type": "application/json",
                                ...(state.csrfToken ? { "X-CSRF-Token": state.csrfToken } : {})
                            }
                        });
                    } catch (_) { /* ignore errors, proceed to redirect */ }
                    window.location.href = "/login";
                });
            }
        } catch (err) {
            console.warn("Could not load user profile:", err);
        }
    }

    // -------------------------------------------------------------
    // Initialization
    // -------------------------------------------------------------
    async function initApp() {
        bindEvents();
        await loadUserProfile();  // Must run first to get CSRF token and verify session
        await checkSystemHealth();
        await loadPatientsList();
    }

    function bindEvents() {
        // Patient selection change
        elements.patientSelect.addEventListener("change", (e) => {
            selectPatient(e.target.value);
        });

        // Telemetry chart limit change
        elements.chartReadingsLimit.addEventListener("change", (e) => {
            state.readingsLimit = parseInt(e.target.value, 10);
            if (state.activePatientId) {
                loadPatientReadings(state.activePatientId);
            }
        });

        // Telemetry refresh button
        elements.btnRefreshTelemetry.addEventListener("click", () => {
            if (state.activePatientId) {
                loadPatientReadings(state.activePatientId);
                loadPredictionHistory(state.activePatientId);
            }
        });

        // Run Prediction button
        elements.btnRunPrediction.addEventListener("click", () => {
            if (state.activePatientId && !state.isPredicting) {
                runPrediction(state.activePatientId);
            }
        });

        // What-If Sliders
        elements.whatifGlucoseSlider.addEventListener("input", (e) => {
            const val = parseFloat(e.target.value);
            elements.whatifGlucoseVal.textContent = `${val >= 0 ? "+" : ""}${val} mg/dL`;
        });

        elements.whatifStepsSlider.addEventListener("input", (e) => {
            const val = parseInt(e.target.value, 10);
            elements.whatifStepsVal.textContent = `+${val} steps`;
        });

        // Preset Scenario Buttons
        document.querySelectorAll(".btn-preset").forEach((btn) => {
            btn.addEventListener("click", () => {
                const glucose = btn.getAttribute("data-glucose");
                const steps = btn.getAttribute("data-steps");
                const name = btn.getAttribute("data-name");

                elements.whatifGlucoseSlider.value = glucose;
                elements.whatifGlucoseVal.textContent = `${glucose >= 0 ? "+" : ""}${glucose} mg/dL`;

                elements.whatifStepsSlider.value = steps;
                elements.whatifStepsVal.textContent = `+${steps} steps`;

                elements.whatifDescInput.value = name;
            });
        });

        // What-If Form Submission
        elements.whatifForm.addEventListener("submit", (e) => {
            e.preventDefault();
            if (state.activePatientId && !state.isSimulating) {
                runWhatIfSimulation(state.activePatientId);
            }
        });

        // Severe Symptoms & Emergency Action Listeners (Requirement 4)
        if (elements.btnReportSevereSymptoms && elements.severeSymptomsCallout) {
            elements.btnReportSevereSymptoms.addEventListener("click", () => {
                elements.severeSymptomsCallout.classList.remove("hidden");
            });
        }
        if (elements.btnDismissSevereSymptoms && elements.severeSymptomsCallout) {
            elements.btnDismissSevereSymptoms.addEventListener("click", () => {
                elements.severeSymptomsCallout.classList.add("hidden");
            });
        }
    }

    function applyModelVersionUI(version, customLimitation) {
        if (version === "v2") {
            const bannerTitle = document.getElementById("banner-warning-title");
            const bannerText = document.getElementById("banner-warning-text");
            const probPill = document.getElementById("prob-hypo-pill");
            const probStatement = document.getElementById("prob-hypo-statement");
            const probDetail = document.getElementById("prob-hypo-detail");
            const calloutTitle = document.getElementById("callout-warning-title");
            const calloutStatement = document.getElementById("callout-warning-statement");
            const calloutDetail = document.getElementById("callout-warning-detail");

            if (bannerTitle) bannerTitle.textContent = "MODEL v2 — SYNTHETIC HYPOGLYCEMIA SUPPORT (NOT CLINICALLY VALIDATED)";
            if (bannerText) bannerText.textContent = customLimitation || "Hypoglycemia prediction is supported only on SYNTHETIC examples generated by the TwinSense simulator. It is NOT clinically validated. A low probability does not rule out hypoglycemia. Real hypoglycemia risk depends on clinical factors not captured in synthetic data.";
            if (probPill) {
                probPill.textContent = "SYNTHETIC v2";
                probPill.className = "unsupported-tag-pill badge-synthetic-v2";
            }
            if (probStatement) probStatement.textContent = "Hypoglycemia prediction supported on synthetic examples only.";
            if (probDetail) probDetail.textContent = "Trained on synthetic simulator episodes; not clinically validated. A low model probability does NOT rule out hypoglycemia.";
            if (calloutTitle) calloutTitle.textContent = "MODEL v2 LIMITATION: SYNTHETIC-ONLY HYPOGLYCEMIA SUPPORT";
            if (calloutStatement) calloutStatement.textContent = "Hypoglycemia prediction is supported only on SYNTHETIC examples. It is NOT clinically validated.";
            if (calloutDetail) calloutDetail.innerHTML = "The underlying v2 machine learning model was trained on synthetic episodes with simulated hypoglycemia. It is <strong>NOT clinically validated</strong> by regulatory authorities (FDA/CE). A low probability does not rule out hypoglycemia. <strong>Always follow clinician guidance.</strong>";
        }
    }

    // -------------------------------------------------------------
    // Measured Reading Low-Glucose Safety Alert (Rule-based, <70 mg/dL)
    // -------------------------------------------------------------
    function updateLowGlucoseAlert(reading) {
        const banner = document.getElementById("low-glucose-alert-banner");
        const text = document.getElementById("low-glucose-alert-text");
        if (!banner || !text) return;

        if (!reading || reading.glucose_mg_dl === null || reading.glucose_mg_dl === undefined) {
            banner.classList.add("hidden");
            return;
        }

        const g = parseFloat(reading.glucose_mg_dl);
        if (isNaN(g) || g >= 70.0) {
            banner.classList.add("hidden");
            return;
        }

        const t = reading.timestamp || "recent timestamp";
        text.textContent = `Low glucose reading: the measured value of ${g.toFixed(1)} mg/dL (at ${t}) is below 70 mg/dL. This alert is based on the measured reading, not the ML prediction. This is synthetic data. If this were a real reading, follow your clinician's guidance and seek medical help if you have symptoms.`;
        banner.classList.remove("hidden");
    }

    // -------------------------------------------------------------
    // Health & System Status
    // -------------------------------------------------------------
    async function checkSystemHealth() {
        try {
            const health = await apiRequest("/api/health");
            if (health.status === "HEALTHY") {
                elements.healthStatusText.textContent = "Backend: Connected";
                elements.systemHealthPill.className = "status-pill status-healthy";
            }
            if (health.model_loaded) {
                elements.modelStatusText.textContent = health.active_model_version === "v2" ? "Random Forest (v2) Active" : "Random Forest Active";
            }
            elements.statTotalPatients.textContent = health.total_patients;
            if (health.active_model_version) {
                state.activeModelVersion = health.active_model_version;
                applyModelVersionUI(health.active_model_version, health.hypoglycemia_limitation);
            }
        } catch (error) {
            elements.healthStatusText.textContent = "Backend: Offline";
            elements.systemHealthPill.className = "status-pill status-hypo";
        }
    }

    // -------------------------------------------------------------
    // Patient Management
    // -------------------------------------------------------------
    async function loadPatientsList() {
        try {
            const patients = await apiRequest("/api/patients");
            state.patients = patients;

            elements.patientSelect.innerHTML = "";
            patients.forEach((p) => {
                const opt = document.createElement("option");
                opt.value = p.patient_id;
                opt.textContent = `${p.patient_id} (${p.diabetes_type}, HbA1c ${p.baseline_hba1c}%)`;
                elements.patientSelect.appendChild(opt);
            });

            if (patients.length > 0) {
                selectPatient(patients[0].patient_id);
            }
        } catch (error) {
            elements.patientSelect.innerHTML = '<option value="">Error loading patients</option>';
        }
    }

    // -------------------------------------------------------------
    // General Wellness Suggestions Helpers
    // -------------------------------------------------------------
    function resetSuggestions() {
        if (!elements.suggestionsPanel) return;
        if (elements.suggestionsEmptyState) elements.suggestionsEmptyState.classList.remove("hidden");
        if (elements.suggestionsActiveState) elements.suggestionsActiveState.classList.add("hidden");
        elements.suggestionsPanel.classList.remove("elevated-risk-amber", "elevated-risk-pink");
        if (elements.suggestionsBadge) elements.suggestionsBadge.textContent = "Non-Clinical Guidance";
        if (elements.suggestionsList) elements.suggestionsList.innerHTML = "";
        if (elements.suggestionsWhyText) elements.suggestionsWhyText.textContent = "--";
        if (elements.suggestionsWhyBox) elements.suggestionsWhyBox.classList.add("hidden");
        if (elements.suggestionsEscalationBox) elements.suggestionsEscalationBox.classList.add("hidden");
    }

    function renderSuggestions(sugg, riskClass, currentGlucose) {
        if (!elements.suggestionsPanel) return;
        if (!sugg || !sugg.suggestions || sugg.suggestions.length === 0) {
            resetSuggestions();
            return;
        }

        if (elements.suggestionsEmptyState) elements.suggestionsEmptyState.classList.add("hidden");
        if (elements.suggestionsActiveState) elements.suggestionsActiveState.classList.remove("hidden");

        // Styling for elevated-risk classes (amber/pink accent)
        elements.suggestionsPanel.classList.remove("elevated-risk-amber", "elevated-risk-pink");
        const isElevated = sugg.is_elevated_risk || riskClass === 3 || riskClass === 1;
        if (isElevated) {
            if (riskClass === 1) {
                elements.suggestionsPanel.classList.add("elevated-risk-pink");
                if (elements.suggestionsBadge) elements.suggestionsBadge.textContent = "Low-Glucose Alert (Unsupported)";
            } else {
                elements.suggestionsPanel.classList.add("elevated-risk-amber");
                if (elements.suggestionsBadge) elements.suggestionsBadge.textContent = "Elevated Risk Guidance";
            }
        } else {
            if (elements.suggestionsBadge) elements.suggestionsBadge.textContent = "In-Range Guidance";
        }

        // "Why am I seeing this?" line referencing actual predicted class and observed glucose
        if (elements.suggestionsWhyBox && elements.suggestionsWhyText) {
            if (sugg.why_am_i_seeing_this) {
                elements.suggestionsWhyText.textContent = sugg.why_am_i_seeing_this;
                elements.suggestionsWhyBox.classList.remove("hidden");
            } else if (riskClass && currentGlucose !== undefined) {
                elements.suggestionsWhyText.textContent = `Why am I seeing this? The forecast estimated Class ${riskClass} based on a current observed glucose of ${parseFloat(currentGlucose).toFixed(1)} mg/dL.`;
                elements.suggestionsWhyBox.classList.remove("hidden");
            } else {
                elements.suggestionsWhyBox.classList.add("hidden");
            }
        }

        // Suggestions List
        if (elements.suggestionsList) {
            elements.suggestionsList.innerHTML = "";
            sugg.suggestions.forEach((text) => {
                const li = document.createElement("li");
                li.className = "suggestion-item";
                li.innerHTML = `<span class="suggestion-bullet">✦</span><span class="suggestion-text">${text}</span>`;
                elements.suggestionsList.appendChild(li);
            });
        }

        // Escalation Box for elevated risk
        if (elements.suggestionsEscalationBox) {
            if (sugg.escalation_line || isElevated) {
                elements.suggestionsEscalationBox.classList.remove("hidden");
                if (elements.suggestionsEscalationText && sugg.escalation_line) {
                    elements.suggestionsEscalationText.textContent = sugg.escalation_line;
                }
            } else {
                elements.suggestionsEscalationBox.classList.add("hidden");
            }
        }

        // Active model hypoglycemia note in suggestions
        if (sugg.hypoglycemia_note) {
            const noteEl = document.getElementById("suggestions-hypo-note-text");
            if (noteEl) {
                noteEl.innerHTML = `<strong>Hypoglycemia Notice:</strong> ${sugg.hypoglycemia_note}`;
            }
        }
    }

    async function selectPatient(patientId) {
        state.activePatientId = patientId;
        elements.patientSelect.value = patientId;
        elements.statActivePatient.textContent = patientId;

        // Reset previous prediction view and clear previous patient's low-glucose alert
        updateLowGlucoseAlert(null);
        elements.predictionEmptyState.classList.remove("hidden");
        elements.predictionActiveState.classList.add("hidden");
        if (elements.predictionUnreliableState) elements.predictionUnreliableState.classList.add("hidden");
        if (elements.predCurrentCautionBox) elements.predCurrentCautionBox.classList.add("hidden");
        resetSuggestions();
        elements.statCurrentRisk.innerHTML = '<span class="risk-badge risk-pending">Awaiting Run</span>';
        elements.whatifResultContainer.classList.add("hidden");

        // Fetch patient profile, readings, and prediction history in parallel
        await Promise.all([
            loadPatientProfile(patientId),
            loadPatientReadings(patientId),
            loadPredictionHistory(patientId)
        ]);
    }

    async function loadPatientProfile(patientId) {
        try {
            const profile = await apiRequest(`/api/patients/${patientId}`);
            state.activeProfile = profile;

            elements.profileAge.textContent = `${profile.age} yrs`;
            elements.profileBmi.textContent = profile.bmi;
            elements.profileType.textContent = profile.diabetes_type;
            elements.profileHba1c.textContent = `${profile.baseline_hba1c}%`;
            elements.profileDuration.textContent = `${profile.diabetes_duration_years} yrs`;
            elements.statPatientType.textContent = `${profile.diabetes_type} • Duration ${profile.diabetes_duration_years}y`;
        } catch (error) {
            console.error("Failed to load patient profile:", error);
        }
    }

    // -------------------------------------------------------------
    // Telemetry & Native SVG Chart Engine
    // -------------------------------------------------------------
    async function loadPatientReadings(patientId) {
        state.isLoadingReadings = true;
        elements.chartLoadingOverlay.classList.remove("hidden");

        try {
            const data = await apiRequest(`/api/patients/${patientId}/readings?limit=${state.readingsLimit}`);
            state.recentReadings = data.readings || [];

            if (state.recentReadings.length > 0) {
                const latest = state.recentReadings[state.recentReadings.length - 1];
                const currentG = parseFloat(latest.glucose_mg_dl);
                elements.statCurrentGlucose.innerHTML = `${currentG.toFixed(1)} <span class="unit">mg/dL</span>`;
                elements.statLatestTimestamp.textContent = `Latest: ${formatDateTime(latest.timestamp)}`;

                // Rule-based low-glucose safety alert (< 70 mg/dL strictly on measured reading)
                updateLowGlucoseAlert(latest);

                // Caution message for current glucose outside target range (Requirement 4)
                if (elements.kpiGlucoseCaution) {
                    if (currentG < 70) {
                        elements.kpiGlucoseCaution.textContent = `⚠️ Low: ${currentG.toFixed(1)} mg/dL (<70)`;
                        elements.kpiGlucoseCaution.classList.remove("hidden");
                    } else if (currentG > 180) {
                        elements.kpiGlucoseCaution.textContent = `⚠️ High: ${currentG.toFixed(1)} mg/dL (>180)`;
                        elements.kpiGlucoseCaution.classList.remove("hidden");
                    } else {
                        elements.kpiGlucoseCaution.classList.add("hidden");
                    }
                }

                // Check for staleness / gap in telemetry stream (>15 min gap between points)
                let isStale = false;
                if (state.recentReadings.length >= 2) {
                    for (let i = 1; i < state.recentReadings.length; i++) {
                        const tPrev = new Date(state.recentReadings[i - 1].timestamp.replace(" ", "T")).getTime();
                        const tCurr = new Date(state.recentReadings[i].timestamp.replace(" ", "T")).getTime();
                        if (tCurr - tPrev > 15 * 60 * 1000) {
                            isStale = true;
                            break;
                        }
                    }
                }
                state.isLatestReadingStale = isStale;
                if (elements.kpiStaleTag) {
                    if (isStale) elements.kpiStaleTag.classList.remove("hidden");
                    else elements.kpiStaleTag.classList.add("hidden");
                }

                // Calculate summary metrics
                const avgHr = Math.round(
                    state.recentReadings.reduce((sum, r) => sum + r.heart_rate, 0) / state.recentReadings.length
                );
                const sumSteps = state.recentReadings.slice(-6).reduce((sum, r) => sum + r.steps, 0);
                const hasMeal = state.recentReadings.slice(-6).some((r) => r.meal_event === 1);

                elements.avgHeartRate.textContent = `${avgHr} bpm`;
                elements.sumSteps.textContent = `${sumSteps} steps (last 30m)`;
                elements.mealStatusFlag.textContent = hasMeal ? "Active (Past 30m)" : "None Recorded";
            }

            renderSvgChart(state.recentReadings);
        } catch (error) {
            console.error("Failed to load readings:", error);
            elements.svgChart.innerHTML = `
                <text x="350" y="140" fill="#94a3b8" text-anchor="middle" font-size="14">
                    Error loading telemetry readings.
                </text>`;
        } finally {
            state.isLoadingReadings = false;
            elements.chartLoadingOverlay.classList.add("hidden");
        }
    }

    /**
     * Renders a pure responsive SVG line chart with target zone and threshold reference lines.
     */
    function renderSvgChart(readings) {
        const svg = elements.svgChart;
        svg.innerHTML = "";

        if (!readings || readings.length === 0) {
            svg.innerHTML = `
                <text x="350" y="140" fill="#94a3b8" text-anchor="middle" font-size="14">
                    No simulated historical records found.
                </text>`;
            return;
        }

        const width = 700;
        const height = 280;
        const padLeft = 55;
        const padRight = 20;
        const padTop = 25;
        const padBottom = 35;

        const plotWidth = width - padLeft - padRight;
        const plotHeight = height - padTop - padBottom;

        // Determine Y bounds: min bound <= 50, max bound >= 240
        const glucoseValues = readings.map((r) => r.glucose_mg_dl);
        const minVal = Math.min(50, Math.min(...glucoseValues) - 10);
        const maxVal = Math.max(240, Math.max(...glucoseValues) + 15);

        function scaleX(index) {
            if (readings.length === 1) return padLeft + plotWidth / 2;
            return padLeft + (index / (readings.length - 1)) * plotWidth;
        }

        function scaleY(val) {
            return padTop + plotHeight - ((val - minVal) / (maxVal - minVal)) * plotHeight;
        }

        // SVG Defs (Gradients & Filters)
        const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
        defs.innerHTML = `
            <linearGradient id="areaGradient" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="#A855F7" stop-opacity="0.30"/>
                <stop offset="100%" stop-color="#A855F7" stop-opacity="0.0"/>
            </linearGradient>
            <filter id="glowFilter" x="-20%" y="-20%" width="140%" height="140%">
                <feDropShadow dx="0" dy="0" stdDeviation="3" flood-color="#A855F7" flood-opacity="0.75"/>
            </filter>
        `;
        svg.appendChild(defs);

        // 1. Target Range Band (70 to 180 mg/dL)
        const y180 = scaleY(180);
        const y70 = scaleY(70);
        const bandHeight = y70 - y180;

        const targetBand = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        targetBand.setAttribute("x", padLeft);
        targetBand.setAttribute("y", y180);
        targetBand.setAttribute("width", plotWidth);
        targetBand.setAttribute("height", Math.max(0, bandHeight));
        targetBand.setAttribute("fill", "rgba(16, 214, 160, 0.16)");
        svg.appendChild(targetBand);

        // 2. Horizontal Reference Grid Lines (70, 120, 180, 240)
        const gridLevels = [70, 120, 180, 240];
        gridLevels.forEach((level) => {
            if (level >= minVal && level <= maxVal) {
                const y = scaleY(level);

                // Grid line
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", padLeft);
                line.setAttribute("y1", y);
                line.setAttribute("x2", width - padRight);
                line.setAttribute("y2", y);

                if (level === 180) {
                    line.setAttribute("stroke", "#FFC247");
                    line.setAttribute("stroke-dasharray", "4,3");
                    line.setAttribute("stroke-width", "1.2");
                } else if (level === 70) {
                    line.setAttribute("stroke", "#FF4385");
                    line.setAttribute("stroke-dasharray", "4,3");
                    line.setAttribute("stroke-width", "1.2");
                } else {
                    line.setAttribute("stroke", "rgba(175, 166, 216, 0.12)");
                    line.setAttribute("stroke-width", "1");
                }
                svg.appendChild(line);

                // Y-Axis Label
                const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
                label.setAttribute("x", padLeft - 8);
                label.setAttribute("y", y + 4);
                label.setAttribute("fill", level === 180 ? "#FFC247" : level === 70 ? "#FF4385" : "#AFA6D8");
                label.setAttribute("font-size", "10");
                label.setAttribute("font-weight", level === 180 || level === 70 ? "700" : "500");
                label.setAttribute("text-anchor", "end");
                label.textContent = `${level}`;
                svg.appendChild(label);
            }
        });

        // 3. Build Points & Area Path
        const points = readings.map((r, i) => ({
            x: scaleX(i),
            y: scaleY(r.glucose_mg_dl),
            reading: r
        }));

        let linePathD = "";
        points.forEach((pt, i) => {
            linePathD += (i === 0 ? "M " : " L ") + `${pt.x.toFixed(1)},${pt.y.toFixed(1)}`;
        });

        const areaPathD = linePathD +
            ` L ${points[points.length - 1].x.toFixed(1)},${(padTop + plotHeight).toFixed(1)}` +
            ` L ${points[0].x.toFixed(1)},${(padTop + plotHeight).toFixed(1)} Z`;

        // Draw Area Fill
        const areaPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
        areaPath.setAttribute("d", areaPathD);
        areaPath.setAttribute("fill", "url(#areaGradient)");
        svg.appendChild(areaPath);

        // Draw Line Stroke with Glowing Violet Filter
        const linePath = document.createElementNS("http://www.w3.org/2000/svg", "path");
        linePath.setAttribute("d", linePathD);
        linePath.setAttribute("fill", "none");
        linePath.setAttribute("stroke", "#C084FC");
        linePath.setAttribute("stroke-width", "2.8");
        linePath.setAttribute("stroke-linejoin", "round");
        linePath.setAttribute("stroke-linecap", "round");
        linePath.setAttribute("filter", "url(#glowFilter)");
        svg.appendChild(linePath);

        // 4. Data Point Circles & Tooltip Interactivity
        points.forEach((pt) => {
            const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
            circle.setAttribute("cx", pt.x);
            circle.setAttribute("cy", pt.y);
            circle.setAttribute("r", "3.5");
            circle.setAttribute("fill", pt.reading.glucose_mg_dl > 180 ? "#FFC247" : pt.reading.glucose_mg_dl < 70 ? "#FF4385" : "#A855F7");
            circle.setAttribute("stroke", "#100828");
            circle.setAttribute("stroke-width", "1.5");
            circle.style.cursor = "pointer";

            circle.addEventListener("mouseenter", (e) => {
                circle.setAttribute("r", "6");
                circle.setAttribute("stroke", "#ffffff");

                elements.chartTooltip.innerHTML = `
                    <strong>${pt.reading.glucose_mg_dl} mg/dL</strong><br>
                    <span>Historical: ${formatDateTime(pt.reading.timestamp)}</span><br>
                    <span>HR: ${pt.reading.heart_rate} bpm | Steps: ${pt.reading.steps}</span>
                `;
                elements.chartTooltip.classList.remove("hidden");

                const rect = elements.svgChart.getBoundingClientRect();
                const tooltipX = (pt.x / width) * rect.width;
                const tooltipY = (pt.y / height) * rect.height;

                elements.chartTooltip.style.left = `${tooltipX}px`;
                elements.chartTooltip.style.top = `${tooltipY}px`;
            });

            circle.addEventListener("mouseleave", () => {
                circle.setAttribute("r", "3.5");
                circle.setAttribute("stroke", "#090e1a");
                elements.chartTooltip.classList.add("hidden");
            });

            svg.appendChild(circle);
        });

        // 5. X-Axis Timestamps (4 to 5 evenly spaced labels)
        const step = Math.max(1, Math.floor(readings.length / 4));
        for (let i = 0; i < readings.length; i += step) {
            const pt = points[i];
            const timeLabel = formatTimeOnly(readings[i].timestamp);

            const xText = document.createElementNS("http://www.w3.org/2000/svg", "text");
            xText.setAttribute("x", pt.x);
            xText.setAttribute("y", height - 12);
            xText.setAttribute("fill", "#AFA6D8");
            xText.setAttribute("font-size", "10");
            xText.setAttribute("text-anchor", "middle");
            xText.textContent = timeLabel;
            svg.appendChild(xText);
        }
    }

    // -------------------------------------------------------------
    // Digital Twin Inference Flow
    // -------------------------------------------------------------
    function showUnreliablePrediction(reason) {
        elements.predictionEmptyState.classList.add("hidden");
        elements.predictionActiveState.classList.add("hidden");
        if (elements.predictionUnreliableState) {
            elements.predictionUnreliableState.classList.remove("hidden");
            if (elements.unreliablePrimaryMessage) {
                elements.unreliablePrimaryMessage.textContent =
                    "Unable to provide a reliable prediction. Check the latest glucose reading and seek appropriate medical guidance.";
            }
            if (elements.unreliableReasonText) {
                elements.unreliableReasonText.textContent = reason ||
                    "Input telemetry is missing, invalid, outdated, or outside the model's supported physiological range.";
            }
        }
        elements.statCurrentRisk.innerHTML = '<span class="risk-badge risk-pending">Unavailable</span>';
        state.activePrediction = null;
        resetSuggestions();
    }

    async function runPrediction(patientId) {
        state.isPredicting = true;
        elements.btnRunPrediction.disabled = true;
        elements.btnRunPrediction.innerHTML = '<div class="spinner" style="width:14px;height:14px;border-width:2px;"></div> Predicting...';

        // Pre-inference safety check: insufficient or missing data (Requirement 3)
        if (!state.recentReadings || state.recentReadings.length < 6) {
            showUnreliablePrediction("Telemetry history contains fewer than 6 consecutive readings (30 minutes required).");
            state.isPredicting = false;
            elements.btnRunPrediction.disabled = false;
            elements.btnRunPrediction.innerHTML = '<span class="btn-icon">⚡</span> Run Twin Forecast';
            return;
        }

        // Physiological range check: outside 30-500 mg/dL (Requirement 3)
        const hasInvalidValues = state.recentReadings.some(
            (r) => r.glucose_mg_dl === null || isNaN(r.glucose_mg_dl) || r.glucose_mg_dl < 30.0 || r.glucose_mg_dl > 500.0
        );
        if (hasInvalidValues) {
            showUnreliablePrediction("Input data contains missing, NaN, or physiological readings outside supported range (30–500 mg/dL).");
            state.isPredicting = false;
            elements.btnRunPrediction.disabled = false;
            elements.btnRunPrediction.innerHTML = '<span class="btn-icon">⚡</span> Run Twin Forecast';
            return;
        }

        try {
            const result = await apiRequest(`/api/patients/${patientId}/predict`, {
                method: "POST",
                body: JSON.stringify({})
            });

            // If API indicates unreliable data
            if (result.is_reliable === false) {
                showUnreliablePrediction(result.unreliable_reason || "Prediction model could not verify telemetry reliability.");
                return;
            }

            state.activePrediction = result;
            renderPredictionResults(result);
            await loadPredictionHistory(patientId);
        } catch (error) {
            showUnreliablePrediction(error.message);
        } finally {
            state.isPredicting = false;
            elements.btnRunPrediction.disabled = false;
            elements.btnRunPrediction.innerHTML = '<span class="btn-icon">⚡</span> Run Twin Forecast';
        }
    }

    function renderPredictionResults(pred) {
        if (elements.predictionUnreliableState) elements.predictionUnreliableState.classList.add("hidden");
        elements.predictionEmptyState.classList.add("hidden");
        elements.predictionActiveState.classList.remove("hidden");

        const riskClass = pred.predicted_risk_class;
        const riskLabel = pred.risk_label;
        const currentG = parseFloat(pred.current_glucose_mg_dl);

        // Distinguish Actual Measured Reading from AI Forecast (Requirement 2 & 6)
        if (elements.predMeasuredGlucose) {
            elements.predMeasuredGlucose.textContent = `${currentG.toFixed(1)} mg/dL`;
        }
        if (elements.predMeasuredTime) {
            elements.predMeasuredTime.textContent = `Latest: ${formatDateTime(pred.current_timestamp)}`;
        }
        if (elements.predStaleBadge) {
            if (pred.is_stale || state.isLatestReadingStale) elements.predStaleBadge.classList.remove("hidden");
            else elements.predStaleBadge.classList.add("hidden");
        }
        if (elements.predForecastRange) {
            if (riskClass === 2) {
                elements.predForecastRange.textContent = "Predicted glucose range: 70–180 mg/dL";
            } else if (riskClass === 3) {
                elements.predForecastRange.textContent = "Potential Hyperglycemia Risk (>180 mg/dL)";
            } else {
                elements.predForecastRange.textContent = "Hypoglycemia Unsupported";
            }
        }

        // Configure Risk Badge
        let badgeClass = "risk-inrange";
        if (riskClass === 3) badgeClass = "risk-hyper";
        else if (riskClass === 1) badgeClass = "risk-hypo";

        elements.predRiskBadge.className = `risk-badge-large ${badgeClass}`;
        elements.predRiskBadge.textContent = riskLabel;

        // Overview KPI Badge
        elements.statCurrentRisk.innerHTML = `<span class="risk-badge ${badgeClass}">${riskLabel}</span>`;

        // Target Timestamp
        elements.predTargetTimestamp.textContent = `${formatDateTime(pred.predicted_target_timestamp)} (+45m)`;

        // Caution banner when current glucose is outside target range (Requirement 4)
        if (elements.predCurrentCautionBox) {
            if (currentG < 70 || currentG > 180) {
                elements.predCurrentCautionBox.classList.remove("hidden");
                if (elements.predCautionText) {
                    elements.predCautionText.textContent = (currentG < 70)
                        ? `Caution: Current measured glucose (${currentG.toFixed(1)} mg/dL) is below the configured target range (<70 mg/dL). A reassuring AI forecast does NOT override your current reading or acute symptoms. Prioritize actual measurements.`
                        : `Caution: Current measured glucose (${currentG.toFixed(1)} mg/dL) is above the configured target range (>180 mg/dL). A reassuring AI forecast does NOT override your current reading or acute symptoms. Prioritize actual measurements.`;
                }
            } else {
                elements.predCurrentCautionBox.classList.add("hidden");
            }
        }

        // Probabilities
        const inRangePct = Math.round((pred.class_probabilities["2_in_range"] || 0) * 100);
        const hyperPct = Math.round((pred.class_probabilities["3_hyperglycemia"] || 0) * 100);

        elements.probValInrange.textContent = `${inRangePct}%`;
        elements.probFillInrange.style.width = `${inRangePct}%`;

        elements.probValHyper.textContent = `${hyperPct}%`;
        elements.probFillHyper.style.width = `${hyperPct}%`;

        // Contributing Factors
        elements.predFactorsList.innerHTML = "";
        pred.key_contributing_factors.forEach((factor) => {
            const li = document.createElement("li");
            li.textContent = factor;
            elements.predFactorsList.appendChild(li);
        });

        // General Wellness Suggestions
        if (pred.suggestions) {
            renderSuggestions(pred.suggestions, riskClass, currentG);
        } else {
            apiRequest(`/api/suggestions/${riskClass}?glucose=${currentG}`)
                .then((sugg) => renderSuggestions(sugg, riskClass, currentG))
                .catch(() => resetSuggestions());
        }
    }

    // -------------------------------------------------------------
    // What-If Counterfactual Simulation Flow
    // -------------------------------------------------------------
    async function runWhatIfSimulation(patientId) {
        state.isSimulating = true;
        elements.btnRunWhatif.disabled = true;
        elements.btnRunWhatif.textContent = "Simulating...";

        const deltaGlucose = parseFloat(elements.whatifGlucoseSlider.value);
        const deltaSteps = parseInt(elements.whatifStepsSlider.value, 10);
        const scenarioName = elements.whatifDescInput.value.trim() || "Activity Simulation";

        try {
            const result = await apiRequest(`/api/patients/${patientId}/what-if`, {
                method: "POST",
                body: JSON.stringify({
                    hypothetical_delta_glucose: deltaGlucose,
                    hypothetical_delta_steps: deltaSteps,
                    scenario_description: scenarioName
                })
            });

            renderWhatIfResults(result);
        } catch (error) {
            alert(`What-if simulation failed: ${error.message}`);
        } finally {
            state.isSimulating = false;
            elements.btnRunWhatif.disabled = false;
            elements.btnRunWhatif.textContent = "🧪 Run Simulation";
        }
    }

    function renderWhatIfResults(data) {
        elements.whatifResultContainer.classList.remove("hidden");

        const obs = data.observed_result;
        const hyp = data.hypothetical_result;

        elements.whatifObsGlucose.textContent = `${obs.glucose_mg_dl} mg/dL`;
        elements.whatifObsRisk.textContent = obs.risk_label;
        elements.whatifObsRisk.className = `comparison-risk ${obs.risk_class === 3 ? "text-accent" : ""}`;

        // Clearly label hypothetical glucose as simulated
        elements.whatifHypGlucose.innerHTML = `${hyp.glucose_mg_dl} mg/dL <span class="badge-simulated">(Simulated)</span>`;
        elements.whatifHypRisk.textContent = hyp.risk_label;
        elements.whatifHypRisk.className = `comparison-risk ${hyp.risk_class === 3 ? "text-accent" : ""}`;
    }

    // -------------------------------------------------------------
    // Prediction History Audit Trail
    // -------------------------------------------------------------
    async function loadPredictionHistory(patientId) {
        try {
            const data = await apiRequest(`/api/patients/${patientId}/predictions?limit=10`);
            state.history = data.predictions || [];

            elements.historyCountBadge.textContent = `${state.history.length} logged`;
            elements.historyTableBody.innerHTML = "";

            if (state.history.length === 0) {
                elements.historyTableBody.innerHTML = `
                    <tr>
                        <td colspan="4" class="text-center text-muted">No predictions logged yet.</td>
                    </tr>`;
                return;
            }

            state.history.forEach((h) => {
                const tr = document.createElement("tr");

                let badgeClass = "risk-inrange";
                if (h.predicted_risk_class === 3) badgeClass = "risk-hyper";
                else if (h.predicted_risk_class === 1) badgeClass = "risk-hypo";

                const timeFormatted = formatDateTime(h.prediction_timestamp);

                tr.innerHTML = `
                    <td>${timeFormatted}</td>
                    <td><strong>${h.current_glucose_mg_dl}</strong> mg/dL</td>
                    <td><span class="risk-badge ${badgeClass}">${h.risk_label}</span></td>
                    <td>+${h.prediction_horizon_minutes}m</td>
                `;
                elements.historyTableBody.appendChild(tr);
            });
        } catch (error) {
            console.error("Failed to load history:", error);
        }
    }

    // -------------------------------------------------------------
    // Download Prediction Report
    // -------------------------------------------------------------
    const dlElements = {
        btnCsv: document.getElementById("btn-download-csv"),
        btnPdf: document.getElementById("btn-download-pdf"),
        statusBox: document.getElementById("report-download-status"),
        noPredNote: document.getElementById("download-no-prediction-note")
    };

    function setDownloadStatus(type, message) {
        const el = dlElements.statusBox;
        el.className = "report-download-status " + type;
        el.textContent = message;
        el.classList.remove("hidden");
        if (type === "status-success" || type === "status-error") {
            setTimeout(() => { el.classList.add("hidden"); }, 4000);
        }
    }

    function updateDownloadButtons() {
        const hasPred = !!state.activePrediction;
        dlElements.btnCsv.disabled = !hasPred;
        dlElements.btnPdf.disabled = !hasPred;
        if (dlElements.noPredNote) {
            dlElements.noPredNote.style.display = hasPred ? "none" : "";
        }
    }

    async function triggerDownload(format) {
        if (!state.activePatientId) return;
        const btn = format === "csv" ? dlElements.btnCsv : dlElements.btnPdf;
        const originalHtml = btn.innerHTML;
        btn.classList.add("btn-loading");
        btn.innerHTML = '<span class="btn-download-icon">⏳</span><span class="btn-download-label">Generating...</span>';
        setDownloadStatus("status-loading", `⏳ Generating ${format.toUpperCase()} report...`);

        try {
            const url = `/api/patients/${encodeURIComponent(state.activePatientId)}/report/${format}`;
            const response = await fetch(url, { method: "GET" });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                throw new Error(errData.detail || `HTTP ${response.status}`);
            }

            const blob = await response.blob();
            const disposition = response.headers.get("Content-Disposition") || "";
            let filename = `TwinSense_Report_${state.activePatientId}.${format}`;
            const fnMatch = disposition.match(/filename="([^"]+)"/);
            if (fnMatch && fnMatch[1]) { filename = fnMatch[1]; }

            // Trigger browser download via temporary anchor
            const blobUrl = URL.createObjectURL(blob);
            const anchor = document.createElement("a");
            anchor.href = blobUrl;
            anchor.download = filename;
            document.body.appendChild(anchor);
            anchor.click();
            document.body.removeChild(anchor);
            setTimeout(() => URL.revokeObjectURL(blobUrl), 2000);

            setDownloadStatus("status-success", `✅ ${format.toUpperCase()} report downloaded: ${filename}`);
        } catch (err) {
            setDownloadStatus("status-error", `❌ Download failed: ${err.message}`);
        } finally {
            btn.classList.remove("btn-loading");
            btn.innerHTML = originalHtml;
        }
    }

    if (dlElements.btnCsv) {
        dlElements.btnCsv.addEventListener("click", () => triggerDownload("csv"));
    }
    if (dlElements.btnPdf) {
        dlElements.btnPdf.addEventListener("click", () => triggerDownload("pdf"));
    }

    // Patch runPrediction to also update download buttons
    const _origRunPrediction = runPrediction;
    async function runPredictionPatched(patientId) {
        await _origRunPrediction(patientId);
        updateDownloadButtons();
    }
    // Override the event binding for prediction button
    elements.btnRunPrediction.removeEventListener("click", elements.btnRunPrediction._dl_listener);
    elements.btnRunPrediction.addEventListener("click", () => {
        if (state.activePatientId && !state.isPredicting) {
            runPredictionPatched(state.activePatientId);
        }
    });

    // Also reset buttons on patient switch
    const _origSelectPatient = selectPatient;
    async function selectPatientPatched(patientId) {
        state.activePrediction = null;
        updateDownloadButtons();
        resetSuggestions();
        await _origSelectPatient(patientId);
    }
    elements.patientSelect.removeEventListener("change", elements.patientSelect._dl_listener);
    elements.patientSelect.addEventListener("change", (e) => {
        selectPatientPatched(e.target.value);
    });

    // Initialize disabled state
    updateDownloadButtons();

    // Launch application on DOM ready
    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", initApp);
    } else {
        initApp();
    }
})();
