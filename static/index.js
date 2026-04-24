const state = {
  tracks: [],
  currentTrackId: null,
  currentAnalysis: null,
  debounceId: null,
};

// ── Toast system ──
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

// ── Button loading state ──
function setButtonLoading(button, loading) {
  const label = button.querySelector(".btn-label");
  const spinner = button.querySelector(".btn-spinner");
  button.disabled = loading;
  if (label) label.textContent = loading ? "Analyzing..." : "Analyze";
  if (spinner) spinner.classList.toggle("hidden", !loading);
}

// ── Stage transitions ──
function showStage(id) {
  const el = document.querySelector(`#${id}`);
  if (el) {
    el.classList.remove("hidden");
    requestAnimationFrame(() => el.classList.add("reveal"));
  }
}

function hideStage(id) {
  const el = document.querySelector(`#${id}`);
  if (el) el.classList.add("hidden");
}

const trackSelect = document.querySelector("#track-select");
const jobPost = document.querySelector("#job-post");
const resumeEditor = document.querySelector("#resume-editor");
const analyzeButton = document.querySelector("#analyze-button");
const saveResumeButton = document.querySelector("#save-resume");
const logJobButton = document.querySelector("#log-job");
const statusLine = document.querySelector("#status-line");
const experienceList = document.querySelector("#experience-list");
const projectList = document.querySelector("#project-list");
const addExperienceButton = document.querySelector("#add-experience");
const addProjectButton = document.querySelector("#add-project");

const atsScoreEl = document.querySelector("#ats-score");
const hmScoreEl = document.querySelector("#hm-score");
const atsMeter = document.querySelector("#ats-meter");
const hmMeter = document.querySelector("#hm-meter");

function setStatus(message) {
  if (statusLine) statusLine.textContent = message;
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

  showStage("stage-score");
  showStage("stage-analysis");

  animateNumber(atsScoreEl, payload.ats_score, "%", 0);
  animateNumber(hmScoreEl, payload.hm_score, "", 1);
  atsMeter.style.width = `${payload.ats_score}%`;
  hmMeter.style.width = `${Math.min(100, payload.hm_score * 10)}%`;

  const roleSummary = document.querySelector("#role-summary");
  if (roleSummary) roleSummary.textContent = payload.role_summary || "";

  renderList("key-requirements", payload.key_requirements);
  renderList("your-strengths", payload.your_strengths);
  renderList("gaps-to-address", payload.gaps_to_address);
  renderList("talking-points", payload.talking_points);
  renderList("red-flags", payload.red_flags);

  // Scroll score into view
  document.querySelector("#stage-score")?.scrollIntoView({ behavior: "smooth", block: "start" });
}

function createField(labelText, name, placeholder = "", value = "", options = {}) {
  const wrapper = document.createElement("label");
  wrapper.className = "entry-field";

  const label = document.createElement("span");
  label.textContent = labelText;
  wrapper.appendChild(label);

  const control = options.multiline ? document.createElement("textarea") : document.createElement("input");
  control.name = name;
  control.placeholder = placeholder;
  control.value = value;
  if (options.multiline) {
    control.rows = options.rows || 4;
  } else {
    control.type = "text";
  }
  wrapper.appendChild(control);
  return wrapper;
}

function createRemoveButton(label) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "remove-entry-button";
  button.dataset.removeEntry = "true";
  button.setAttribute("aria-label", `Remove ${label}`);
  button.textContent = "✕ Remove";
  return button;
}

function createExperienceEntry(entry = {}) {
  const card = document.createElement("article");
  card.className = "entry-card";
  card.dataset.entryType = "experience";

  const header = document.createElement("div");
  header.className = "entry-card-header";

  const title = document.createElement("h4");
  title.textContent = "Experience entry";
  header.appendChild(title);
  header.appendChild(createRemoveButton("experience entry"));
  card.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "entry-grid";
  grid.appendChild(createField("Company", "company", "Amazon", entry.company || ""));
  grid.appendChild(createField("Title", "title", "Customer Success Specialist", entry.title || ""));
  grid.appendChild(createField("Dates", "dates", "2024-Present", entry.dates || ""));
  card.appendChild(grid);

  const bullets = Array.isArray(entry.bullets) && entry.bullets.length ? entry.bullets.join("\n") : "";
  card.appendChild(
    createField("Bullets", "bullets", "Led onboarding for enterprise customers\nImproved response time", bullets, {
      multiline: true,
      rows: 4,
    })
  );
  return card;
}

function createProjectEntry(entry = {}) {
  const card = document.createElement("article");
  card.className = "entry-card";
  card.dataset.entryType = "project";

  const header = document.createElement("div");
  header.className = "entry-card-header";

  const title = document.createElement("h4");
  title.textContent = "Project entry";
  header.appendChild(title);
  header.appendChild(createRemoveButton("project entry"));
  card.appendChild(header);

  const grid = document.createElement("div");
  grid.className = "entry-grid entry-grid-project";
  grid.appendChild(createField("Project name", "name", "Landed", entry.name || ""));
  grid.appendChild(
    createField("Description", "description", "AI job search command center", entry.description || "")
  );
  card.appendChild(grid);

  return card;
}

function parseExperienceLine(line) {
  const cleaned = line.replace(/^-+\s*/, "").trim();
  if (!cleaned) {
    return { company: "", title: "", dates: "", bullets: [] };
  }
  const parts = cleaned.split(",").map((part) => part.trim()).filter(Boolean);
  if (parts.length >= 3) {
    return {
      title: parts[0],
      company: parts.slice(1, -1).join(", "),
      dates: parts.at(-1) || "",
      bullets: [],
    };
  }
  if (parts.length === 2) {
    return {
      title: parts[0],
      company: parts[1],
      dates: "",
      bullets: [],
    };
  }
  return { title: cleaned, company: "", dates: "", bullets: [] };
}

function parseProjectLine(line) {
  const cleaned = line.replace(/^-+\s*/, "").trim();
  if (!cleaned) {
    return { name: "", description: "" };
  }
  const parts = cleaned.split(/\s+-\s+/);
  if (parts.length >= 2) {
    return { name: parts[0].trim(), description: parts.slice(1).join(" - ").trim() };
  }
  return { name: cleaned, description: "" };
}

function parseResume(text) {
  const parsed = {
    nameTitle: "",
    contact: "",
    experience: [],
    projects: [],
    skills: "",
    education: "",
  };
  let currentSection = "";
  let currentExperience = null;

  const lines = text.split(/\r?\n/);
  lines.forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      return;
    }
    if (trimmed.startsWith("Name:")) {
      parsed.nameTitle = trimmed.slice("Name:".length).trim();
      currentSection = "";
      currentExperience = null;
      return;
    }
    if (trimmed.startsWith("Contact:")) {
      parsed.contact = trimmed.slice("Contact:".length).trim();
      currentSection = "";
      currentExperience = null;
      return;
    }
    if (trimmed === "Experience:") {
      currentSection = "experience";
      currentExperience = null;
      return;
    }
    if (trimmed === "Projects:") {
      currentSection = "projects";
      currentExperience = null;
      return;
    }
    if (trimmed.startsWith("Skills:")) {
      parsed.skills = trimmed.slice("Skills:".length).trim();
      currentSection = "skills";
      currentExperience = null;
      return;
    }
    if (trimmed.startsWith("Education:")) {
      parsed.education = trimmed.slice("Education:".length).trim();
      currentSection = "education";
      currentExperience = null;
      return;
    }

    if (currentSection === "experience") {
      if (/^\s+- /.test(line) && currentExperience) {
        currentExperience.bullets.push(trimmed.replace(/^-+\s*/, "").trim());
        return;
      }
      if (/^- /.test(trimmed)) {
        currentExperience = parseExperienceLine(trimmed);
        parsed.experience.push(currentExperience);
        return;
      }
      return;
    }

    if (currentSection === "projects") {
      if (/^- /.test(trimmed)) {
        parsed.projects.push(parseProjectLine(trimmed));
      }
      return;
    }

    if (currentSection === "skills") {
      parsed.skills = [parsed.skills, trimmed].filter(Boolean).join(", ");
      return;
    }

    if (currentSection === "education") {
      parsed.education = [parsed.education, trimmed].filter(Boolean).join("\n");
    }
  });

  if (!parsed.experience.length) {
    parsed.experience.push({ company: "", title: "", dates: "", bullets: [] });
  }
  if (!parsed.projects.length) {
    parsed.projects.push({ name: "", description: "" });
  }
  return parsed;
}

function setControlValue(selector, value) {
  const control = document.querySelector(selector);
  if (control) {
    control.value = value;
  }
}

function renderResumeEditor(parsed) {
  setControlValue("#resume-name-title", parsed.nameTitle || "");
  setControlValue("#resume-contact", parsed.contact || "");
  setControlValue("#resume-skills", parsed.skills || "");
  setControlValue("#resume-education", parsed.education || "");

  experienceList.innerHTML = "";
  parsed.experience.forEach((entry) => experienceList.appendChild(createExperienceEntry(entry)));

  projectList.innerHTML = "";
  parsed.projects.forEach((entry) => projectList.appendChild(createProjectEntry(entry)));
}

function readTextValue(root, selector) {
  const control = root.querySelector(selector);
  return control ? control.value.trim() : "";
}

function collectExperienceEntries() {
  return Array.from(experienceList.querySelectorAll("[data-entry-type='experience']")).map((card) => ({
    company: readTextValue(card, "[name='company']"),
    title: readTextValue(card, "[name='title']"),
    dates: readTextValue(card, "[name='dates']"),
    bullets: readTextValue(card, "[name='bullets']")
      .split("\n")
      .map((bullet) => bullet.trim())
      .filter(Boolean),
  }));
}

function collectProjectEntries() {
  return Array.from(projectList.querySelectorAll("[data-entry-type='project']")).map((card) => ({
    name: readTextValue(card, "[name='name']"),
    description: readTextValue(card, "[name='description']"),
  }));
}

function serializeResume() {
  const nameTitle = readTextValue(document, "#resume-name-title");
  const contact = readTextValue(document, "#resume-contact");
  const skills = readTextValue(document, "#resume-skills");
  const education = readTextValue(document, "#resume-education");
  const experienceEntries = collectExperienceEntries();
  const projectEntries = collectProjectEntries();

  const lines = [];
  lines.push(`Name: ${nameTitle}`);
  if (contact) {
    lines.push(`Contact: ${contact}`);
  }
  lines.push("Experience:");
  experienceEntries
    .filter((entry) => entry.company || entry.title || entry.dates || entry.bullets.length)
    .forEach((entry) => {
      const headline = [entry.title, entry.company, entry.dates].filter(Boolean).join(", ");
      lines.push(`- ${headline}`);
      entry.bullets.forEach((bullet) => {
        lines.push(`  - ${bullet}`);
      });
    });
  lines.push("Projects:");
  projectEntries
    .filter((entry) => entry.name || entry.description)
    .forEach((entry) => {
      const projectLine = entry.description ? `${entry.name} - ${entry.description}` : entry.name;
      lines.push(`- ${projectLine}`);
    });
  lines.push(`Skills: ${skills}`);
  lines.push(`Education: ${education}`);
  return lines.join("\n").trim();
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
    renderResumeEditor(parseResume(initialTrack.base_resume));
  }
}

async function runAnalysis() {
  if (!jobPost.value.trim()) {
    showToast("Paste a job post first.", "error");
    return;
  }
  setButtonLoading(analyzeButton, true);
  document.querySelector("#analysis-loading")?.classList.remove("hidden");
  try {
    const response = await fetch("/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        job_post: jobPost.value,
        resume: serializeResume(),
        track_id: Number(trackSelect.value),
      }),
    });
    const payload = await response.json();
    renderAnalysis(payload);
  } catch (err) {
    showToast("Analysis failed. Try again.", "error");
  } finally {
    setButtonLoading(analyzeButton, false);
    document.querySelector("#analysis-loading")?.classList.add("hidden");
  }
}

async function saveBaseResume() {
  await fetch(`/tracks/${trackSelect.value}/resume`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ resume: serializeResume() }),
  });
  const track = state.tracks.find((item) => item.id === Number(trackSelect.value));
  if (track) track.base_resume = serializeResume();
  showToast("Resume saved ✓");
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
  showToast(`${job.company} logged ✓ — opening pipeline`);
  setTimeout(() => { window.location.href = `/tracker?track_id=${job.track_id}`; }, 1200);
}

function scheduleAnalysis() {
  clearTimeout(state.debounceId);
  state.debounceId = setTimeout(runAnalysis, 1500);
}

trackSelect.addEventListener("change", () => {
  const track = state.tracks.find((item) => item.id === Number(trackSelect.value));
  state.currentTrackId = Number(trackSelect.value);
  if (track) {
    renderResumeEditor(parseResume(track.base_resume));
    document.querySelector("#role").value = track.display_name;
  }
  scheduleAnalysis();
});

jobPost.addEventListener("input", scheduleAnalysis);
resumeEditor.addEventListener("input", scheduleAnalysis);
resumeEditor.addEventListener("click", (event) => {
  const removeButton = event.target.closest("[data-remove-entry='true']");
  if (removeButton) {
    removeButton.closest(".entry-card")?.remove();
    if (!experienceList.children.length) {
      experienceList.appendChild(createExperienceEntry());
    }
    if (!projectList.children.length) {
      projectList.appendChild(createProjectEntry());
    }
    scheduleAnalysis();
  }
});

addExperienceButton.addEventListener("click", () => {
  experienceList.appendChild(createExperienceEntry());
  scheduleAnalysis();
});

addProjectButton.addEventListener("click", () => {
  projectList.appendChild(createProjectEntry());
  scheduleAnalysis();
});

analyzeButton.addEventListener("click", runAnalysis);
saveResumeButton.addEventListener("click", saveBaseResume);
logJobButton.addEventListener("click", logJob);

// Tune panel
document.querySelector("#tune-button")?.addEventListener("click", () => {
  showStage("stage-tune");
  document.querySelector("#stage-tune")?.scrollIntoView({ behavior: "smooth", block: "start" });
});
document.querySelector("#close-tune")?.addEventListener("click", () => hideStage("stage-tune"));

// Log panel
document.querySelector("#log-job")?.addEventListener("click", () => {
  if (!state.currentAnalysis) { showToast("Run Analyze first.", "error"); return; }
  showStage("stage-log");
  document.querySelector("#stage-log")?.scrollIntoView({ behavior: "smooth", block: "start" });
});
document.querySelector("#close-log")?.addEventListener("click", () => hideStage("stage-log"));
document.querySelector("#confirm-log")?.addEventListener("click", logJob);

const dateApplied = document.querySelector("#date-applied");
if (dateApplied) dateApplied.value = new Date().toISOString().slice(0, 10);

window.LandedResumeEditor = { parseResume, serializeResume };
loadTracks().catch((error) => setStatus(`Failed to load tracks: ${error.message}`));
