// auth.js globals used directly: fetchCurrentUser, fetchJson, redirectToLogin, renderAuthNav, requireAuth

const phaseWarmup = document.querySelector("#phase-warmup");
const phaseSession = document.querySelector("#phase-session");
const phaseSummary = document.querySelector("#phase-summary");

const startButton = document.querySelector("#start-button");
const warmupCard = document.querySelector("#warmup-card");
const questionEl = document.querySelector("#current-question");
const questionBubble = document.querySelector("#question-bubble");
const coachingBubble = document.querySelector("#coaching-bubble");
const thinkingBubble = document.querySelector("#jordan-thinking");
const audioEl = document.querySelector("#jordan-audio");
const micButton = document.querySelector("#mic-button");
const submitButton = document.querySelector("#submit-answer");
const answerInput = document.querySelector("#answer-text");
const retryButton = document.querySelector("#retry-button");
const restartButton = document.querySelector("#restart-button");
const summaryCard = document.querySelector("#summary-card");
const sessionTypeBar = document.querySelector("#session-type-bar");

// Jordan presence — visual state system
const jordanPresence = document.querySelector("#jordan-presence");
const jordanPresenceLabel = document.querySelector("#jordan-presence-label");

function setJordanState(state) {
  if (!jordanPresence) return;
  jordanPresence.classList.remove("is-speaking", "is-thinking");
  if (state === "speaking") {
    jordanPresence.classList.add("is-speaking");
    if (jordanPresenceLabel) jordanPresenceLabel.textContent = "Speaking";
  } else if (state === "thinking") {
    jordanPresence.classList.add("is-thinking");
    if (jordanPresenceLabel) jordanPresenceLabel.textContent = "Thinking";
  }
}

// Wire audio events to Jordan's visual state
if (audioEl) {
  audioEl.addEventListener("play",  () => setJordanState("speaking"));
  audioEl.addEventListener("pause", () => setJordanState("idle"));
  audioEl.addEventListener("ended", () => setJordanState("idle"));
}
const warmupSessionBadge = document.querySelector("#warmup-session-badge");
const summarySessionBadge = document.querySelector("#summary-session-badge");
const warmupReturningNote = document.querySelector("#warmup-returning-note");
const sessionStatusText = document.querySelector("#session-status-text");
const sessionTimer = document.querySelector("#session-timer");

let sessionId = null;
let recognition = null;
let lastAnswer = "";
let sessionDone = false;
let timerInterval = null;
let sessionStartTime = null;

const fitLabels = {
  mismatch: { text: "Career Navigation", cls: "session-type-navigate" },
  pivot: { text: "Career Pivot", cls: "session-type-pivot" },
  good: { text: "Interview Prep", cls: "session-type-prep" },
};

function showPhase(phase) {
  [phaseWarmup, phaseSession, phaseSummary].forEach((node) => {
    node.classList.add("hidden");
    node.classList.remove("reveal", "summary-enter", "phase-fade-out");
  });
  phase.classList.remove("hidden");
  window.requestAnimationFrame(() => phase.classList.add("reveal"));
}

function transitionToSummary(summaryHtml) {
  phaseSession.classList.add("phase-fade-out");
  window.setTimeout(() => {
    summaryCard.innerHTML = summaryHtml;
    phaseSession.classList.remove("phase-fade-out");
    showPhase(phaseSummary);
    phaseSummary.classList.add("summary-enter");
    setStatusText("Session complete");
    stopTimer();
  }, 240);
}

function setStatusText(text) {
  sessionStatusText.textContent = text;
}

function applySessionBadge(fitLevel) {
  const fitInfo = fitLabels[fitLevel] || fitLabels.good;
  [sessionTypeBar, warmupSessionBadge, summarySessionBadge].forEach((badge) => {
    if (!badge) return;
    badge.textContent = fitInfo.text;
    badge.className = `session-type-badge ${fitInfo.cls}`;
  });
  return fitInfo;
}

function formatTimer(elapsedMs) {
  const totalSeconds = Math.max(0, Math.floor(elapsedMs / 1000));
  const minutes = String(Math.floor(totalSeconds / 60)).padStart(2, "0");
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function startTimer() {
  if (timerInterval) return;
  sessionStartTime = Date.now();
  sessionTimer.textContent = "00:00";
  sessionTimer.classList.remove("hidden");
  timerInterval = window.setInterval(() => {
    sessionTimer.textContent = formatTimer(Date.now() - sessionStartTime);
  }, 1000);
}

function stopTimer() {
  if (timerInterval) {
    window.clearInterval(timerInterval);
    timerInterval = null;
  }
}

function setThinking(on) {
  thinkingBubble.classList.toggle("hidden", !on);
  questionBubble.classList.toggle("hidden", on);
  if (on) coachingBubble.classList.add("hidden");
  setStatusText(on ? "Jordan is thinking" : "Jordan is listening");
  if (on) setJordanState("thinking");
}

function setCoaching(text) {
  if (!text) {
    coachingBubble.classList.add("hidden");
    coachingBubble.textContent = "";
    return;
  }
  coachingBubble.textContent = text;
  coachingBubble.classList.remove("hidden");
  coachingBubble.classList.add("reveal");
}

function setQuestion(text) {
  questionEl.textContent = text;
  questionBubble.classList.remove("hidden");
  questionBubble.classList.add("reveal");
  thinkingBubble.classList.add("hidden");
  setStatusText("Jordan is speaking");
}

function setInputEnabled(on) {
  micButton.disabled = !on;
  submitButton.disabled = !on;
  answerInput.disabled = !on;
  if (on) {
    micButton.classList.remove("mic-disabled");
    setStatusText("Your turn");
  } else {
    micButton.classList.add("mic-disabled");
  }
}

function renderWarmup(data) {
  applySessionBadge(data.fit_level);
  const name = data.display_name ? escapeHtml(data.display_name) : "";
  const hasHistory = data.session_count > 0;
  const hasWeakness = data.known_weaknesses && data.known_weaknesses.length > 0;

  // Greeting — varied so Jordan never sounds like a recording
  const pick = (arr) => arr[Math.floor(Math.random() * arr.length)];

  let greetingText = "";
  if (name) {
    if (!hasHistory) {
      greetingText = pick([
        `${name}. First session. Let's find out exactly where you stand.`,
        `${name}. Haven't worked together yet. Let's change that.`,
        `${name}. First time? Good. Let's see what we're working with.`,
        `${name}. Fresh start. Tell me what you're going for.`,
      ]);
    } else if (data.readiness_score >= 8) {
      greetingText = pick([
        `${name}. You're at ${data.readiness_score.toFixed(1)}/10 — that's real. Let's keep going.`,
        `${name}. ${data.readiness_score.toFixed(1)}/10. You've put in the work. Let's finish it.`,
        `${name}. That ${data.readiness_score.toFixed(1)} didn't come from nowhere. Let's push higher.`,
      ]);
    } else if (hasWeakness) {
      greetingText = pick([
        `${name}. You're back. Last time ${data.known_weaknesses[0]} held you down — that's what we're fixing today.`,
        `${name}. Still got ${data.known_weaknesses[0]} on the list. Let's close it.`,
        `${name}. We know the gap — ${data.known_weaknesses[0]}. Let's work it.`,
      ]);
    } else {
      greetingText = pick([
        `${name}. Good to see you back. Let's pick up where we left off.`,
        `${name}. You came back. That means you're serious.`,
        `${name}. Back again. Good. Let's make this one count.`,
        `${name}. Welcome back. What are we working on today?`,
        `${name}. Ready when you are. Let's get into it.`,
      ]);
    }
  }
  const displayName = greetingText ? `<p class="warmup-greeting">${greetingText}</p>` : "";

  // Readiness section — specific, not generic
  const pushText = hasWeakness
    ? `${data.readiness_score.toFixed(1)}/10 last round. ${data.known_weaknesses[0]} is still the gap — let's close it.`
    : `${data.readiness_score.toFixed(1)}/10. Let's push higher this round.`;

  const readinessMarkup = hasHistory
    ? `
      <section class="warmup-readiness">
        <span class="warmup-readiness-label">Where you left off</span>
        <div class="warmup-readiness-row">
          <div class="warmup-readiness-score">${data.readiness_score.toFixed(1)}<span>/10</span></div>
          <p class="warmup-readiness-push">${pushText}</p>
        </div>
      </section>
    `
    : "";

  const sessionLine = hasHistory ? `Session ${data.session_count + 1}` : "First session";

  if (warmupReturningNote) {
    if (hasHistory && hasWeakness) {
      warmupReturningNote.textContent = `Jordan remembers: ${data.known_weaknesses[0]}.`;
    } else if (hasHistory) {
      warmupReturningNote.textContent = `Jordan remembers your last round.`;
    } else {
      warmupReturningNote.textContent = `Jordan has read your resume and the job post.`;
    }
  }

  warmupCard.innerHTML = `
    <div class="warmup-card-body">
      <div class="warmup-card-copy">
        ${displayName}
        <p class="warmup-session-line">${sessionLine}</p>
        <p class="warmup-text">${escapeHtml(data.warmup_text || data.context_summary || "")}</p>
      </div>
      ${readinessMarkup}
    </div>
  `;
}

async function loadSession() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode") || "track";
  const payload = mode === "job"
    ? { mode, job_id: Number(params.get("job_id")) }
    : { mode, track_id: Number(params.get("track_id") || 1) };

  const response = await fetchJson("/jordan/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  sessionId = data.session_id;

  applySessionBadge(data.fit_level);
  setStatusText("Ready when you are");

  const taglineEl = document.querySelector(".jordan-tagline");
  if (taglineEl) {
    if (data.fit_level === "mismatch") taglineEl.textContent = "Honest about fit. Focused on where you'll win.";
    else if (data.fit_level === "pivot") taglineEl.textContent = "Own your story. Bridge the gap.";
    else taglineEl.textContent = "Warm, direct, no weak answers allowed.";
  }

  renderWarmup(data);

  const btnLabels = {
    mismatch: "Start the conversation",
    pivot: "Start this session",
    good: "Start this session",
  };
  const btnLabel = data.session_count > 0
    ? `Start session ${data.session_count + 1}`
    : (btnLabels[data.fit_level] || "Start this session");
  startButton.querySelector(".btn-label").textContent = btnLabel;
  startButton.disabled = false;

  audioEl.src = data.audio_url;

  startButton.addEventListener("click", () => {
    showPhase(phaseSession);
    startTimer();
    setInputEnabled(false);
    setQuestion(data.question_text);

    const enableAfterAudio = () => setInputEnabled(true);
    audioEl.onended = enableAfterAudio;
    audioEl.onerror = enableAfterAudio;
    audioEl.play().catch(() => setInputEnabled(true));
  }, { once: true });
}

async function sendAnswer(answer) {
  if (!answer.trim() || sessionDone) return;
  lastAnswer = answer.trim();

  answerInput.value = "";
  retryButton.classList.add("hidden");
  setInputEnabled(false);
  setThinking(true);

  const response = await fetchJson("/jordan/session/respond", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer: lastAnswer }),
  });
  const data = await response.json();

  setCoaching(data.coaching);

  if (data.session_complete) {
    sessionDone = true;
    setQuestion(data.next_question_text);
    audioEl.src = data.audio_url;

    const showSummary = () => {
      const scoreDisplay = data.readiness_score
        ? `
          <section class="readiness-score-wrap">
            <span class="readiness-label">Readiness score</span>
            <span class="readiness-number">${data.readiness_score.toFixed(1)}<span class="readiness-max">/10</span></span>
          </section>
        `
        : "";
      transitionToSummary(scoreDisplay + formatSummary(data.summary || ""));
    };

    audioEl.onended = showSummary;
    audioEl.onerror = showSummary;
    audioEl.play().catch(showSummary);
    return;
  }

  setQuestion(data.next_question_text);
  audioEl.src = data.audio_url;

  const enableInput = () => {
    setInputEnabled(true);
    retryButton.classList.remove("hidden");
  };
  audioEl.onended = enableInput;
  audioEl.onerror = enableInput;
  audioEl.play().catch(enableInput);
}

function formatSummary(text) {
  if (!text) {
    return `<section class="summary-section"><h3>Takeaway</h3><p>Session complete. Review your answers and prep with real examples and metrics.</p></section>`;
  }

  const groups = [];
  let currentGroup = null;

  text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .forEach((line) => {
      let title = "Notes";
      let cls = "";

      if (line.startsWith("✅")) {
        title = "What landed";
        cls = "summary-win";
      } else if (line.startsWith("🔧")) {
        title = "What to sharpen";
        cls = "summary-fix";
      } else if (line.startsWith("💬")) {
        title = "What to memorize";
        cls = "summary-memorize";
      }

      if (!currentGroup || currentGroup.title !== title) {
        currentGroup = { title, lines: [] };
        groups.push(currentGroup);
      }

      currentGroup.lines.push(`<p class="${cls}">${line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")}</p>`);
    });

  return `
    ${groups.map((group) => `
      <section class="summary-section">
        <h3>${group.title}</h3>
        ${group.lines.join("")}
      </section>
    `).join("")}
  `;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function setupMic() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    micButton.querySelector(".mic-label").textContent = "Mic unavailable";
    micButton.classList.add("mic-disabled");
    return;
  }

  recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;

  recognition.onresult = (event) => {
    answerInput.value = event.results[0][0].transcript;
    micButton.classList.remove("mic-active");
    micButton.querySelector(".mic-label").textContent = "Hold to speak";
  };

  recognition.onerror = () => {
    micButton.classList.remove("mic-active");
    micButton.querySelector(".mic-label").textContent = "Hold to speak";
  };

  recognition.onend = () => {
    micButton.classList.remove("mic-active");
    micButton.querySelector(".mic-label").textContent = "Hold to speak";
  };

  micButton.addEventListener("click", () => {
    if (micButton.disabled) return;
    if (micButton.classList.contains("mic-active")) {
      recognition.stop();
      return;
    }
    micButton.classList.add("mic-active");
    micButton.querySelector(".mic-label").textContent = "Listening...";
    try {
      recognition.start();
    } catch (_) {}
  });
}

submitButton.addEventListener("click", () => sendAnswer(answerInput.value));

answerInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendAnswer(answerInput.value);
  }
});

retryButton.addEventListener("click", () => {
  answerInput.value = "";
  answerInput.focus();
  retryButton.classList.add("hidden");
});

restartButton.addEventListener("click", () => {
  sessionId = null;
  sessionDone = false;
  lastAnswer = "";
  stopTimer();
  sessionTimer.textContent = "Timer off";
  coachingBubble.classList.add("hidden");
  setStatusText("Preparing Jordan");
  sessionTypeBar.textContent = "Loading session";
  sessionTypeBar.className = "session-type-badge session-type-loading";
  if (warmupSessionBadge) {
    warmupSessionBadge.textContent = "Loading session";
    warmupSessionBadge.className = "session-type-badge session-type-loading";
  }
  if (summarySessionBadge) {
    summarySessionBadge.textContent = "Loading session";
    summarySessionBadge.className = "session-type-badge session-type-loading";
  }
  if (warmupReturningNote) {
    warmupReturningNote.textContent = "Jordan is getting the room ready.";
  }
  showPhase(phaseWarmup);
  startButton.disabled = true;
  startButton.querySelector(".btn-label").textContent = "Loading...";
  loadSession().catch(console.error);
});

const params = new URLSearchParams(window.location.search);
const hasContext = params.get("mode") === "job" ? !!params.get("job_id") : !!params.get("track_id");

// Tag the journey with this job_id so My Journey can greet you by company
if (params.get("job_id")) {
  sessionStorage.setItem("landed_last_job_id", params.get("job_id"));
}

async function bootstrap() {
  if (!requireAuth()) return;
  const user = await fetchCurrentUser();
  if (!user) {
    redirectToLogin();
    return;
  }

  renderAuthNav(user);
  setupMic();

  if (!hasContext && !params.get("mode")) {
    warmupCard.innerHTML = `<p class="warmup-text">Analyze a job first, then come back to prep. <a href="/" class="warmup-link">← Back to analyzer</a></p>`;
    startButton.remove();
    setStatusText("Waiting for context");
    return;
  }

  loadSession().catch((err) => {
    warmupCard.innerHTML = `<p class="warmup-text warmup-text-error">Could not connect to Jordan: ${escapeHtml(err.message)}</p>`;
    setStatusText("Connection failed");
  });
}

bootstrap();
