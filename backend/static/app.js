// SehatSamjho — Web Interface JavaScript

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("upload-form");
    const fileInput = document.getElementById("image-input");
    const uploadZone = document.getElementById("upload-zone");
    const fileName = document.getElementById("file-name");
    const imagePreview = document.getElementById("image-preview");
    const submitBtn = document.getElementById("submit-btn");
    const loadingEl = document.getElementById("loading");
    const resultsEl = document.getElementById("results");
    const errorEl = document.getElementById("error-msg");
    const resetBtn = document.getElementById("reset-btn");

    // Drag and drop
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

    // File select
    fileInput.addEventListener("change", () => {
        if (fileInput.files.length > 0) {
            handleFileSelect(fileInput.files[0]);
        }
    });

    function handleFileSelect(file) {
        // Validate type
        if (!file.type.startsWith("image/")) {
            showError("Please select an image file (JPEG, PNG).");
            return;
        }
        // Validate size (10MB)
        if (file.size > 10 * 1024 * 1024) {
            showError("Image too large. Maximum size is 10MB.");
            return;
        }

        fileName.textContent = file.name;
        fileName.style.display = "block";

        // Preview
        const reader = new FileReader();
        reader.onload = (e) => {
            imagePreview.src = e.target.result;
            imagePreview.style.display = "block";
        };
        reader.readAsDataURL(file);

        hideError();
    }

    // Form submit
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        if (!fileInput.files.length) {
            showError("Please select a prescription image first.");
            return;
        }

        // Show loading, hide results
        hideError();
        resultsEl.classList.remove("active");
        loadingEl.classList.add("active");
        submitBtn.disabled = true;

        const formData = new FormData();
        formData.append("image", fileInput.files[0]);
        formData.append("language_code", document.getElementById("language-select").value);

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
        } catch (err) {
            showError(err.message || "Failed to process prescription. Please try again.");
        } finally {
            loadingEl.classList.remove("active");
            submitBtn.disabled = false;
        }
    });

    // Reset
    resetBtn.addEventListener("click", () => {
        resultsEl.classList.remove("active");
        form.reset();
        fileName.textContent = "";
        fileName.style.display = "none";
        imagePreview.style.display = "none";
        hideError();
        window.scrollTo({ top: uploadZone.offsetTop - 100, behavior: "smooth" });
    });

    function renderResults(data) {
        // Medicines
        const medContainer = document.getElementById("medicines-list");
        medContainer.innerHTML = "";

        if (data.medicines && data.medicines.length > 0) {
            data.medicines.forEach((med, i) => {
                const card = document.createElement("div");
                card.className = "medicine-card";

                let badge = "";
                if (med.confidence !== null && med.confidence !== undefined) {
                    const cls = med.confidence >= 0.8 ? "high" : med.confidence >= 0.5 ? "medium" : "low";
                    const label = med.confidence >= 0.8 ? "Clear" : med.confidence >= 0.5 ? "Partial" : "Unclear";
                    badge = `<span class="confidence-badge confidence-${cls}">${label} (${Math.round(med.confidence * 100)}%)</span>`;
                }

                let details = "";
                if (med.dosage) details += `<div class="detail">Dosage: ${med.dosage}</div>`;
                if (med.frequency) details += `<div class="detail">Frequency: ${med.frequency}</div>`;
                if (med.duration) details += `<div class="detail">Duration: ${med.duration}</div>`;

                let purpose = "";
                if (med.purpose) {
                    purpose = `<div class="purpose">${med.purpose}</div>`;
                }
                if (med.side_effects) {
                    purpose += `<div class="detail" style="margin-top:0.25rem;color:#991b1b">Side effects: ${med.side_effects}</div>`;
                }

                let summary = "";
                if (data.per_medicine_summaries && data.per_medicine_summaries[i]) {
                    summary = `<div class="purpose">${data.per_medicine_summaries[i]}</div>`;
                }

                card.innerHTML = `
                    <h4>${med.name} ${badge}</h4>
                    ${details}
                    ${purpose}
                    ${summary}
                `;
                medContainer.appendChild(card);
            });
        }

        // Translation
        document.getElementById("translation-text").textContent = data.translated_text;

        // Audio
        const audioSection = document.getElementById("audio-section");
        if (data.audio_url) {
            document.getElementById("audio-player").src = data.audio_url;
            audioSection.style.display = "block";
        } else {
            audioSection.style.display = "none";
        }

        // Disclaimer
        document.getElementById("disclaimer-text").textContent = data.disclaimer;

        // Latency
        document.getElementById("latency-value").textContent =
            `Processed in ${(data.latency_ms / 1000).toFixed(1)} seconds`;

        resultsEl.classList.add("active");
        resultsEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function showError(msg) {
        errorEl.textContent = msg;
        errorEl.classList.add("active");
    }

    function hideError() {
        errorEl.classList.remove("active");
    }
});
