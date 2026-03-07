// SehatSamjho — Web Interface JavaScript (Wizard Flow)

document.addEventListener("DOMContentLoaded", () => {
    // Elements
    const steps = {
        1: document.getElementById("step-1"),
        2: document.getElementById("step-2"),
        loading: document.getElementById("step-loading"),
        3: document.getElementById("step-3"),
    };
    const progressSteps = document.querySelectorAll(".progress-step");
    const progressLines = document.querySelectorAll(".progress-line");
    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("image-input");
    const uploadZone = document.getElementById("upload-zone");
    const uploadPlaceholder = document.getElementById("upload-placeholder");
    const uploadPreview = document.getElementById("upload-preview");
    const imagePreview = document.getElementById("image-preview");
    const fileNameEl = document.getElementById("file-name");
    const submitBtn = document.getElementById("submit-btn");
    const errorEl = document.getElementById("error-msg");
    const resetBtn = document.getElementById("reset-btn");
    const changeImageBtn = document.getElementById("change-image");
    const langSearch = document.getElementById("lang-search");
    const selectedLangBadge = document.getElementById("selected-lang-badge");
    const selectedLangText = document.getElementById("selected-lang-text");

    let selectedLanguage = "hi";
    let selectedLanguageLabel = "Hindi - \u0939\u093F\u0928\u094D\u0926\u0940";

    // ── Localization ────────────────────────────────────────

    function applyLocale() {
        window._uiLang = selectedLanguage;

        // Progress bar labels (all 3 steps)
        const progLabels = document.querySelectorAll(".progress-label");
        if (progLabels.length >= 3) {
            progLabels[0].textContent = t("progress_choose");
            progLabels[1].textContent = t("progress_upload");
            progLabels[2].textContent = t("progress_results");
        }

        // Step 2
        const s2Title = document.querySelector("#step-2 h2");
        const s2Desc = document.querySelector("#step-2 .step-desc");
        if (s2Title) s2Title.textContent = t("step2_title");
        if (s2Desc) s2Desc.textContent = t("step2_desc");

        const placeholder = document.querySelector("#upload-placeholder p");
        if (placeholder) placeholder.innerHTML = t("upload_hint").replace("\n", "<br>");

        document.getElementById("back-to-1").childNodes.forEach(n => {
            if (n.nodeType === 3 && n.textContent.trim()) n.textContent = "\n            " + t("btn_back") + "\n        ";
        });
        submitBtn.childNodes.forEach(n => {
            if (n.nodeType === 3 && n.textContent.trim()) n.textContent = "\n            " + t("btn_translate") + "\n            ";
        });
        changeImageBtn.textContent = t("btn_change_image");

        // Loading state
        const loadTitle = document.querySelector("#step-loading h2");
        const loadHint = document.querySelector("#step-loading .loading-hint");
        if (loadTitle) loadTitle.textContent = t("loading_title");
        if (loadHint) loadHint.textContent = t("loading_hint");

        document.querySelectorAll("#step-loading .loading-step").forEach(el => {
            const id = el.id;
            const cls = el.className;
            el.innerHTML = '<span class="ls-dot"></span> ' + t(id);
            el.className = cls;
        });

        // Step 3 static labels
        document.querySelector("#rx-section-medicines h3").textContent = t("rx_title");
        document.querySelector("#rx-section-medicines .section-subtitle").textContent = t("rx_subtitle");
        document.querySelector("#lab-section-tests h3").textContent = t("lab_title");
        document.querySelector("#lab-section-tests .section-subtitle").textContent = t("lab_subtitle");
        document.querySelector("#audio-section h4").textContent = t("audio_title");
        document.querySelector("#audio-section .audio-note").textContent = t("audio_note");
        document.querySelector(".full-translation summary").textContent = t("full_translation");
        document.getElementById("section-next-title").textContent = t("next_title");
        document.querySelector(".disclaimer strong").textContent = t("disclaimer_label");
    }

    // ── Wizard Navigation ──────────────────────────────────

    const containerEl = document.querySelector(".container");

    function goToStep(step) {
        Object.values(steps).forEach(el => el.classList.remove("active"));
        const target = steps[step];
        if (target) target.classList.add("active");

        // Widen container for results view
        if (step === 3) {
            containerEl.classList.add("container-wide");
        } else {
            containerEl.classList.remove("container-wide");
        }

        const stepNum = typeof step === "number" ? step : 0;
        progressSteps.forEach((el) => {
            const s = parseInt(el.dataset.step);
            el.classList.remove("active", "done");
            if (s < stepNum) el.classList.add("done");
            else if (s === stepNum) el.classList.add("active");
        });
        progressLines.forEach((line, i) => {
            line.classList.remove("done");
            if (i + 1 < stepNum) line.classList.add("done");
        });

        window.scrollTo({ top: 0, behavior: "smooth" });
    }

    // ── Step 1: Language Selection ──────────────────────────

    const langOptions = document.querySelectorAll(".language-option");

    langOptions.forEach(opt => {
        opt.addEventListener("click", () => {
            langOptions.forEach(o => o.classList.remove("selected"));
            opt.classList.add("selected");
            const radio = opt.querySelector("input[type=radio]");
            radio.checked = true;
            selectedLanguage = radio.value;
            const name = opt.querySelector(".lang-name").textContent;
            const native = opt.querySelector(".lang-native").textContent;
            selectedLanguageLabel = name + " - " + native;
        });
    });

    // Language search/filter
    if (langSearch) {
        langSearch.addEventListener("input", () => {
            const q = langSearch.value.toLowerCase().trim();
            langOptions.forEach(opt => {
                const name = opt.querySelector(".lang-name").textContent.toLowerCase();
                const native = opt.querySelector(".lang-native").textContent.toLowerCase();
                if (!q || name.includes(q) || native.includes(q)) {
                    opt.classList.remove("hidden");
                } else {
                    opt.classList.add("hidden");
                }
            });
        });
    }

    document.getElementById("next-to-2").addEventListener("click", () => {
        // Update badge with selected language
        if (selectedLangText) {
            selectedLangText.textContent = selectedLanguageLabel;
        }
        applyLocale();
        goToStep(2);
    });

    // ── Step 2: Upload ─────────────────────────────────────

    document.getElementById("back-to-1").addEventListener("click", () => {
        goToStep(1);
    });

    uploadZone.addEventListener("dragover", (e) => {
        e.preventDefault();
        uploadZone.classList.add("dragover");
    });

    uploadZone.addEventListener("dragleave", () => {
        uploadZone.classList.remove("dragover");
    });

    uploadZone.addEventListener("drop", (e) => {
        e.preventDefault();
        uploadZone.classList.remove("dragover");
        if (e.dataTransfer.files.length > 0) {
            fileInput.files = e.dataTransfer.files;
            handleFileSelect(e.dataTransfer.files[0]);
        }
    });

    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    changeImageBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        fileInput.value = "";
        uploadPlaceholder.style.display = "";
        uploadPreview.style.display = "none";
        submitBtn.disabled = true;
    });

    function handleFileSelect(file) {
        if (!file.type.startsWith("image/")) {
            showError(t("err_not_image"));
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showError(t("err_too_large"));
            return;
        }

        hideError();
        fileNameEl.textContent = file.name;

        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            uploadPlaceholder.style.display = "none";
            uploadPreview.style.display = "";
            submitBtn.disabled = false;
        };
        reader.readAsDataURL(file);
    }

    // ── Submit ─────────────────────────────────────────────

    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        if (!fileInput.files.length) {
            showError(t("err_no_image"));
            return;
        }

        hideError();
        goToStep("loading");
        startLoadingAnimation();

        const formData = new FormData();
        formData.append("image", fileInput.files[0]);
        formData.append("language_code", selectedLanguage);

        try {
            const response = await fetch("/api/translate", {
                method: "POST",
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || "Something went wrong.");
            }

            renderResults(data);
            goToStep(3);
        } catch (err) {
            goToStep(2);
            showError(err.message || t("err_generic"));
        }
    });

    // ── Loading Animation ──────────────────────────────────

    let loadingTimer = null;

    function startLoadingAnimation() {
        const loadingSteps = ["ls-extract", "ls-lookup", "ls-translate", "ls-audio"];
        let current = 0;

        loadingSteps.forEach(id => {
            const el = document.getElementById(id);
            el.classList.remove("active", "done");
        });
        document.getElementById(loadingSteps[0]).classList.add("active");

        loadingTimer = setInterval(() => {
            if (current < loadingSteps.length - 1) {
                document.getElementById(loadingSteps[current]).classList.remove("active");
                document.getElementById(loadingSteps[current]).classList.add("done");
                current++;
                document.getElementById(loadingSteps[current]).classList.add("active");
            }
        }, 8000);
    }

    // ── Render Results ─────────────────────────────────────

    function renderResults(data) {
        if (loadingTimer) {
            clearInterval(loadingTimer);
            loadingTimer = null;
        }

        const isLabReport = data.doc_type === "lab_report";

        // Result badge
        const badge = document.querySelector(".result-badge");
        badge.textContent = isLabReport ? t("badge_lab") : t("badge_translation");

        // Combined confidence score
        const confEl = document.getElementById("confidence-score");
        if (!isLabReport && data.medicines && data.medicines.length > 0) {
            const scores = data.medicines.filter(m => m.confidence != null).map(m => m.confidence);
            if (scores.length > 0) {
                const avg = scores.reduce((a, b) => a + b, 0) / scores.length;
                const pct = Math.round(avg * 100);
                const cls = avg >= 0.8 ? "high" : avg >= 0.5 ? "medium" : "low";
                const label = avg >= 0.8 ? t("confidence_high") : avg >= 0.5 ? t("confidence_medium") : t("confidence_low");
                confEl.className = "confidence-score confidence-" + cls;
                confEl.textContent = label + " (" + pct + "%)";
                confEl.style.display = "";
            } else {
                confEl.style.display = "none";
            }
        } else {
            confEl.style.display = "none";
        }

        // Meta info
        const metaEl = document.getElementById("rx-meta");
        let metaParts = [];
        if (data.doctor_name) metaParts.push(`<strong>${isLabReport ? t("meta_lab_doctor") : t("meta_doctor")}</strong> ${esc(data.doctor_name)}`);
        if (data.diagnosis) metaParts.push(`<strong>${t("meta_diagnosis")}</strong> ${esc(data.diagnosis)}`);
        if (data.date) metaParts.push(`<strong>${t("meta_date")}</strong> ${esc(data.date)}`);
        metaParts.push(`<strong>${t("meta_language")}</strong> ${esc(data.language_name)}`);
        if (isLabReport) metaParts.push(`<strong>${t("meta_type")}</strong> ${t("meta_lab_report")}`);
        metaEl.innerHTML = metaParts.join("&nbsp;&nbsp;|&nbsp;&nbsp;");

        // Toggle sections based on doc_type
        const rxMedSection = document.getElementById("rx-section-medicines");
        const labTestSection = document.getElementById("lab-section-tests");

        if (isLabReport) {
            rxMedSection.style.display = "none";
            labTestSection.style.display = "";
            renderLabTests(data);
        } else {
            rxMedSection.style.display = "";
            labTestSection.style.display = "none";
            renderMedicines(data);
        }

        // Section 2: title adapts to doc type
        document.getElementById("section-why-title").textContent =
            isLabReport ? t("why_title_lab") : t("why_title_rx");
        document.getElementById("section-why-subtitle").textContent =
            isLabReport ? t("why_subtitle_lab") : t("why_subtitle_rx");
        document.getElementById("section-why").textContent = data.section_why || "";

        // Section 3: next steps
        document.getElementById("section-next-subtitle").textContent =
            isLabReport ? t("next_subtitle_lab") : t("next_subtitle_rx");
        document.getElementById("section-next-steps").textContent = data.section_next_steps || "";

        // Full translation
        document.getElementById("translation-text").textContent = data.translated_text;

        // Audio
        const audioSection = document.getElementById("audio-section");
        if (data.audio_url) {
            document.getElementById("audio-player").src = data.audio_url;
            audioSection.style.display = "";
        } else {
            audioSection.style.display = "none";
        }

        // Disclaimer
        document.getElementById("disclaimer-text").textContent = data.disclaimer;

        // Latency
        document.getElementById("latency-value").textContent =
            t("processed_in").replace("{s}", (data.latency_ms / 1000).toFixed(1));

        // New Document button text
        resetBtn.childNodes.forEach(n => {
            if (n.nodeType === 3 && n.textContent.trim()) n.textContent = "\n                    " + t("btn_new_doc") + "\n                ";
        });
    }

    // ── Render Medicines (Prescription) ────────────────────

    function renderMedicines(data) {
        const medSection = document.getElementById("section-medicines");
        const medCards = document.getElementById("medicines-cards");
        medSection.textContent = data.section_medicines || "";
        medCards.innerHTML = "";

        if (data.medicines && data.medicines.length > 0) {
            data.medicines.forEach((med) => {
                const card = document.createElement("div");
                card.className = "med-card";

                let details = [];
                if (med.dosage) details.push(esc(med.dosage));
                if (med.frequency) details.push(esc(med.frequency));
                if (med.duration) details.push(esc(med.duration));

                let purposeHtml = "";
                if (med.purpose) {
                    purposeHtml = `<div class="med-purpose">${esc(med.purpose)}</div>`;
                }

                let sideEffectsHtml = "";
                if (med.side_effects) {
                    sideEffectsHtml = `<div class="med-side-effects">${t("side_effects")} ${esc(med.side_effects)}</div>`;
                }

                card.innerHTML = `
                    <h4>${esc(med.name)}</h4>
                    ${details.length ? `<div class="med-details">${details.join(" &bull; ")}</div>` : ""}
                    ${purposeHtml}
                    ${sideEffectsHtml}
                `;
                medCards.appendChild(card);
            });
        }
    }

    // ── Render Lab Tests (Lab Report) ──────────────────────

    function renderLabTests(data) {
        const overviewEl = document.getElementById("section-lab-overview");
        const cardsEl = document.getElementById("lab-tests-cards");
        overviewEl.textContent = data.section_medicines || "";
        cardsEl.innerHTML = "";

        if (data.lab_tests && data.lab_tests.length > 0) {
            data.lab_tests.forEach((test) => {
                const card = document.createElement("div");
                card.className = "lab-test-card";

                const flag = (test.flag || "").toLowerCase();
                let flagClass = "flag-unknown";
                let flagLabel = "\u2014";
                if (flag === "normal") { flagClass = "flag-normal"; flagLabel = t("flag_normal"); }
                else if (flag === "high") { flagClass = "flag-high"; flagLabel = t("flag_high"); }
                else if (flag === "low") { flagClass = "flag-low"; flagLabel = t("flag_low"); }

                const valueStr = test.value ? esc(test.value) : "\u2014";
                const unitStr = test.unit ? esc(test.unit) : "";
                const rangeStr = test.reference_range ? `${t("ref_range")} ${esc(test.reference_range)}` : "";

                card.innerHTML = `
                    <div class="lab-test-header">
                        <span class="lab-test-name">${esc(test.test_name)}</span>
                        <span class="lab-flag ${flagClass}">${flagLabel}</span>
                    </div>
                    <div class="lab-test-value">${valueStr} <span class="lab-test-unit">${unitStr}</span></div>
                    ${rangeStr ? `<div class="lab-test-range">${rangeStr}</div>` : ""}
                `;
                cardsEl.appendChild(card);
            });
        }
    }

    // ── Reset ──────────────────────────────────────────────

    resetBtn.addEventListener("click", () => {
        form.reset();
        fileInput.value = "";
        uploadPlaceholder.style.display = "";
        uploadPreview.style.display = "none";
        submitBtn.disabled = true;
        hideError();

        langOptions.forEach(o => o.classList.remove("selected"));
        const hiOption = document.querySelector('.language-option input[value="hi"]');
        if (hiOption) {
            hiOption.checked = true;
            hiOption.closest(".language-option").classList.add("selected");
        }
        selectedLanguage = "hi";
        selectedLanguageLabel = "Hindi - \u0939\u093F\u0928\u094D\u0926\u0940";
        if (langSearch) langSearch.value = "";
        langOptions.forEach(o => o.classList.remove("hidden"));

        // Reset locale to English defaults
        window._uiLang = "en";
        applyLocale();

        goToStep(1);
    });

    // ── Helpers ────────────────────────────────────────────

    function showError(msg) {
        errorEl.textContent = msg;
        errorEl.classList.add("active");
    }

    function hideError() {
        errorEl.classList.remove("active");
    }

    function esc(str) {
        const div = document.createElement("div");
        div.textContent = str;
        return div.innerHTML;
    }
});
