(function () {
  const user = Auth.requireAnyRole(["teacher", "admin"]);
  if (!user) return;

  const alertBox = document.getElementById("alertBox");
  let currentClassId = null;
  let canManageClass = false;

  // --- Tabs -------------------------------------------------------------
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
      if (btn.dataset.tab === "report") loadReport();
    });
  });

  function statusChip(session) {
    if (session.is_active) return '<span class="chip chip-amber"><span class="dot"></span>Active</span>';
    return '<span class="chip chip-muted">Ended</span>';
  }

  async function load() {
    try {
      const data = await Api.get(`/api/teacher/subjects/${SUBJECT_ID}`);
      currentClassId = data.class.id;
      document.getElementById("backLink").href = `/teacher/classes/${data.class.id}`;
      document.getElementById("classNameLabel").textContent = `${data.class.name}${data.class.section ? " · " + data.class.section : ""}`;
      document.getElementById("subjectName").textContent = data.subject.name;

      document.getElementById("startSessionBtn").classList.toggle("hidden", !data.can_manage_sessions);
      canManageClass = !!data.can_manage_class;
      document.getElementById("assignTeacherCard").classList.toggle("hidden", !canManageClass);

      // Sessions
      const body = document.getElementById("sessionsBody");
      const empty = document.getElementById("emptySessions");
      if (!data.sessions.length) {
        empty.classList.remove("hidden");
        body.innerHTML = "";
      } else {
        empty.classList.add("hidden");
        body.innerHTML = data.sessions.map((s) => `
          <tr>
            <td>${formatDate(s.start_time)}</td>
            <td>${statusChip(s)}</td>
            <td>${s.present_count}</td>
            <td><a href="/teacher/sessions/${s.id}" class="btn btn-outline btn-sm">View</a></td>
          </tr>
        `).join("");
      }

      // Subject teachers + assignment dropdown (from class_teachers list)
      renderSubjectTeachers(data.subject.teachers);
      populateTeacherSelect(data.class_teachers, data.subject.teachers);
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  function renderSubjectTeachers(teachers) {
    const body = document.getElementById("subjectTeachersBody");
    const empty = document.getElementById("emptySubjectTeachers");
    if (!teachers.length) {
      empty.classList.remove("hidden");
      body.innerHTML = "";
      return;
    }
    empty.classList.add("hidden");
    body.innerHTML = teachers.map((t) => `
      <tr>
        <td>${escapeHtml(t.name)}</td>
        <td>${escapeHtml(t.email)}</td>
        <td>${canManageClass ? `<button class="btn btn-danger btn-sm" data-remove-subject-teacher="${t.id}">Remove</button>` : ""}</td>
      </tr>
    `).join("");
    body.querySelectorAll("[data-remove-subject-teacher]").forEach((btn) => {
      btn.addEventListener("click", () => removeSubjectTeacher(btn.dataset.removeSubjectTeacher));
    });
  }

  function populateTeacherSelect(classTeachers, subjectTeachers) {
    const select = document.getElementById("teacherSelect");
    const assignedIds = new Set(subjectTeachers.map((t) => t.id));
    const available = classTeachers.filter((t) => !assignedIds.has(t.id));
    if (!available.length) {
      select.innerHTML = `<option value="">All class teachers already assigned</option>`;
      select.disabled = true;
      return;
    }
    select.disabled = false;
    select.innerHTML = available.map((t) => `<option value="${escapeHtml(t.email)}">${escapeHtml(t.name)} (${escapeHtml(t.email)})</option>`).join("");
  }

  document.getElementById("assignTeacherForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    const email = document.getElementById("teacherSelect").value;
    if (!email) return;
    try {
      await Api.post(`/api/teacher/subjects/${SUBJECT_ID}/teachers`, { email });
      load();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  async function removeSubjectTeacher(teacherId) {
    if (!confirm("Remove this teacher from the subject?")) return;
    try {
      await Api.del(`/api/teacher/subjects/${SUBJECT_ID}/teachers/${teacherId}`);
      load();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  // --- Report ---------------------------------------------------------------
  let reportLoaded = false;
  async function loadReport() {
    if (reportLoaded) return;
    try {
      const data = await Api.get(`/api/teacher/subjects/${SUBJECT_ID}/attendance-report`);
      document.getElementById("reportSummary").textContent = `${data.total_sessions} session${data.total_sessions === 1 ? "" : "s"} held so far`;
      const body = document.getElementById("reportBody");
      const empty = document.getElementById("emptyReport");
      if (!data.report.length) {
        empty.classList.remove("hidden");
        body.innerHTML = "";
        return;
      }
      empty.classList.add("hidden");
      body.innerHTML = data.report.map((r) => `
        <tr>
          <td>${escapeHtml(r.name)}</td>
          <td>${escapeHtml(r.enrollment_no || "—")}</td>
          <td>${r.sessions_present} / ${r.total_sessions}</td>
          <td>
            <div class="flex items-center gap-8">
              <div class="progress-track" style="width:100px;"><div class="progress-fill" style="width:${r.attendance_percent}%;"></div></div>
              <span class="text-sm">${r.attendance_percent}%</span>
            </div>
          </td>
        </tr>
      `).join("");
      reportLoaded = true;
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  document.getElementById("exportBtn").addEventListener("click", async () => {
    try {
      const res = await fetch(`/api/teacher/subjects/${SUBJECT_ID}/attendance-report/export`, {
        headers: { Authorization: `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) throw new Error("Could not export report");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "attendance_report.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  // --- Start session modal -------------------------------------------------
  const sessionModal = document.getElementById("sessionModalBackdrop");
  document.getElementById("startSessionBtn").addEventListener("click", () => {
    sessionModal.classList.remove("hidden");
  });
  document.getElementById("cancelSessionBtn").addEventListener("click", () => {
    sessionModal.classList.add("hidden");
  });

  document.getElementById("sessionForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const sessionAlertBox = document.getElementById("sessionAlertBox");
    const confirmBtn = document.getElementById("confirmSessionBtn");
    clearAlert(sessionAlertBox);
    confirmBtn.disabled = true;
    confirmBtn.innerHTML = `<span class="spinner"></span> Getting location…`;

    try {
      const pos = await getCurrentPosition();
      confirmBtn.innerHTML = `<span class="spinner"></span> Starting…`;
      const payload = {
        duration_minutes: parseInt(document.getElementById("durationInput").value, 10),
        radius_meters: parseFloat(document.getElementById("radiusInput").value),
        latitude: pos.latitude,
        longitude: pos.longitude,
      };
      const data = await Api.post(`/api/teacher/subjects/${SUBJECT_ID}/sessions`, payload);
      window.location.href = `/teacher/sessions/${data.session.id}`;
    } catch (err) {
      showAlert(sessionAlertBox, err.message);
      confirmBtn.disabled = false;
      confirmBtn.textContent = "Start session";
    }
  });

  load();
})();
