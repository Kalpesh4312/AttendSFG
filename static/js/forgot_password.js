(function () {
  let email = "";
  let resetToken = "";

  const stepEmail = document.getElementById("stepEmail");
  const stepOtp = document.getElementById("stepOtp");
  const stepReset = document.getElementById("stepReset");

  function goToStep(step) {
    [stepEmail, stepOtp, stepReset].forEach(s => s.classList.add("hidden"));
    step.classList.remove("hidden");
  }

  function showDevOtp(data) {
    const banner = document.getElementById("devOtpBanner");
    if (data.dev_otp) {
      banner.textContent = `Dev mode — no email server configured. Your code is: ${data.dev_otp}`;
      banner.classList.remove("hidden");
    } else {
      banner.classList.add("hidden");
    }
  }

  // ---- Step 1: request OTP ----------------------------------------------
  const emailForm = document.getElementById("emailForm");
  const emailAlertBox = document.getElementById("emailAlertBox");
  const submitEmailBtn = document.getElementById("submitEmailBtn");

  emailForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(emailAlertBox);
    email = document.getElementById("email").value.trim();

    submitEmailBtn.disabled = true;
    submitEmailBtn.innerHTML = `<span class="spinner"></span>`;
    try {
      const data = await Api.post("/api/auth/forgot-password/request-otp", { email });
      document.getElementById("otpEmailLabel").textContent = email;
      showDevOtp(data);
      goToStep(stepOtp);
      document.getElementById("otpInput").focus();
    } catch (err) {
      showAlert(emailAlertBox, err.message);
    } finally {
      submitEmailBtn.disabled = false;
      submitEmailBtn.textContent = "Send reset code";
    }
  });

  document.getElementById("backToEmailBtn").addEventListener("click", () => goToStep(stepEmail));

  // ---- Step 2: verify OTP -------------------------------------------------
  const otpForm = document.getElementById("otpForm");
  const otpAlertBox = document.getElementById("otpAlertBox");
  const submitOtpBtn = document.getElementById("submitOtpBtn");

  otpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(otpAlertBox);
    submitOtpBtn.disabled = true;
    submitOtpBtn.innerHTML = `<span class="spinner"></span>`;
    try {
      const data = await Api.post("/api/auth/forgot-password/verify-otp", {
        email,
        otp: document.getElementById("otpInput").value.trim(),
      });
      resetToken = data.reset_token;
      document.getElementById("resetEmailLabel").textContent = email;
      goToStep(stepReset);
    } catch (err) {
      showAlert(otpAlertBox, err.message);
    } finally {
      submitOtpBtn.disabled = false;
      submitOtpBtn.textContent = "Verify code";
    }
  });

  document.getElementById("resendOtpBtn").addEventListener("click", async function () {
    clearAlert(otpAlertBox);
    this.disabled = true;
    const original = this.textContent;
    this.textContent = "Sending...";
    try {
      const data = await Api.post("/api/auth/forgot-password/request-otp", { email });
      showDevOtp(data);
      showAlert(otpAlertBox, "A new code has been sent.", "success");
    } catch (err) {
      showAlert(otpAlertBox, err.message);
    } finally {
      this.disabled = false;
      this.textContent = original;
    }
  });

  // ---- Step 3: set new password -------------------------------------------
  const pwChecker = attachPasswordStrengthChecklist(
    document.getElementById("newPassword"),
    document.getElementById("pwChecklist")
  );

  const resetForm = document.getElementById("resetForm");
  const resetAlertBox = document.getElementById("resetAlertBox");
  const submitResetBtn = document.getElementById("submitResetBtn");

  resetForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(resetAlertBox);

    const newPassword = document.getElementById("newPassword").value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (!pwChecker.isValid()) {
      showAlert(resetAlertBox, "Your password doesn't meet all the requirements below yet.");
      return;
    }
    if (newPassword !== confirmPassword) {
      showAlert(resetAlertBox, "Passwords do not match.");
      return;
    }

    submitResetBtn.disabled = true;
    submitResetBtn.innerHTML = `<span class="spinner"></span>`;
    try {
      await Api.post("/api/auth/forgot-password/reset", {
        email,
        reset_token: resetToken,
        new_password: newPassword,
      });
      window.location.href = "/login?reset=success";
    } catch (err) {
      showAlert(resetAlertBox, err.message);
      submitResetBtn.disabled = false;
      submitResetBtn.textContent = "Reset password";
    }
  });
})();
