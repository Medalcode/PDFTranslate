/**
 * PDFTranslate — Frontend Logic
 * Handles drag-and-drop upload, status polling, and download.
 */

(function () {
  "use strict";

  // ── Element refs ─────────────────────────────────────────────────────────
  const dropzone       = document.getElementById("dropzone");
  const fileInput      = document.getElementById("file-input");
  const fileInfo       = document.getElementById("file-info");
  const fileName       = document.getElementById("file-name");
  const fileSize       = document.getElementById("file-size");
  const removeBtn      = document.getElementById("remove-btn");
  const btnTranslate   = document.getElementById("btn-translate");
  const btnText        = document.getElementById("btn-text");
  const progressSec    = document.getElementById("progress-section");
  const progressLabel  = document.getElementById("progress-label");
  const progressPct    = document.getElementById("progress-pct");
  const progressFill   = document.getElementById("progress-fill");
  const stepUpload     = document.getElementById("step-upload");
  const stepTranslate  = document.getElementById("step-translate");
  const stepDone       = document.getElementById("step-done");
  const downloadSec    = document.getElementById("download-section");
  const btnDownload    = document.getElementById("btn-download");
  const btnReset       = document.getElementById("btn-reset");
  const errorBanner    = document.getElementById("error-banner");
  const errorMsg       = document.getElementById("error-msg");

  let selectedFile = null;
  let pollInterval  = null;

  // ── File formatting ───────────────────────────────────────────────────────
  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / (1024 * 1024)).toFixed(2) + " MB";
  }

  // ── Show file info ────────────────────────────────────────────────────────
  function showFile(file) {
    selectedFile = file;
    fileName.textContent = file.name;
    fileSize.textContent = formatBytes(file.size);
    fileInfo.style.display = "flex";
    dropzone.style.display = "none";
    btnTranslate.disabled = false;
    hideError();
  }

  function clearFile() {
    selectedFile = null;
    fileInput.value = "";
    fileInfo.style.display = "none";
    dropzone.style.display = "block";
    btnTranslate.disabled = true;
    hideError();
  }

  // ── Error handling ────────────────────────────────────────────────────────
  function showError(msg) {
    errorMsg.textContent = msg;
    errorBanner.style.display = "flex";
  }
  function hideError() {
    errorBanner.style.display = "none";
  }

  // ── Progress update ───────────────────────────────────────────────────────
  function setProgress(pct, label) {
    progressFill.style.width = pct + "%";
    progressPct.textContent = pct + "%";
    progressLabel.textContent = label;
  }

  function activateStep(id) {
    [stepUpload, stepTranslate, stepDone].forEach(s => {
      s.classList.remove("active", "done");
    });
    const steps = [stepUpload, stepTranslate, stepDone];
    const idx = steps.findIndex(s => s.id === id);
    steps.forEach((s, i) => {
      if (i < idx) s.classList.add("done");
    });
    const target = document.getElementById(id);
    if (target) target.classList.add("active");
  }

  // ── Reset to initial state ────────────────────────────────────────────────
  function resetUI() {
    clearFile();
    progressSec.style.display = "none";
    downloadSec.style.display = "none";
    setProgress(0, "Uploading…");
    [stepUpload, stepTranslate, stepDone].forEach(s => s.classList.remove("active", "done"));
    btnTranslate.style.display = "flex";
    btnTranslate.disabled = true;
    btnText.textContent = "Translate PDF";
    hideError();
    if (pollInterval) clearInterval(pollInterval);
  }

  // ── Drag & drop ───────────────────────────────────────────────────────────
  dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dropzone.classList.add("drag-over");
  });

  dropzone.addEventListener("dragleave", () => {
    dropzone.classList.remove("drag-over");
  });

  dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dropzone.classList.remove("drag-over");
    const files = e.dataTransfer.files;
    if (files.length && files[0].type === "application/pdf") {
      showFile(files[0]);
    } else {
      showError("Please drop a valid PDF file.");
    }
  });

  dropzone.addEventListener("click", () => fileInput.click());

  fileInput.addEventListener("change", () => {
    if (fileInput.files.length) showFile(fileInput.files[0]);
  });

  removeBtn.addEventListener("click", clearFile);

  // ── Translate ─────────────────────────────────────────────────────────────
  btnTranslate.addEventListener("click", async () => {
    if (!selectedFile) return;

    // Validate size (50 MB)
    if (selectedFile.size > 50 * 1024 * 1024) {
      showError("File too large. Maximum size is 50 MB.");
      return;
    }

    hideError();
    btnTranslate.style.display = "none";
    progressSec.style.display = "block";
    downloadSec.style.display = "none";

    setProgress(10, "Uploading…");
    activateStep("step-upload");

    const formData = new FormData();
    formData.append("file", selectedFile);

    let jobId;
    try {
      const res = await fetch("/translate", { method: "POST", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.detail || "Upload failed.");
      }
      const data = await res.json();
      jobId = data.job_id;
    } catch (err) {
      showError(err.message || "Upload failed. Please try again.");
      btnTranslate.style.display = "flex";
      progressSec.style.display = "none";
      return;
    }

    // Upload done → start translating
    setProgress(30, "Translating pages…");
    activateStep("step-translate");

    // ── Poll status ──────────────────────────────────────────────────────
    let fakePct = 30;
    pollInterval = setInterval(async () => {
      try {
        const res = await fetch(`/status/${jobId}`);
        if (!res.ok) throw new Error("Status check failed.");
        const data = await res.json();

        if (data.status === "done") {
          clearInterval(pollInterval);
          pollInterval = null;
          setProgress(100, "Complete!");
          stepTranslate.classList.remove("active");
          stepTranslate.classList.add("done");
          stepDone.classList.add("active");
          stepDone.classList.add("done");

          // Show download
          setTimeout(() => {
            progressSec.style.display = "none";
            downloadSec.style.display = "flex";
            btnDownload.href = `/download/${jobId}`;
          }, 600);

        } else if (data.status === "error") {
          clearInterval(pollInterval);
          pollInterval = null;
          const errDetail = data.error || "Translation failed. Please try again.";
          showError(errDetail);
          progressSec.style.display = "none";
          btnTranslate.style.display = "flex";
          btnTranslate.disabled = false;

        } else {
          // Still processing — increment progress bar slowly
          if (fakePct < 90) {
            fakePct = Math.min(fakePct + 2, 90);
            setProgress(fakePct, "Translating pages…");
          }
        }
      } catch (err) {
        // Don't break on transient network errors during polling
        console.warn("Polling error:", err);
      }
    }, 2000);
  });

  // ── Reset ─────────────────────────────────────────────────────────────────
  btnReset.addEventListener("click", resetUI);
  btnDownload.addEventListener("click", (e) => {
    // Allow default download; but also trigger the anchor download attr
    if (!btnDownload.href || btnDownload.href === window.location.href + "#") {
      e.preventDefault();
    }
  });

  // ── Init ──────────────────────────────────────────────────────────────────
  resetUI();
  dropzone.style.display = "block";
  btnTranslate.style.display = "flex";
})();
