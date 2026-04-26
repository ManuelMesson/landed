const resetPasswordForm = document.querySelector("#reset-password-form");
const resetPasswordError = document.querySelector("#reset-password-error");
const resetPasswordStatus = document.querySelector("#reset-password-status");
const resetPasswordInvalid = document.querySelector("#reset-password-invalid");

const resetToken = new URLSearchParams(window.location.search).get("token") || "";

function showExpiredState() {
  resetPasswordStatus.textContent = "";
  resetPasswordForm.classList.add("hidden");
  resetPasswordInvalid.classList.remove("hidden");
}

function showResetPasswordError(message) {
  resetPasswordError.textContent = message;
  resetPasswordError.classList.remove("hidden");
}

async function verifyResetToken() {
  if (!resetToken) {
    showExpiredState();
    return;
  }

  try {
    const response = await fetch(`/auth/reset-password/verify?token=${encodeURIComponent(resetToken)}`, {
      credentials: "include",
    });
    if (!response.ok) {
      showExpiredState();
      return;
    }

    resetPasswordStatus.textContent = "Your link is valid. Set a new password below.";
    resetPasswordForm.classList.remove("hidden");
  } catch (_) {
    showExpiredState();
  }
}

resetPasswordForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetPasswordError.classList.add("hidden");

  const submitButton = resetPasswordForm.querySelector('button[type="submit"]');
  submitButton?.setAttribute("disabled", "disabled");

  try {
    const form = new FormData(resetPasswordForm);
    const response = await fetch("/auth/reset-password", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token: resetToken,
        password: form.get("password"),
      }),
    });

    const payload = await response.json();
    if (!response.ok) {
      showResetPasswordError(payload.detail || "This link has expired. Request a new one.");
      if (response.status === 400) {
        showExpiredState();
      }
      return;
    }

    window.location.href = "/login?message=password-reset";
  } catch (_) {
    showResetPasswordError("Could not update password.");
  } finally {
    submitButton?.removeAttribute("disabled");
  }
});

verifyResetToken();
