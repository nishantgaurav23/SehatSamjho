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
            showError("Please select an image file (JPEG, PNG).");
            return;
        }
        if (file.size > 10 * 1024 * 1024) {
            showError("Image too large. Maximum size is 10MB.");
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
            showError("Please select an image first.");
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
            showError(err.message || "Failed to process document. Please try again.");
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
        badge.textContent = isLabReport ? "Report Analysis Complete" : "Translation Complete";

        // Meta info
        const metaEl = document.getElementById("rx-meta");
        let metaParts = [];
        if (data.doctor_name) metaParts.push(`<strong>${isLabReport ? "Lab/Doctor:" : "Doctor:"}</strong> ${esc(data.doctor_name)}`);
        if (data.diagnosis) metaParts.push(`<strong>Diagnosis:</strong> ${esc(data.diagnosis)}`);
        if (data.date) metaParts.push(`<strong>Date:</strong> ${esc(data.date)}`);
        metaParts.push(`<strong>Language:</strong> ${esc(data.language_name)}`);
        if (isLabReport) metaParts.push(`<strong>Type:</strong> Lab Report`);
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
            isLabReport ? "What These Results Mean" : "Why These Medicines";
        document.getElementById("section-why-subtitle").textContent =
            isLabReport ? "Simple explanation of each test result" : "What each medicine does and why it was prescribed";
        document.getElementById("section-why").textContent = data.section_why || "";

        // Section 3: next steps
        document.getElementById("section-next-subtitle").textContent =
            isLabReport ? "Follow-up tests, lifestyle advice, and when to see a doctor" : "When to take, what to avoid, and follow-up";
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
            `Processed in ${(data.latency_ms / 1000).toFixed(1)} seconds`;
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

                let badge = "";
                if (med.confidence != null) {
                    const cls = med.confidence >= 0.8 ? "high" : med.confidence >= 0.5 ? "medium" : "low";
                    const label = med.confidence >= 0.8 ? "High" : med.confidence >= 0.5 ? "Medium" : "Low";
                    badge = `<span class="confidence-badge confidence-${cls}">${label} Confidence</span>`;
                }

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
                    sideEffectsHtml = `<div class="med-side-effects">Side effects: ${esc(med.side_effects)}</div>`;
                }

                card.innerHTML = `
                    <h4>${esc(med.name)} ${badge}</h4>
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
                if (flag === "normal") { flagClass = "flag-normal"; flagLabel = "Normal"; }
                else if (flag === "high") { flagClass = "flag-high"; flagLabel = "High"; }
                else if (flag === "low") { flagClass = "flag-low"; flagLabel = "Low"; }

                const valueStr = test.value ? esc(test.value) : "\u2014";
                const unitStr = test.unit ? esc(test.unit) : "";
                const rangeStr = test.reference_range ? `Ref: ${esc(test.reference_range)}` : "";

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
