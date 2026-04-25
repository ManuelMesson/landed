const {
  fetchCurrentUser,
  fetchJson,
  redirectToLogin,
  renderAuthNav,
  requireAuth,
} = window.LandedAuth;

const trackSelectEl = document.querySelector("#tracker-track-select");
const jobsBody     = document.querySelector("#jobs-body");
const summaryEl    = document.querySelector("#tracker-summary");
const emptyState   = document.querySelector("#empty-state");

function badge(status) {
  return `<span class="status-badge status-${status}">${status}</span>`;
}

function jordanBadge(sessionCount, readinessScore, job) {
  if (!sessionCount) {
    const nudge = jordanRowNudge(job);
    return `<div class="jordan-row-nudge">
      <span class="jordan-nudge-line">${nudge}</span>
      <a class="jordan-nudge-link" href="/jordan?mode=job&job_id=${job.id}">Prep this role →</a>
    </div>`;
  }
  const color = readinessScore >= 7 ? "jordan-badge-green" : readinessScore >= 5 ? "jordan-badge-yellow" : "jordan-badge-red";
  return `<span class="jordan-badge ${color}">${sessionCount} session${sessionCount > 1 ? "s" : ""} · ${readinessScore.toFixed(1)}/10</span>`;
}

function jordanRowNudge(job) {
  const ats = job.ats_score || 0;
  const company = job.company || "this role";
  if (ats >= 75) return `Strong match at ${company}. Don't leave it on the table.`;
  if (ats >= 55) return `Solid shot. I can close the gap before you walk in.`;
  if (ats >= 35) return `Stretch role — I'll show you exactly how to pitch it.`;
  return `This one needs prep. Let's build the angle together.`;
}

function detailCard(label, items, modifier = "") {
  if (!items || !items.length) return "";
  const bullets = items.map(i => `<li>${i}</li>`).join("");
  return `<div class="detail-card ${modifier}">
    <p class="detail-card-label">${label}</p>
    <ul class="detail-card-list">${bullets}</ul>
  </div>`;
}

function detailMarkup(job, profile) {
  const a = job.analysis || {};

  const jordanSection = profile && profile.session_count > 0
    ? `<div class="detail-jordan-history">
        <div class="detail-jordan-header">
          <span class="detail-jordan-title">Jordan · ${profile.session_count} session${profile.session_count > 1 ? "s" : ""}</span>
          <span class="readiness-pill">${profile.readiness_score.toFixed(1)}/10 readiness</span>
        </div>
        ${profile.known_strengths.length ? `<p class="detail-strength">✅ ${profile.known_strengths.slice(0, 2).join(" · ")}</p>` : ""}
        ${profile.known_weaknesses.length ? `<p class="detail-focus">Focus next: ${profile.known_weaknesses.slice(0, 2).join(" · ")}</p>` : ""}
        <a class="action-pill action-primary detail-jordan-cta" href="/jordan?mode=job&job_id=${job.id}">
          Session ${profile.session_count + 1} →
        </a>
      </div>`
    : `<a class="action-pill action-primary" href="/jordan?mode=job&job_id=${job.id}">Prep with Jordan →</a>`;

  return `
    <div class="detail-panel">
      ${a.role_summary ? `<p class="detail-summary">${a.role_summary}</p>` : ""}
      <div class="detail-grid">
        ${detailCard("Key requirements", a.key_requirements)}
        ${detailCard("Your gaps", a.gaps_to_address, "detail-card-gaps")}
        ${detailCard("Talking points", a.talking_points)}
      </div>
      ${jordanSection}
    </div>
  `;
}

async function fetchProfile(jobId) {
  try {
    const res = await fetchJson(`/jordan/profile/job/${jobId}`);
    return await res.json();
  } catch {
    return null;
  }
}

async function renderJobs(jobs) {
  jobsBody.innerHTML = "";
  emptyState.classList.toggle("hidden", jobs.length !== 0);
  summaryEl.textContent = `${jobs.length} application${jobs.length === 1 ? "" : "s"}`;

  // Fetch Jordan profiles in parallel
  const profiles = await Promise.all(jobs.map(job => fetchProfile(job.id)));

  // Jordan pipeline summary — specific, not generic
  const jordanMsg = document.getElementById("jordan-pipeline-message");
  if (jordanMsg) {
    const prepped = profiles.filter(p => p && p.session_count > 0).length;
    const unprepped = jobs.length - prepped;
    // Find highest-scoring unprepped job to call out by name
    const unprepedJobs = jobs.filter((j, i) => !profiles[i] || !profiles[i].session_count);
    const bestUnprepped = unprepedJobs.sort((a, b) => (b.ats_score || 0) - (a.ats_score || 0))[0];
    // Find best prepped job score
    const preppedScores = profiles.filter(p => p && p.session_count > 0).map(p => p.readiness_score || 0);
    const bestReadiness = preppedScores.length ? Math.max(...preppedScores) : 0;

    if (jobs.length === 0) {
      jordanMsg.textContent = "Nothing here yet. Go to the analyzer, paste a job post — I'll score it and we start from there.";
    } else if (prepped === 0) {
      if (bestUnprepped && bestUnprepped.ats_score >= 60) {
        jordanMsg.textContent = `${bestUnprepped.company} is your strongest match at ${bestUnprepped.ats_score}% — and you haven't prepped it yet. That's the one I'd start with.`;
      } else {
        jordanMsg.textContent = `${jobs.length} application${jobs.length === 1 ? "" : "s"} and none prepped. Pick your best shot — let's build your answers before they call.`;
      }
    } else if (unprepped === 0) {
      if (bestReadiness >= 8) {
        jordanMsg.textContent = `All ${prepped} prepped. Your top readiness score is ${bestReadiness.toFixed(1)}/10. You're ready — now apply more.`;
      } else {
        jordanMsg.textContent = `All ${prepped} prepped. Run another session on the ones below 7 — that's where interviews get lost.`;
      }
    } else {
      if (bestUnprepped && bestUnprepped.ats_score >= 65) {
        jordanMsg.textContent = `${prepped} of ${jobs.length} prepped. ${bestUnprepped.company} scores ${bestUnprepped.ats_score}% and hasn't been touched — that one should be next.`;
      } else {
        jordanMsg.textContent = `${prepped} of ${jobs.length} prepped. ${unprepped} application${unprepped === 1 ? "" : "s"} waiting — the interview could come any day.`;
      }
    }
  }

  jobs.forEach((job, i) => {
    const profile = profiles[i];
    const row = document.createElement("tr");
    row.innerHTML = `
      <td>${job.company}</td>
      <td>${job.role}</td>
      <td>${job.track_display_name}</td>
      <td>${job.date_applied}</td>
      <td>${job.ats_score}%</td>
      <td>${job.hm_score}</td>
      <td>${badge(job.status)}</td>
      <td>${jordanBadge(profile?.session_count || 0, profile?.readiness_score || 0, job)}</td>
      <td class="row-actions">
        <button class="secondary-button" type="button" data-action="toggle" data-id="${job.id}">Details</button>
      </td>
    `;
    const detailRow = document.createElement("tr");
    detailRow.classList.add("hidden");
    detailRow.dataset.detailFor = String(job.id);
    detailRow.innerHTML = `<td colspan="9">${detailMarkup(job, profile)}</td>`;
    jobsBody.append(row, detailRow);
  });
}

async function loadTracks() {
  const response = await fetchJson("/tracks");
  const tracks = await response.json();
  trackSelectEl.innerHTML = `<option value="">All tracks</option>`;
  tracks.forEach((track) => {
    const option = document.createElement("option");
    option.value = track.id;
    option.textContent = track.display_name;
    trackSelectEl.appendChild(option);
  });
  const params = new URLSearchParams(window.location.search);
  if (params.get("track_id")) trackSelectEl.value = params.get("track_id");
}

async function loadJobs() {
  const params = new URLSearchParams();
  if (trackSelectEl.value) params.set("track_id", trackSelectEl.value);
  const response = await fetchJson(`/jobs?${params.toString()}`);
  const jobs = await response.json();
  await renderJobs(jobs);
}

trackSelectEl.addEventListener("change", loadJobs);
jobsBody.addEventListener("click", (event) => {
  const button = event.target.closest("[data-action='toggle']");
  if (!button) return;
  const detailRow = jobsBody.querySelector(`[data-detail-for='${button.dataset.id}']`);
  detailRow?.classList.toggle("hidden");
});

async function bootstrap() {
  if (!requireAuth()) return;
  const user = await fetchCurrentUser();
  if (!user) {
    redirectToLogin();
    return;
  }
  renderAuthNav(user);
  await Promise.all([loadTracks(), loadJobs()]);
}

bootstrap();
