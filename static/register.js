// Uses auth.js globals directly: fetchCurrentUser, setSessionFlag

const registerForm = document.querySelector("#auth-form");
const registerError = document.querySelector("#auth-error");

function showRegisterError(message) {
  registerError.textContent = message;
  registerError.classList.remove("hidden");
}

registerForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  registerError.classList.add("hidden");

  const form = new FormData(registerForm);
  const response = await fetch("/auth/register", {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      name: form.get("name"),
      email: form.get("email"),
      password: form.get("password"),
    }),
  });

  const payload = await response.json();
  if (!response.ok) {
    showRegisterError(payload.detail || "Could not create account.");
    return;
  }

  setSessionFlag();
  try {
    await fetchCurrentUser();
  } catch (_) {}
  const next = new URLSearchParams(window.location.search).get("next") || "/";
  window.location.href = next;
});
