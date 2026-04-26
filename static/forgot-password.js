const forgotPasswordForm = document.querySelector("#forgot-password-form");
const forgotPasswordError = document.querySelector("#forgot-password-error");
const forgotPasswordSuccess = document.querySelector("#forgot-password-success");

function hideForgotPasswordMessages() {
  forgotPasswordError.classList.add("hidden");
  forgotPasswordSuccess.classList.add("hidden");
}

function showForgotPasswordError(message) {
  forgotPasswordError.textContent = message;
  forgotPasswordError.classList.remove("hidden");
}

function showForgotPasswordSuccess(message) {
  forgotPasswordSuccess.textContent = message;
  forgotPasswordSuccess.classList.remove("hidden");
}

forgotPasswordForm?.addEventListener("submit", async (event) => {
  event.preventDefault();
  hideForgotPasswordMessages();

  const submitButton = forgotPasswordForm.querySelector('button[type="submit"]');
  submitButton?.setAttribute("disabled", "disabled");

  try {
    const form = new FormData(forgotPasswordForm);
    const response = await fetch("/auth/forgot-password", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: form.get("email") }),
    });

    if (!response.ok) {
      showForgotPasswordError("Check your email. If it exists in Landed, a reset link is on its way.");
      return;
    }

    showForgotPasswordSuccess("Check your email. Link expires in 1 hour.");
    forgotPasswordForm.reset();
  } catch (_) {
    showForgotPasswordError("Check your email. If it exists in Landed, a reset link is on its way.");
  } finally {
    submitButton?.removeAttribute("disabled");
  }
});
