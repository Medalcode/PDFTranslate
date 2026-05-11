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
  let activeJobId   = null;

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
    pollInterval = null;
    activeJobId = null;
  }

  function stopPolling() {
    if (pollInterval) clearInterval(pollInterval);
    pollInterval = null;
  }

  function progressForStatus(data) {
    if (data.status === "done") {
      return { pct: 100, label: "Translation Complete!", step: "step-done" };
    }

    if (data.status === "error") {
      return { pct: 0, label: "Translation failed", step: "step-translate" };
    }

    const phase = data.phase || "queued";
    const current = Number(data.current || 0);
    const total = Number(data.total || 0) || 1;

    if (phase === "extract") {
      return {
        pct: Math.round((current / total) * 33),
        label: `Extracting content: page ${current} of ${total}`,
        step: "step-upload",
      };
    }

    if (phase === "translate") {
      return {
        pct: 33 + Math.round((current / total) * 33),
        label: "Translating blocks…",
        step: "step-translate",
      };
    }

    if (phase === "overlay") {
      return {
        pct: 66 + Math.round((current / total) * 34),
        label: `Restoring layout: page ${current} of ${total}`,
        step: "step-translate",
      };
    }

    return { pct: 10, label: "Queued…", step: "step-upload" };
  }

  async function refreshStatus(jobId) {
    const res = await fetch(`/status/${jobId}`);
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Could not load job status.");
    }

    const data = await res.json();
    const progress = progressForStatus(data);

    setProgress(progress.pct, progress.label);
    activateStep(progress.step);

    if (data.status === "done") {
      stopPolling();
      setProgress(100, "Translation Complete!");
      confetti({
        particleCount: 150,
        spread: 70,
        origin: { y: 0.6 },
        colors: ["#3b82f6", "#8b5cf6", "#10b981"],
      });

      stepTranslate.classList.remove("active");
      stepTranslate.classList.add("done");
      stepDone.classList.add("active");
      stepDone.classList.add("done");

      setTimeout(() => {
        progressSec.style.display = "none";
        downloadSec.style.display = "flex";
        btnDownload.href = `/download/${jobId}`;
      }, 800);
      return true;
    }

    if (data.status === "error") {
      stopPolling();
      showError(data.error || "Translation failed. Check the PDF format or LLM quota.");
      progressSec.style.display = "none";
      btnTranslate.style.display = "flex";
      btnTranslate.disabled = false;
      return true;
    }

    return false;
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

    activeJobId = jobId;
    setProgress(10, "Queued…");
    activateStep("step-upload");

    stopPolling();
    await refreshStatus(jobId);
    pollInterval = window.setInterval(() => {
      if (!activeJobId) {
        stopPolling();
        return;
      }
      refreshStatus(activeJobId).catch((err) => {
        console.error("Status poll error:", err);
        showError(err.message || "Connection lost. Please refresh or check the PDF status.");
        stopPolling();
        progressSec.style.display = "none";
        btnTranslate.style.display = "flex";
        btnTranslate.disabled = false;
      });
    }, 1000);
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
