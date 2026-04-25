const TOKEN_KEY = "landed_jwt";
const RESUME_KEY = "landed_user_resume";

function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

function isLoggedIn() {
  return !!getToken();
}

function setToken(token) {
  if (token) {
    localStorage.setItem(TOKEN_KEY, token);
  }
}

function clearAuth() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(RESUME_KEY);
  localStorage.removeItem("landed_user_email");
}

function getAuthHeaders(headers = {}) {
  const token = getToken();
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: getAuthHeaders(options.headers || {}),
  });
  return response;
}

async function fetchCurrentUser() {
  if (!isLoggedIn()) return null;
  const response = await fetchJson("/auth/me");
  if (response.status === 401) {
    clearAuth();
    return null;
  }
  if (!response.ok) {
    throw new Error("Failed to fetch current user");
  }
  const user = await response.json();
  localStorage.setItem("landed_user_email", user.email);
  if (user.resume && user.resume.trim()) {
    localStorage.setItem(RESUME_KEY, user.resume);
  }
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
    const localPart = user.email.split("@")[0];
    const firstName = localPart.split(/[._\-0-9]/)[0];
    const displayName = firstName.charAt(0).toUpperCase() + firstName.slice(1).toLowerCase();
    slot.innerHTML = `
      <span class="auth-greeting">Hey, ${displayName}</span>
      <a href="#" class="nav-pill nav-pill-logout" data-logout-link>Log out</a>
    `;
    slot.querySelector("[data-logout-link]")?.addEventListener("click", (event) => {
      event.preventDefault();
      clearAuth();
      window.location.href = "/login";
    });
    return;
  }

  slot.innerHTML = `<a href="/login" class="nav-pill">Sign in</a>`;
}

window.LandedAuth = {
  RESUME_KEY,
  clearAuth,
  fetchCurrentUser,
  fetchJson,
  getAuthHeaders,
  getToken,
  isLoggedIn,
  redirectToLogin,
  renderAuthNav,
  requireAuth,
  setToken,
};
