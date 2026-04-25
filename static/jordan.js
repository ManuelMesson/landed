const { fetchCurrentUser, fetchJson, redirectToLogin, renderAuthNav, requireAuth } = window.LandedAuth;
const phaseWarmup  = document.querySelector("#phase-warmup");
const phaseSession = document.querySelector("#phase-session");
const phaseSummary = document.querySelector("#phase-summary");

const startButton    = document.querySelector("#start-button");
const warmupCard     = document.querySelector("#warmup-card");
const questionEl     = document.querySelector("#current-question");
const questionBubble = document.querySelector("#question-bubble");
const coachingBubble = document.querySelector("#coaching-bubble");
const thinkingBubble = document.querySelector("#jordan-thinking");
const userMessages   = document.querySelector("#user-messages");
const audioEl        = document.querySelector("#jordan-audio");
const micButton      = document.querySelector("#mic-button");
const submitButton   = document.querySelector("#submit-answer");
const answerInput    = document.querySelector("#answer-text");
const retryButton    = document.querySelector("#retry-button");
const restartButton  = document.querySelector("#restart-button");
const summaryCard    = document.querySelector("#summary-card");

let sessionId    = null;
let recognition  = null;
let lastAnswer   = "";
let sessionDone  = false;

// ── Phase transitions ──

function showPhase(phase) {
  [phaseWarmup, phaseSession, phaseSummary].forEach(p => p.classList.add("hidden"));
  phase.classList.remove("hidden");
  phase.classList.add("reveal");
}

// ── User message bubbles ──

function appendUserBubble(text) {
  const wrap = document.createElement("div");
  wrap.className = "user-bubble-wrap reveal";
  const bubble = document.createElement("div");
  bubble.className = "bubble user-bubble";
  bubble.textContent = text;
  wrap.appendChild(bubble);
  userMessages.appendChild(wrap);
  wrap.scrollIntoView({ behavior: "smooth", block: "end" });
}

// ── Jordan state ──

function setThinking(on) {
  thinkingBubble.classList.toggle("hidden", !on);
  questionBubble.classList.toggle("hidden", on);
  coachingBubble.classList.add("hidden");
}

function setCoaching(text) {
  if (!text) { coachingBubble.classList.add("hidden"); return; }
  coachingBubble.textContent = text;
  coachingBubble.classList.remove("hidden");
  coachingBubble.classList.add("reveal");
}

function setQuestion(text) {
  questionEl.textContent = text;
  questionBubble.classList.remove("hidden");
  questionBubble.classList.add("reveal");
  thinkingBubble.classList.add("hidden");
}

function setInputEnabled(on) {
  micButton.disabled = !on;
  submitButton.disabled = !on;
  answerInput.disabled = !on;
  if (on) {
    micButton.classList.remove("mic-disabled");
  } else {
    micButton.classList.add("mic-disabled");
  }
}

// ── Load session ──

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

  // Session type badge
  const fitLabels = {
    mismatch: { text: "Career navigation", cls: "session-type-navigate" },
    pivot:    { text: "Career pivot",      cls: "session-type-pivot" },
    good:     { text: "Interview prep",    cls: "session-type-prep" },
  };
  const fitInfo = fitLabels[data.fit_level] || fitLabels.good;
  const sessionTypeBadge = `<span class="session-type-badge ${fitInfo.cls}">${fitInfo.text}</span>`;

  // Tagline adapts to session type
  const taglineEl = document.querySelector(".jordan-tagline");
  if (taglineEl) {
    if (data.fit_level === "mismatch") taglineEl.textContent = "Honest about fit. Focused on where you'll win.";
    else if (data.fit_level === "pivot") taglineEl.textContent = "Own your story. Bridge the gap.";
    else taglineEl.textContent = "Warm, direct, no weak answers allowed.";
  }

  // Score history — show coaching focus (not raw weakness label)
  let scoreHtml;
  if (data.session_count > 0) {
    const focusText = data.known_weaknesses.length
      ? `Focus this session: <em>${data.known_weaknesses[0]}</em>`
      : "";
    scoreHtml = `<div class="score-history">${sessionTypeBadge} Session ${data.session_count + 1} · Readiness: <strong>${data.readiness_score.toFixed(1)}/10</strong>${focusText ? ` · ${focusText}` : ""}</div>`;
  } else {
    scoreHtml = `<div class="score-history first-session">${sessionTypeBadge} First session — establishing your baseline.</div>`;
  }

  warmupCard.innerHTML = `${scoreHtml}<p class="warmup-text">${data.warmup_text || data.context_summary}</p>`;

  const btnLabels = { mismatch: "Let's talk.", pivot: "I'm ready. Let's go.", good: "I'm ready. Let's go." };
  const btnLabel = data.session_count > 0
    ? (data.fit_level === "mismatch" ? "Session 2. Let's talk." : `Session ${data.session_count + 1}. Let's go.`)
    : (btnLabels[data.fit_level] || "I'm ready. Let's go.");
  startButton.querySelector(".btn-label").textContent = btnLabel;
  startButton.disabled = false;

  // Pre-load first question audio
  audioEl.src = data.audio_url;

  startButton.addEventListener("click", () => {
    showPhase(phaseSession);
    setInputEnabled(false);
    setQuestion(data.question_text);
    // Always enable input after audio — fallback if audio fails or can't play
    const enableAfterAudio = () => setInputEnabled(true);
    audioEl.onended = enableAfterAudio;
    audioEl.onerror = enableAfterAudio;
    audioEl.play().catch(() => setInputEnabled(true));
  }, { once: true });
}

// ── Send answer ──

async function sendAnswer(answer) {
  if (!answer.trim() || sessionDone) return;
  lastAnswer = answer.trim();

  appendUserBubble(lastAnswer);
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
        ? `<div class="readiness-score-wrap"><span class="readiness-label">Readiness score</span><span class="readiness-number">${data.readiness_score.toFixed(1)}<span class="readiness-max">/10</span></span></div>`
        : "";
      summaryCard.innerHTML = scoreDisplay + formatSummary(data.summary || "");
      showPhase(phaseSummary);
    };
    audioEl.onended = showSummary;
    audioEl.onerror = showSummary;
    audioEl.play().catch(showSummary);
  } else {
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
}

function formatSummary(text) {
  if (!text) return "<p>Session complete. Review your answers and prep with real examples and metrics.</p>";
  return text
    .split("\n")
    .map(line => line.trim())
    .filter(Boolean)
    .map(line => {
      // Render **bold** as <strong>
      line = line.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
      // Style the emoji section headers
      if (line.startsWith("✅")) return `<p class="summary-win">${line}</p>`;
      if (line.startsWith("🔧")) return `<p class="summary-fix">${line}</p>`;
      if (line.startsWith("💬")) return `<p class="summary-memorize">${line}</p>`;
      return `<p>${line}</p>`;
    })
    .join("");
}

// ── Mic ──

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
    const transcript = event.results[0][0].transcript;
    answerInput.value = transcript;
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
    } else {
      micButton.classList.add("mic-active");
      micButton.querySelector(".mic-label").textContent = "Listening...";
      try { recognition.start(); } catch (_) {}
    }
  });
}

// ── Event listeners ──

submitButton.addEventListener("click", () => sendAnswer(answerInput.value));

answerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
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
  userMessages.innerHTML = "";
  coachingBubble.classList.add("hidden");
  showPhase(phaseWarmup);
  startButton.disabled = true;
  startButton.querySelector(".btn-label").textContent = "Loading...";
  loadSession().catch(console.error);
});

// ── Boot ──

const _params = new URLSearchParams(window.location.search);
const _hasContext = _params.get("mode") === "job" ? !!_params.get("job_id") : !!_params.get("track_id");

async function bootstrap() {
  if (!requireAuth()) return;
  const user = await fetchCurrentUser();
  if (!user) {
    redirectToLogin();
    return;
  }
  renderAuthNav(user);
  setupMic();

  if (!_hasContext && !_params.get("mode")) {
    warmupCard.innerHTML = `<p class="warmup-text">Analyze a job first, then come back to prep. <a href="/" style="color:var(--accent);text-decoration:none">← Back to analyzer</a></p>`;
    startButton.remove();
    return;
  }

  loadSession().catch((err) => {
    warmupCard.innerHTML = `<p class="warmup-text" style="color:var(--red)">Could not connect to Jordan: ${err.message}</p>`;
  });
}

bootstrap();
