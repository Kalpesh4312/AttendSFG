(function () {
  const user = Auth.requireRole("student");
  if (!user) return;

  const alertBox = document.getElementById("alertBox");

  function pctClass(pct) {
    if (pct >= 75) return "matrix-pct-good";
    if (pct >= 50) return "matrix-pct-warn";
    return "matrix-pct-bad";
  }

  async function loadOverview() {
    try {
      const data = await Api.get(`/api/student/classes/${CLASS_ID}/attendance-overview`);
      document.getElementById("overallPercent").textContent = `${data.overall_percent}%`;
      document.getElementById("overallPresent").textContent = data.overall_present;
      document.getElementById("overallTotal").textContent = data.overall_total;

      const body = document.getElementById("perSubjectBody");
      const empty = document.getElementById("emptyPerSubject");
      if (!data.per_subject.length) {
        empty.classList.remove("hidden");
        body.innerHTML = "";
        return;
      }
      empty.classList.add("hidden");
      body.innerHTML = data.per_subject.map((s) => `
        <tr>
          <td>${escapeHtml(s.subject_name)}</td>
          <td>${s.sessions_present} / ${s.total_sessions}</td>
          <td class="${pctClass(s.attendance_percent)}">${s.attendance_percent}%</td>
          <td><a href="/student/subjects/${s.subject_id}" class="btn btn-outline btn-sm">Details</a></td>
        </tr>
      `).join("");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  async function load() {
    try {
      const data = await Api.get(`/api/student/classes/${CLASS_ID}`);
      document.getElementById("className").textContent = data.class.name;
      document.getElementById("classSubtitle").textContent = data.class.section || "Class";

      const grid = document.getElementById("subjectsGrid");
      const empty = document.getElementById("emptySubjects");
      if (!data.subjects.length) {
        empty.classList.remove("hidden");
        grid.innerHTML = "";
        return;
      }
      empty.classList.add("hidden");
      grid.innerHTML = data.subjects.map((s) => `
        <a class="card-link" href="/student/subjects/${s.id}">
          <div class="h-card mb-8">${escapeHtml(s.name)}</div>
          <p class="text-sm">${s.teachers.length ? s.teachers.map(t => escapeHtml(t.name)).join(", ") : "No teacher assigned yet"}</p>
        </a>
      `).join("");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  load();
  loadOverview();
})();
