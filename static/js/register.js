(function () {
  if (Auth.isLoggedIn()) {
    const user = Auth.getUser();
    window.location.href = dashboardUrlForRole ? dashboardUrlForRole(user.role) : (user.role === "teacher" ? "/teacher/dashboard" : "/student/dashboard");
    return;
  }

  // ---- Step 1: role toggle -------------------------------------------
  const roleInput = document.getElementById("role");
  const studentBtn = document.getElementById("roleStudentBtn");
  const teacherBtn = document.getElementById("roleTeacherBtn");
  const enrollmentField = document.getElementById("enrollmentField");

  function setRole(role) {
    roleInput.value = role;
    studentBtn.classList.toggle("active", role === "student");
    teacherBtn.classList.toggle("active", role === "teacher");
    enrollmentField.classList.toggle("hidden", role !== "student");
  }
  studentBtn.addEventListener("click", () => setRole("student"));
  teacherBtn.addEventListener("click", () => setRole("teacher"));

  // ---- Live password strength checklist -------------------------------
  const passwordInput = document.getElementById("password");
  const pwChecker = attachPasswordStrengthChecklist(passwordInput, document.getElementById("pwChecklist"));

  // ---- Step navigation --------------------------------------------------
  const stepDetails = document.getElementById("stepDetails");
  const stepOtp = document.getElementById("stepOtp");
  let registeredEmail = "";

  function showOtpStep(email) {
    registeredEmail = email;
    document.getElementById("otpEmailLabel").textContent = email;
    stepDetails.classList.add("hidden");
    stepOtp.classList.remove("hidden");
    document.getElementById("otpInput").focus();
  }

  function showDetailsStep() {
    stepOtp.classList.add("hidden");
    stepDetails.classList.remove("hidden");
  }

  document.getElementById("backToDetailsBtn").addEventListener("click", showDetailsStep);

  // ---- Step 1 submit: request OTP ---------------------------------------
  const detailsForm = document.getElementById("detailsForm");
  const alertBox = document.getElementById("alertBox");
  const submitDetailsBtn = document.getElementById("submitDetailsBtn");

  detailsForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);

    const password = passwordInput.value;
    const confirmPassword = document.getElementById("confirmPassword").value;

    if (!pwChecker.isValid()) {
      showAlert(alertBox, "Your password doesn't meet all the requirements below yet.");
      return;
    }
    if (password !== confirmPassword) {
      showAlert(alertBox, "Passwords do not match.");
      return;
    }

    const payload = {
      name: document.getElementById("name").value.trim(),
      email: document.getElementById("email").value.trim(),
      password,
      role: roleInput.value,
      enrollment_no: document.getElementById("enrollment_no").value.trim(),
    };

    submitDetailsBtn.disabled = true;
    submitDetailsBtn.innerHTML = `<span class="spinner"></span>`;
    try {
      const data = await Api.post("/api/auth/register/request-otp", payload);
      showOtpStep(payload.email);

      const devBanner = document.getElementById("devOtpBanner");
      if (data.dev_otp) {
        devBanner.textContent = `Dev mode — no email server configured. Your code is: ${data.dev_otp}`;
        devBanner.classList.remove("hidden");
      } else {
        devBanner.classList.add("hidden");
      }
    } catch (err) {
      showAlert(alertBox, err.message);
    } finally {
      submitDetailsBtn.disabled = false;
      submitDetailsBtn.textContent = "Send verification code";
    }
  });

  // ---- Step 2 submit: verify OTP -----------------------------------------
  const otpForm = document.getElementById("otpForm");
  const otpAlertBox = document.getElementById("otpAlertBox");
  const submitOtpBtn = document.getElementById("submitOtpBtn");

  otpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(otpAlertBox);
    submitOtpBtn.disabled = true;
    submitOtpBtn.innerHTML = `<span class="spinner"></span>`;

    try {
      const data = await Api.post("/api/auth/register/verify-otp", {
        email: registeredEmail,
        otp: document.getElementById("otpInput").value.trim(),
      });
      Auth.setSession(data.token, data.user);
      if (data.user.role === "student") {
        window.location.href = "/student/enroll-face";
      } else {
        window.location.href = "/teacher/dashboard";
      }
    } catch (err) {
      showAlert(otpAlertBox, err.message);
      submitOtpBtn.disabled = false;
      submitOtpBtn.textContent = "Verify & create account";
    }
  });

  // ---- Resend OTP ---------------------------------------------------------
  const resendBtn = document.getElementById("resendOtpBtn");
  resendBtn.addEventListener("click", async () => {
    clearAlert(otpAlertBox);
    resendBtn.disabled = true;
    const originalText = resendBtn.textContent;
    resendBtn.textContent = "Sending...";
    try {
      const data = await Api.post("/api/auth/register/resend-otp", { email: registeredEmail });
      const devBanner = document.getElementById("devOtpBanner");
      if (data.dev_otp) {
        devBanner.textContent = `Dev mode — no email server configured. Your code is: ${data.dev_otp}`;
        devBanner.classList.remove("hidden");
      }
      showAlert(otpAlertBox, "A new code has been sent.", "success");
    } catch (err) {
      showAlert(otpAlertBox, err.message);
    } finally {
      resendBtn.disabled = false;
      resendBtn.textContent = originalText;
    }
  });
})();
