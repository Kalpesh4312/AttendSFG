(function () {
  const user = Auth.requireAnyRole(["teacher", "admin"]);
  if (!user) return;

  const alertBox = document.getElementById("alertBox");
  let endTime = null;
  let refreshTimer = null;
  let countdownTimer = null;

  function renderRow(record) {
    return `<tr><td>${escapeHtml(record.student_name)}</td><td class="text-muted text-sm">${escapeHtml(record.enrollment_no || "")}</td><td class="text-sm text-muted">${formatDate(record.marked_at)}</td></tr>`;
  }

  function renderAbsentRow(student) {
    return `<tr><td>${escapeHtml(student.name)}</td><td class="text-muted text-sm">${escapeHtml(student.enrollment_no || "")}</td><td></td></tr>`;
  }

  async function load() {
    try {
      const data = await Api.get(`/api/teacher/sessions/${SESSION_ID}`);
      document.getElementById("backLink").href = `/teacher/subjects/${data.subject.id}`;
      document.getElementById("backLink").textContent = `← Back to ${data.subject.name}`;
      document.getElementById("sessionContext").textContent = `${data.class.name}${data.class.section ? " · " + data.class.section : ""} — ${data.subject.name}`;
      document.getElementById("tokenChars").textContent = data.session.token;
      endTime = new Date(data.session.end_time.replace(' ', 'T') + 'Z');;

      const chip = document.getElementById("sessionStatusChip");
      if (data.session.is_active) {
        chip.className = "chip chip-amber";
        chip.innerHTML = '<span class="dot"></span>Live';
        document.getElementById("endSessionBtn").classList.remove("hidden");
      } else {
        chip.className = "chip chip-muted";
        chip.textContent = "Ended";
        document.getElementById("endSessionBtn").classList.add("hidden");
      }

      document.getElementById("presentCount").textContent = data.present.length;
      document.getElementById("absentCount").textContent = data.absent.length;

      const presentBody = document.getElementById("presentBody");
      const emptyPresent = document.getElementById("emptyPresent");
      if (!data.present.length) {
        emptyPresent.classList.remove("hidden");
        presentBody.innerHTML = "";
      } else {
        emptyPresent.classList.add("hidden");
        presentBody.innerHTML = data.present.map(renderRow).join("");
      }
      document.getElementById("absentBody").innerHTML = data.absent.map(renderAbsentRow).join("");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  function updateCountdown() {
    const timerEl = document.getElementById("tokenTimer");
    
    if (!endTime) return;
    const diff = endTime.getTime() - Date.now();
    if (diff <= 0) {
      timerEl.textContent = "Session Ended";
      return;
    }
    const mins = Math.floor(diff / 60000);
    const secs = Math.floor((diff % 60000) / 1000);
    timerEl.textContent = `Expires in ${mins}:${secs.toString().padStart(2, "0")}`;
  }

  document.getElementById("endSessionBtn").addEventListener("click", async () => {
    if (!confirm("End this attendance session now?")) return;
    try {
      await Api.post(`/api/teacher/sessions/${SESSION_ID}/end`, {});
      load();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  load();
  refreshTimer = setInterval(load, 5000);
  countdownTimer = setInterval(updateCountdown, 1000);
})();
