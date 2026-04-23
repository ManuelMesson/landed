const trackSelectEl = document.querySelector("#tracker-track-select");
const jobsBody = document.querySelector("#jobs-body");
const summaryEl = document.querySelector("#tracker-summary");
const emptyState = document.querySelector("#empty-state");

function badge(status) {
  return `<span class="status-badge status-${status}">${status}</span>`;
}

function analysisBlock(title, items) {
  const content = (items || []).map((item) => `<li>${item}</li>`).join("");
  return `<div><strong>${title}</strong><ul>${content}</ul></div>`;
}

function detailMarkup(job) {
  return `
    <div class="detail-panel">
      <p><strong>Summary:</strong> ${job.analysis.role_summary}</p>
      ${analysisBlock("Key requirements", job.analysis.key_requirements)}
      ${analysisBlock("Gaps", job.analysis.gaps_to_address)}
      ${analysisBlock("Talking points", job.analysis.talking_points)}
      <div class="row-actions">
        <a class="ghost-link" href="/jordan?mode=job&job_id=${job.id}">Prep with Jordan →</a>
      </div>
    </div>
  `;
}

function renderJobs(jobs) {
  jobsBody.innerHTML = "";
  emptyState.classList.toggle("hidden", jobs.length !== 0);
  summaryEl.textContent = `${jobs.length} application${jobs.length === 1 ? "" : "s"}`;
  jobs.forEach((job) => {
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${job.company}</td>
      <td>${job.role}</td>
      <td>${job.track_display_name}</td>
      <td>${job.date_applied}</td>
      <td>${job.ats_score}%</td>
      <td>${job.hm_score}</td>
      <td>${badge(job.status)}</td>
      <td class="row-actions">
        <button class="secondary-button" type="button" data-action="toggle" data-id="${job.id}">Details</button>
        <a class="ghost-link" href="/jordan?mode=job&job_id=${job.id}">Prep with Jordan →</a>
      </td>
    `;
    const detailRow = document.createElement("tr");
    detailRow.classList.add("hidden");
    detailRow.dataset.detailFor = String(job.id);
    detailRow.innerHTML = `<td colspan="8">${detailMarkup(job)}</td>`;
    jobsBody.append(row, detailRow);
  });
}

async function loadTracks() {
  const response = await fetch("/tracks");
  const tracks = await response.json();
  trackSelectEl.innerHTML = `<option value="">All tracks</option>`;
  tracks.forEach((track) => {
    const option = document.createElement("option");
    option.value = track.id;
    option.textContent = track.display_name;
    trackSelectEl.appendChild(option);
  });
  const params = new URLSearchParams(window.location.search);
  if (params.get("track_id")) {
    trackSelectEl.value = params.get("track_id");
  }
}

async function loadJobs() {
  const params = new URLSearchParams();
  if (trackSelectEl.value) params.set("track_id", trackSelectEl.value);
  const response = await fetch(`/jobs?${params.toString()}`);
  const jobs = await response.json();
  renderJobs(jobs);
}

trackSelectEl.addEventListener("change", loadJobs);
jobsBody.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action='toggle']");
  if (!button) return;
  const detailRow = jobsBody.querySelector(`[data-detail-for='${button.dataset.id}']`);
  detailRow.classList.toggle("hidden");
});

Promise.all([loadTracks(), loadJobs()]);
