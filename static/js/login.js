async function verifyExistingSession() {
  const token = Auth.getToken();
  if (!token) return false;
  try {
    // Deliberately a raw fetch (not the shared Api helper) so a bad token
    // here doesn't trigger another redirect — we handle it locally.
    const res = await fetch("/api/auth/me", { headers: { Authorization: `Bearer ${token}` } });
    return res.ok;
  } catch (err) {
    return false;
  }
}

(async function () {
  const alertBox = document.getElementById("alertBox");

  if (Auth.isLoggedIn()) {
    const valid = await verifyExistingSession();
    if (valid) {
      const user = Auth.getUser();
      window.location.href = dashboardUrlForRole(user.role);
      return;
    }
    // Token existed but the server doesn't accept it (expired/invalid/
    // deleted account) — clean it up quietly instead of bouncing through
    // the dashboard and back, which is confusing.
    Auth.clearSession();
  }

  const form = document.getElementById("loginForm");
  const submitBtn = document.getElementById("submitBtn");

  const params = new URLSearchParams(window.location.search);
  if (params.get("reason") === "session_expired") {
    const detail = params.get("detail");
    showAlert(alertBox, detail ? `Your session expired: ${detail}` : "Your session expired. Please log in again.", "info");
  } else if (params.get("reset") === "success") {
    showAlert(alertBox, "Password reset successfully. Log in with your new password.", "success");
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    submitBtn.disabled = true;
    submitBtn.innerHTML = `<span class="spinner"></span>`;

    const email = document.getElementById("email").value.trim();
    const password = document.getElementById("password").value;

    try {
      const data = await Api.post("/api/auth/login", { email, password });
      Auth.setSession(data.token, data.user);
      window.location.href = dashboardUrlForRole(data.user.role);
    } catch (err) {
      showAlert(alertBox, err.message);
      submitBtn.disabled = false;
      submitBtn.textContent = "Log in";
    }
  });
})();
