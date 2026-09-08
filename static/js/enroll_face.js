(function () {
  const user = Auth.requireRole("student");
  if (!user) return;

  const video = document.getElementById("video");
  const scanWrap = document.getElementById("scanWrap");
  const scanStatus = document.getElementById("scanStatus");
  const startBtn = document.getElementById("startBtn");
  const captureBtn = document.getElementById("captureBtn");
  const alertBox = document.getElementById("alertBox");

  let stream = null;

  startBtn.addEventListener("click", async () => {
    clearAlert(alertBox);
    startBtn.disabled = true;
    startBtn.innerHTML = `<span class="spinner spinner-dark"></span> Loading model…`;
    try {
      await FaceEngine.loadModels();
      stream = await FaceEngine.startCamera(video);
      scanStatus.textContent = "Position your face in the frame";
      scanWrap.classList.add("state-scanning");
      captureBtn.disabled = false;
      startBtn.classList.add("hidden");
    } catch (err) {
      showAlert(alertBox, err.message || "Could not access the camera.");
      startBtn.disabled = false;
      startBtn.textContent = "Start camera";
    }
  });

  captureBtn.addEventListener("click", async () => {
    clearAlert(alertBox);
    captureBtn.disabled = true;
    captureBtn.innerHTML = `<span class="spinner"></span> Scanning…`;
    try {
      const descriptor = await FaceEngine.captureDescriptor(video);
      if (!descriptor) {
        showAlert(alertBox, "No face detected. Center your face in the frame and try again.");
        captureBtn.disabled = false;
        captureBtn.textContent = "Capture & save";
        return;
      }
      await Api.post("/api/auth/face-enroll", { descriptor });
      scanWrap.classList.remove("state-scanning");
      scanWrap.classList.add("state-match");
      scanStatus.textContent = "Face enrolled successfully ✓";
      captureBtn.textContent = "Enrolled";
      FaceEngine.stopCamera(stream);
      setTimeout(() => { window.location.href = "/student/dashboard"; }, 1200);
    } catch (err) {
      showAlert(alertBox, err.message);
      captureBtn.disabled = false;
      captureBtn.textContent = "Capture & save";
    }
  });
})();
