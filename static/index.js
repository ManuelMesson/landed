const RESUME_KEY = "landed_user_resume";

const state = {
  currentAnalysis: null,
  savedJobId: null,
  debounceId: null,
};

// ── Resume storage ──
function getUserResume() {
  return localStorage.getItem(RESUME_KEY) || "";
}

function saveUserResume(text) {
  if (text.trim()) localStorage.setItem(RESUME_KEY, text.trim());
}

// ── Onboarding ──
function showOnboarding() {
  document.querySelector("#onboarding-overlay").classList.remove("hidden");
}

function hideOnboarding() {
  document.querySelector("#onboarding-overlay").classList.add("hidden");
}

function initOnboarding() {
  const textarea = document.querySelector("#onboarding-resume");
  const submit   = document.querySelector("#onboarding-submit");

  if (!getUserResume()) {
    showOnboarding();
  }

  submit.addEventListener("click", () => {
    const resume = textarea.value.trim();
    if (!resume) { showToast("Paste your resume first.", "error"); return; }
    saveUserResume(resume);
    hideOnboarding();
    showToast("Resume saved ✓");
  });
}

// ── Toast ──
function showToast(message, type = "success") {
  const container = document.querySelector("#toast-container");
  const toast = document.createElement("div");
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  requestAnimationFrame(() => toast.classList.add("toast-visible"));
  setTimeout(() => {
    toast.classList.remove("toast-visible");
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// ── Stage transitions ──
function showStage(id) {
  const el = document.querySelector(`#${id}`);
  if (el) {
    el.classList.remove("hidden");
    requestAnimationFrame(() => el.classList.add("reveal"));
  }
}

// ── Score animation ──
function meterColor(score) {
  if (score <= 50) return "var(--red)";
  if (score < 75) return "var(--yellow)";
  return "var(--green)";
}

function animateNumber(node, endValue, suffix = "", decimals = 0) {
  const current = Number(node.dataset.value || 0);
  const steps = 18;
  let step = 0;
  const delta = (endValue - current) / steps;
  const timer = setInterval(() => {
    step += 1;
    const value = step >= steps ? endValue : current + delta * step;
    node.textContent = `${value.toFixed(decimals)}${suffix}`;
    node.dataset.value = value.toString();
    if (step >= steps) clearInterval(timer);
  }, 20);
}

function renderList(id, items) {
  const node = document.querySelector(`#${id}`);
  if (!node) return;
  node.innerHTML = "";
  (items && items.length ? items : ["—"]).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  });
}

function renderAnalysis(payload) {
  state.currentAnalysis = payload;
  state.savedJobId = null;

  showStage("stage-score");
  showStage("stage-analysis");

  const atsScoreEl = document.querySelector("#ats-score");
  const hmScoreEl  = document.querySelector("#hm-score");
  const atsMeter   = document.querySelector("#ats-meter");
  const hmMeter    = document.querySelector("#hm-meter");

  animateNumber(atsScoreEl, payload.ats_score, "%", 0);
  animateNumber(hmScoreEl, payload.hm_score, "", 1);
  atsMeter.style.width = `${payload.ats_score}%`;
  atsMeter.style.background = meterColor(payload.ats_score);
  hmMeter.style.width = `${Math.min(100, payload.hm_score * 10)}%`;

  const roleSummary = document.querySelector("#role-summary");
  if (roleSummary) roleSummary.textContent = payload.role_summary || "";

  const jobIntel = document.querySelector("#job-intel");
  if (jobIntel) {
    const company = payload.company_name;
    const role    = payload.role_title || "";
    const style   = payload.interview_style;

    // Only show intel card if we have at least one real value
    if (company || role || style) {
      jobIntel.classList.remove("hidden");
      const companyDisplay = company ? (role ? `${company} — ${role}` : company) : role || "";
      if (companyDisplay) document.querySelector("#intel-company").textContent = companyDisplay;
      else document.querySelector("#intel-company").closest(".intel-row")?.classList.add("hidden");
      if (style) {
        document.querySelector("#intel-style").textContent = style;
      } else {
        document.querySelector("#intel-style").closest(".intel-row")?.classList.add("hidden");
      }
      if (payload.company_values && payload.company_values.length > 0) {
        document.querySelector("#intel-values").textContent = payload.company_values.slice(0, 4).join(" · ");
        document.querySelector("#intel-values-row").classList.remove("hidden");
      }
    }
  }

  renderList("key-requirements", payload.key_requirements);
  renderList("your-strengths", payload.your_strengths);
  renderList("gaps-to-address", payload.gaps_to_address);
  renderList("talking-points", payload.talking_points);
  renderList("red-flags", payload.red_flags);

  // Reset Jordan link to base (no job context until saved)
  const jordanLink = document.querySelector("#jordan-link");
  if (jordanLink) jordanLink.href = "/jordan";

  document.querySelector("#stage-score")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

// ── Analysis ──
const jobPost = document.querySelector("#job-post");
const analyzeButton = document.querySelector("#analyze-button");

async function runAnalysis() {
  const jobText = jobPost?.value.trim();
  if (!jobText) return;

  const resume = getUserResume();
  if (!resume) {
    showToast("Add your resume first.", "error");
    showOnboarding();
    return;
  }

  // Show loading state
  document.querySelector("#analysis-loading")?.classList.remove("hidden");
  if (analyzeButton) analyzeButton.textContent = "Analyzing...";

  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ job_post: jobText, resume, track_id: 1 }),
    });
    const payload = await response.json();
    renderAnalysis(payload);
  } catch {
    showToast("Analysis failed. Try again.", "error");
    if (analyzeButton) analyzeButton.classList.remove("hidden");
  } finally {
    document.querySelector("#analysis-loading")?.classList.add("hidden");
    if (analyzeButton) analyzeButton.textContent = "Analyze now";
  }
}

function scheduleAnalysis() {
  clearTimeout(state.debounceId);
  // Show fallback button after 3s of no more typing (user might want to trigger manually)
  if (analyzeButton) {
    clearTimeout(state.debounceId);
    state.debounceId = setTimeout(() => {
      if (jobPost.value.trim().length > 100) {
        runAnalysis();
      }
    }, 1500);
  }
}

jobPost?.addEventListener("input", scheduleAnalysis);
analyzeButton?.addEventListener("click", runAnalysis);

// Show fallback button after user pastes something but analysis hasn't started
jobPost?.addEventListener("focus", () => {
  if (analyzeButton && jobPost.value.trim().length > 50) {
    analyzeButton.classList.remove("hidden");
  }
});

// ── Save to Pipeline (toast, no redirect) ──
async function saveToPipeline() {
  if (!state.currentAnalysis) {
    showToast("Analyze a job first.", "error");
    return;
  }
  if (state.savedJobId) {
    showToast("Already saved ✓");
    return;
  }

  try {
    const payload = {
      track_id: 1,
      company: state.currentAnalysis.company_name || "Unknown company",
      role: state.currentAnalysis.role_title || "Unknown role",
      job_post: jobPost.value,
      date_applied: new Date().toISOString().slice(0, 10),
      ats_score: state.currentAnalysis.ats_score,
      hm_score: state.currentAnalysis.hm_score,
      analysis: state.currentAnalysis,
      interview_prep: (state.currentAnalysis.talking_points || []).join(" "),
      notes: "",
    };
    const response = await fetch("/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const job = await response.json();
    state.savedJobId = job.id;

    // Update Jordan link to job-specific mode
    const jordanLink = document.querySelector("#jordan-link");
    if (jordanLink) jordanLink.href = `/jordan?mode=job&job_id=${job.id}`;

    showToast(`${job.company} saved to pipeline ✓`);
  } catch {
    showToast("Could not save. Try again.", "error");
  }
}

document.querySelector("#save-pipeline-btn")?.addEventListener("click", saveToPipeline);

// ── Jordan link: save first if not yet saved ──
document.querySelector("#jordan-link")?.addEventListener("click", async (e) => {
  if (!state.currentAnalysis) return; // let default navigation happen
  if (!state.savedJobId) {
    e.preventDefault();
    await saveToPipeline();
    if (state.savedJobId) {
      window.location.href = `/jordan?mode=job&job_id=${state.savedJobId}`;
    }
  }
});

initOnboarding();
