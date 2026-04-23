const stateEl = document.querySelector("#jordan-state");
const questionEl = document.querySelector("#current-question");
const audioEl = document.querySelector("#jordan-audio");
const answerEl = document.querySelector("#answer-text");
const coachingEl = document.querySelector("#coaching-copy");
const transcriptEl = document.querySelector("#transcript-log");
const micButton = document.querySelector("#mic-button");
const submitButton = document.querySelector("#submit-answer");

let sessionId = null;
let recognition = null;

function setJordanState(label, tone) {
  stateEl.textContent = label;
  stateEl.className = `jordan-state ${tone}`;
}

function appendTranscript(label, text) {
  transcriptEl.textContent += `${label}: ${text}\n\n`;
}

async function startSession() {
  const params = new URLSearchParams(window.location.search);
  const mode = params.get("mode") || "track";
  const payload = mode === "job"
    ? { mode, job_id: Number(params.get("job_id")) }
    : { mode, track_id: Number(params.get("track_id") || 1) };
  const response = await fetch("/jordan/session/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json();
  sessionId = data.session_id;
  questionEl.textContent = data.question_text;
  audioEl.src = data.audio_url;
  appendTranscript("Jordan", data.question_text);
  setJordanState("Jordan is speaking...", "speaking");
  audioEl.play().catch(() => {});
  audioEl.onended = () => setJordanState("Your turn.", "listening");
}

async function sendAnswer() {
  const answer = answerEl.value.trim();
  if (!answer) return;
  appendTranscript("You", answer);
  answerEl.value = "";
  setJordanState("Jordan is thinking...", "thinking");
  const response = await fetch("/jordan/session/respond", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, answer }),
  });
  const data = await response.json();
  coachingEl.textContent = data.coaching;
  questionEl.textContent = data.next_question_text;
  audioEl.src = data.audio_url;
  appendTranscript("Jordan", `${data.coaching}\n${data.next_question_text}`);
  setJordanState("Jordan is speaking...", "speaking");
  audioEl.play().catch(() => {});
  audioEl.onended = () => setJordanState(data.session_complete ? "Session complete." : "Your turn.", data.session_complete ? "thinking" : "listening");
}

function setupRecognition() {
  const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!Recognition) {
    micButton.disabled = true;
    micButton.textContent = "Mic unavailable";
    return;
  }
  recognition = new Recognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.onstart = () => setJordanState("Your turn.", "listening");
  recognition.onresult = (event) => {
    answerEl.value = event.results[0][0].transcript;
  };
  recognition.onerror = () => setJordanState("Your turn.", "listening");
}

micButton.addEventListener("click", () => recognition && recognition.start());
submitButton.addEventListener("click", sendAnswer);

setupRecognition();
startSession().catch((error) => {
  questionEl.textContent = `Jordan could not start: ${error.message}`;
  setJordanState("Jordan is thinking...", "thinking");
});
