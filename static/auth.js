const SESSION_FLAG = "landed_has_session";
const RESUME_KEY = "landed_user_resume";

function isLoggedIn() {
  return !!localStorage.getItem(SESSION_FLAG);
}

function setSessionFlag() {
  localStorage.setItem(SESSION_FLAG, "1");
}

function clearSessionFlag() {
  localStorage.removeItem(SESSION_FLAG);
}

async function clearAuth() {
  clearSessionFlag();
  localStorage.removeItem(RESUME_KEY);
  localStorage.removeItem("landed_user_email");
  try {
    await fetch("/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch (_) {}
}

function getAuthHeaders(headers = {}) {
  return headers;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    credentials: "include",
    headers: getAuthHeaders(options.headers || {}),
  });
  return response;
}

async function fetchCurrentUser() {
  if (!isLoggedIn()) return null;
  const response = await fetchJson("/auth/me");
  if (response.status === 401) {
    await clearAuth();
    return null;
  }
  if (!response.ok) {
    throw new Error("Failed to fetch current user");
  }
  const user = await response.json();
  setSessionFlag();
  localStorage.setItem("landed_user_email", user.email);
  if (user.resume && user.resume.trim()) {
    localStorage.setItem(RESUME_KEY, user.resume);
  }
  window.dispatchEvent(new CustomEvent("auth:ready", { detail: { user } }));
  return user;
}

function redirectToLogin() {
  const next = encodeURIComponent(window.location.pathname + window.location.search);
  window.location.href = `/login?next=${next}`;
}

function requireAuth() {
  if (!isLoggedIn()) {
    redirectToLogin();
    return false;
  }
  return true;
}

function renderAuthNav(user = null) {
  const slot = document.querySelector("[data-auth-slot]");
  if (!slot) return;

  if (user) {
    const name = user.display_name || user.email.split("@")[0].replace(/[._\-0-9].*/, "");
    const greeting = name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
    slot.innerHTML = `
      <span class="auth-greeting">Hey, ${greeting}</span>
      <a href="#" class="nav-pill nav-pill-logout" data-logout-link>Log out</a>
    `;
    slot.querySelector("[data-logout-link]")?.addEventListener("click", async (event) => {
      event.preventDefault();
      await clearAuth();
      window.location.href = "/login";
    });
    return;
  }

  slot.innerHTML = `<a href="/login" class="nav-pill">Sign in</a>`;
}

window.LandedAuth = {
  SESSION_FLAG,
  RESUME_KEY,
  clearAuth,
  clearSessionFlag,
  fetchCurrentUser,
  fetchJson,
  getAuthHeaders,
  isLoggedIn,
  redirectToLogin,
  renderAuthNav,
  requireAuth,
  setSessionFlag,
};
