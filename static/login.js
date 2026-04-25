const loginForm = document.querySelector("#auth-form");
const loginError = document.querySelector("#auth-error");

function showLoginError(message) {
  loginError.textContent = message;
  loginError.classList.remove("hidden");
}

loginForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  loginError.classList.add("hidden");

  const form = new FormData(loginForm);
  const response = await fetch("/auth/login", {
    method: "POST",
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

  window.LandedAuth.setToken(payload.access_token);
  if (payload.user?.resume) {
    localStorage.setItem(window.LandedAuth.RESUME_KEY, payload.user.resume);
  }

  try {
    await window.LandedAuth.fetchCurrentUser();
  } catch (_) {}

  const next = new URLSearchParams(window.location.search).get("next") || "/";
  window.location.href = next;
});
