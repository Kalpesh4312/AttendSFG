(function () {
  const user = Auth.requireRole("student");
  if (!user) return;

  const alertBox = document.getElementById("alertBox");

  function statusChip(status) {
    return status === "present"
      ? `<span class="chip chip-success"><span class="dot"></span>Present</span>`
      : `<span class="chip chip-danger"><span class="dot"></span>Absent</span>`;
  }

  async function load() {
    try {
      const data = await Api.get(`/api/student/subjects/${SUBJECT_ID}/attendance`);
      document.getElementById("backLink").href = `/student/classes/${data.class.id}`;
      document.getElementById("classNameLabel").textContent = `${data.class.name}${data.class.section ? " · " + data.class.section : ""}`;
      document.getElementById("subjectName").textContent = data.subject.name;
      document.getElementById("statPercent").textContent = `${data.attendance_percent}%`;
      document.getElementById("statPresent").textContent = data.present_count;
      document.getElementById("statTotal").textContent = data.total_sessions;

      const body = document.getElementById("historyBody");
      if (!data.history.length) {
        document.getElementById("emptyHistory").classList.remove("hidden");
        body.innerHTML = "";
      } else {
        document.getElementById("emptyHistory").classList.add("hidden");
        body.innerHTML = data.history.slice().reverse().map(h => `
          <tr><td>${formatDate(h.date)}</td><td>${statusChip(h.status)}</td></tr>
        `).join("");
      }
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  load();
})();
