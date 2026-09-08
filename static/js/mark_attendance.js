(function () {
  const user = Auth.requireRole("student");
  if (!user) return;

  const video = document.getElementById("video");
  const scanWrap = document.getElementById("scanWrap");
  const scanStatus = document.getElementById("scanStatus");
  const verifyBtn = document.getElementById("verifyBtn");
  const tokenInput = document.getElementById("tokenInput");
  const alertBox = document.getElementById("alertBox");

  const checkToken = document.getElementById("checkToken");
  const checkFace = document.getElementById("checkFace");
  const checkGeo = document.getElementById("checkGeo");
  const backToDashboardBtn = document.getElementById("backToDashboardBtn");

  backToDashboardBtn.addEventListener("click", () => {
    window.location.href = "/student/dashboard";
  });

  function setCheck(el, state) {
    // state: pending | active | pass | fail
    const chip = el.querySelector(".chip");
    chip.className = "chip " + ({
      pending: "chip-muted", active: "chip-amber", pass: "chip-success", fail: "chip-danger",
    })[state];
  }

  verifyBtn.addEventListener("click", async () => {
    clearAlert(alertBox);
    const token = tokenInput.value.trim().toUpperCase();
    if (!token) {
      showAlert(alertBox, "Enter the session token displayed by your teacher.");
      return;
    }
    setCheck(checkToken, "active");
    setCheck(checkFace, "pending");
    setCheck(checkGeo, "pending");

    verifyBtn.disabled = true;
    verifyBtn.innerHTML = `<span class="spinner"></span> Verifying…`;
    scanWrap.classList.add("state-scanning");
    scanWrap.classList.remove("state-match", "state-fail");

    let stream = null;
    try {
      // Step 1 (visual only — real validation happens server-side): token present.
      setCheck(checkToken, "pass");

      // Step 2: face capture
      scanStatus.textContent = "Loading camera & AI model…";
      setCheck(checkFace, "active");
      await FaceEngine.loadModels();
      stream = await FaceEngine.startCamera(video);
      await new Promise((r) => setTimeout(r, 600)); // let camera settle
      scanStatus.textContent = "Scanning your face…";
      const descriptor = await FaceEngine.captureDescriptor(video);
      if (!descriptor) {
        setCheck(checkFace, "fail");
        scanWrap.classList.remove("state-scanning");
        scanWrap.classList.add("state-fail");
        scanStatus.textContent = "No face detected — try again";
        showAlert(alertBox, "No face detected. Center your face in the frame and try again.");
        FaceEngine.stopCamera(stream);
        resetButton();
        return;
      }

      // Step 3: geolocation
      scanStatus.textContent = "Checking your location…";
      setCheck(checkGeo, "active");
      const pos = await getCurrentPosition();

      const result = await Api.post("/api/attendance/mark", {
        token,
        descriptor,
        latitude: pos.latitude,
        longitude: pos.longitude,
      });

      setCheck(checkFace, "pass");
      setCheck(checkGeo, "pass");
      scanWrap.classList.remove("state-scanning");
      scanWrap.classList.add("state-match");
      scanStatus.textContent = "Attendance marked ✓";
      showAlert(alertBox, `Attendance marked for ${result.subject.name} (${result.class.name}).`, "success");
      verifyBtn.textContent = "Done";
      verifyBtn.classList.add("hidden");
      backToDashboardBtn.classList.remove("hidden");
      FaceEngine.stopCamera(stream);
    } catch (err) {
      scanWrap.classList.remove("state-scanning");
      scanWrap.classList.add("state-fail");
      const reasonCode = err.data && err.data.reason_code;
      if (reasonCode === "FACE_MISMATCH") setCheck(checkFace, "fail");
      else if (reasonCode === "OUT_OF_RANGE") { setCheck(checkFace, "pass"); setCheck(checkGeo, "fail"); }
      else if (reasonCode === "TOKEN_EXPIRED") setCheck(checkToken, "fail");
      scanStatus.textContent = "Attendance not marked";
      showAlert(alertBox, `${err.message} You're still logged in — try again, or head back to your dashboard.`);
      FaceEngine.stopCamera(stream);
      resetButton();
    }
  });

  function resetButton() {
    verifyBtn.disabled = false;
    verifyBtn.textContent = "Try again";
    backToDashboardBtn.classList.remove("hidden");
  }
})();
