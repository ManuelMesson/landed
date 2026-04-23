const state = {
  tracks: [],
  currentTrackId: null,
  currentAnalysis: null,
  debounceId: null,
};

const trackSelect = document.querySelector("#track-select");
const jobPost = document.querySelector("#job-post");
const resumeEditor = document.querySelector("#resume-editor");
const analyzeButton = document.querySelector("#analyze-button");
const saveResumeButton = document.querySelector("#save-resume");
const logJobButton = document.querySelector("#log-job");
const statusLine = document.querySelector("#status-line");

const atsScoreEl = document.querySelector("#ats-score");
const hmScoreEl = document.querySelector("#hm-score");
const atsMeter = document.querySelector("#ats-meter");
const hmMeter = document.querySelector("#hm-meter");

function setStatus(message) {
  statusLine.textContent = message;
}

function renderList(id, items) {
  const node = document.querySelector(`#${id}`);
  node.innerHTML = "";
  (items.length ? items : ["Waiting for analysis."]).forEach((item) => {
    const li = document.createElement("li");
    li.textContent = item;
    node.appendChild(li);
  });
}

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

function renderAnalysis(payload) {
  state.currentAnalysis = payload;
  animateNumber(atsScoreEl, payload.ats_score, "%", 0);
  animateNumber(hmScoreEl, payload.hm_score, "", 1);
  atsMeter.style.width = `${payload.ats_score}%`;
  hmMeter.style.width = `${Math.min(100, payload.hm_score * 10)}%`;
  atsMeter.style.background = meterColor(payload.ats_score);
  hmMeter.style.background = meterColor(payload.ats_score);
  document.querySelector("#role-summary").textContent = payload.role_summary;
  renderList("key-requirements", payload.key_requirements);
  renderList("your-strengths", payload.your_strengths);
  renderList("gaps-to-address", payload.gaps_to_address);
  renderList("talking-points", payload.talking_points);
  renderList("red-flags", payload.red_flags);
}

async function loadTracks() {
  const response = await fetch("/tracks");
  state.tracks = await response.json();
  trackSelect.innerHTML = "";
  state.tracks.forEach((track) => {
    const option = document.createElement("option");
    option.value = track.id;
    option.textContent = track.display_name;
    trackSelect.appendChild(option);
  });
  const initialTrack = state.tracks[0];
  if (initialTrack) {
    state.currentTrackId = initialTrack.id;
    trackSelect.value = String(initialTrack.id);
    resumeEditor.value = initialTrack.base_resume;
  }
}

async function runAnalysis() {
  if (!jobPost.value.trim()) {
    setStatus("Paste a job post to analyze.");
    return;
  }
  setStatus("Analyzing with Landed...");
  const response = await fetch("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      job_post: jobPost.value,
      resume: resumeEditor.value,
      track_id: Number(trackSelect.value),
    }),
  });
  const payload = await response.json();
  renderAnalysis(payload);
  setStatus("Analysis updated.");
}

async function saveBaseResume() {
  setStatus("Saving base resume...");
  await fetch(`/tracks/${trackSelect.value}/resume`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume: resumeEditor.value }),
  });
  setStatus("Base resume saved for this track.");
}

async function logJob() {
  if (!state.currentAnalysis) {
    setStatus("Run Analyze before logging the job.");
    return;
  }
  const payload = {
    track_id: Number(trackSelect.value),
    company: document.querySelector("#company").value || "Unknown company",
    role: document.querySelector("#role").value || "Unknown role",
    job_post: jobPost.value,
    date_applied: document.querySelector("#date-applied").value || new Date().toISOString().slice(0, 10),
    ats_score: state.currentAnalysis.ats_score,
    hm_score: state.currentAnalysis.hm_score,
    analysis: state.currentAnalysis,
    interview_prep: state.currentAnalysis.talking_points.join(" "),
    notes: "",
  };
  const response = await fetch("/jobs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const job = await response.json();
  setStatus(`Logged ${job.company} - ${job.role}.`);
  window.location.href = `/tracker?track_id=${job.track_id}`;
}

function scheduleAnalysis() {
  clearTimeout(state.debounceId);
  state.debounceId = setTimeout(runAnalysis, 1500);
}

trackSelect.addEventListener("change", () => {
  const track = state.tracks.find((item) => item.id === Number(trackSelect.value));
  state.currentTrackId = Number(trackSelect.value);
  if (track) {
    resumeEditor.value = track.base_resume;
    document.querySelector("#role").value = track.display_name;
  }
  scheduleAnalysis();
});

jobPost.addEventListener("input", scheduleAnalysis);
resumeEditor.addEventListener("input", scheduleAnalysis);
analyzeButton.addEventListener("click", runAnalysis);
saveResumeButton.addEventListener("click", saveBaseResume);
logJobButton.addEventListener("click", logJob);

document.querySelector("#date-applied").value = new Date().toISOString().slice(0, 10);
loadTracks().catch((error) => setStatus(`Failed to load tracks: ${error.message}`));
