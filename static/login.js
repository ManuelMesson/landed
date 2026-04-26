// Uses auth.js globals directly: RESUME_KEY, fetchCurrentUser, setSessionFlag

const loginForm = document.querySelector("#auth-form");
const loginError = document.querySelector("#auth-error");
const loginToast = document.querySelector("#auth-toast");

function showLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

const loginMessage = new URLSearchParams(window.location.search).get("message");
if (loginMessage === "password-reset" && loginToast) {
  loginToast.textContent = "Password updated. Sign in.";
  loginToast.classList.remove("hidden");
}

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.classList.add("hidden");

  const form = new FormData(loginForm);
  const response = await fetch("/auth/login", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: form.get("email"),
      password: form.get("password"),
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    showLoginError(payload.detail || "Could not sign in.");
    return;
  }

  setSessionFlag();
  if (payload.user?.resume) {
    localStorage.setItem(RESUME_KEY, payload.user.resume);
  }

  try {
    await fetchCurrentUser();
  } catch (_) {}

  const next = new URLSearchParams(window.location.search).get("next") || "/";
  window.location.href = next;
});
