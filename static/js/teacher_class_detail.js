(function () {
  const user = Auth.requireAnyRole(["teacher", "admin"]);
  if (!user) return;

  const alertBox = document.getElementById("alertBox");
  let canManageClass = false;

  // --- Tabs -------------------------------------------------------------
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.add("hidden"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.remove("hidden");
      if (btn.dataset.tab === "overview") loadOverview();
    });
  });

  // --- Load class header + students/teachers/subjects --------------------
  async function loadClass() {
    try {
      const data = await Api.get(`/api/teacher/classes/${CLASS_ID}`);
      document.getElementById("className").textContent = data.class.name;
      document.getElementById("classSubtitle").textContent = data.class.section || "Class";
      document.getElementById("joinCodeChip").textContent = data.class.join_code;
      canManageClass = !!data.can_manage_class;

      document.getElementById("addSubjectCard").classList.toggle("hidden", !canManageClass);
      document.getElementById("addStudentCard").classList.toggle("hidden", !canManageClass);

      renderStudents(data.students);
      renderClassTeacherPanel(data.class.class_teacher, data.teachers);
      renderTeachers(data.teachers);
      renderSubjects(data.subjects);
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  function renderClassTeacherPanel(classTeacher, teachers) {
    const chip = document.getElementById("classTeacherChip");
    if (classTeacher) {
      chip.textContent = classTeacher.name;
      chip.className = "chip chip-teal";
    } else {
      chip.textContent = "None assigned";
      chip.className = "chip chip-muted";
    }

    const form = document.getElementById("setClassTeacherForm");
    const select = document.getElementById("classTeacherSelect");
    if (user.role !== "admin") {
      form.classList.add("hidden");
      return;
    }
    form.classList.remove("hidden");
    const candidates = teachers.filter((t) => t.role !== "admin");
    if (!candidates.length) {
      select.innerHTML = `<option value="">Add a teacher below first</option>`;
    } else {
      select.innerHTML = candidates.map((t) =>
        `<option value="${escapeHtml(t.email)}" ${classTeacher && classTeacher.id === t.id ? "selected" : ""}>${escapeHtml(t.name)}</option>`
      ).join("");
    }
  }

  function renderSubjects(subjects) {
    const grid = document.getElementById("subjectsGrid");
    const empty = document.getElementById("emptySubjects");
    if (!subjects.length) {
      empty.classList.remove("hidden");
      grid.innerHTML = "";
      return;
    }
    empty.classList.add("hidden");
    grid.innerHTML = subjects.map((s) => `
      <a class="card-link" href="/teacher/subjects/${s.id}">
        <div class="h-card mb-8">${escapeHtml(s.name)}</div>
        <p class="text-sm">${s.teachers.length ? s.teachers.map(t => escapeHtml(t.name)).join(", ") : "No teacher assigned yet"}</p>
        <div class="text-sm text-muted mt-16">${s.session_count} session${s.session_count === 1 ? "" : "s"} held</div>
      </a>
    `).join("");
  }

  function renderStudents(students) {
    const body = document.getElementById("studentsBody");
    const empty = document.getElementById("emptyStudents");
    if (!students.length) {
      empty.classList.remove("hidden");
      body.innerHTML = "";
      return;
    }
    empty.classList.add("hidden");
    body.innerHTML = students.map((s) => `
      <tr>
        <td>${escapeHtml(s.name)}</td>
        <td>${escapeHtml(s.enrollment_no || "—")}</td>
        <td>${escapeHtml(s.email)}</td>
        <td>${s.face_enrolled ? '<span class="chip chip-success">Enrolled</span>' : '<span class="chip chip-amber">Pending</span>'}</td>
        <td>${canManageClass ? `<button class="btn btn-danger btn-sm" data-remove-student="${s.id}">Remove</button>` : ""}</td>
      </tr>
    `).join("");
    body.querySelectorAll("[data-remove-student]").forEach((btn) => {
      btn.addEventListener("click", () => removeStudent(btn.dataset.removeStudent));
    });
  }

  function renderTeachers(teachers) {
    document.getElementById("addTeacherCard").classList.toggle("hidden", !canManageClass);

    const body = document.getElementById("teachersBody");
    body.innerHTML = teachers.map((t) => {
      const isAdminRow = t.role === "admin";
      const tags = [
        t.id === user.id ? '<span class="chip chip-muted">You</span>' : "",
        isAdminRow ? '<span class="chip chip-amber">Admin</span>' : "",
      ].filter(Boolean).join(" ");
      const canRemoveThisRow = canManageClass && !isAdminRow && teachers.length > 1;
      return `
        <tr>
          <td>${escapeHtml(t.name)} ${tags}</td>
          <td>${escapeHtml(t.email)}</td>
          <td>${canRemoveThisRow ? `<button class="btn btn-danger btn-sm" data-remove-teacher="${t.id}">Remove</button>` : ""}</td>
        </tr>
      `;
    }).join("");
    body.querySelectorAll("[data-remove-teacher]").forEach((btn) => {
      btn.addEventListener("click", () => removeTeacher(btn.dataset.removeTeacher));
    });
  }

  document.getElementById("addSubjectForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    const name = document.getElementById("subjectName").value.trim();
    try {
      await Api.post(`/api/teacher/classes/${CLASS_ID}/subjects`, { name });
      document.getElementById("subjectName").value = "";
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  document.getElementById("addStudentForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    const email = document.getElementById("studentEmail").value.trim();
    try {
      await Api.post(`/api/teacher/classes/${CLASS_ID}/students`, { email });
      document.getElementById("studentEmail").value = "";
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  async function removeStudent(studentId) {
    if (!confirm("Remove this student from the class?")) return;
    try {
      await Api.del(`/api/teacher/classes/${CLASS_ID}/students/${studentId}`);
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  document.getElementById("addTeacherForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    const email = document.getElementById("teacherEmail").value.trim();
    try {
      await Api.post(`/api/teacher/classes/${CLASS_ID}/teachers`, { email });
      document.getElementById("teacherEmail").value = "";
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  async function removeTeacher(teacherId) {
    if (!confirm("Remove this teacher from the class?")) return;
    try {
      await Api.del(`/api/teacher/classes/${CLASS_ID}/teachers/${teacherId}`);
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  document.getElementById("setClassTeacherForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    clearAlert(alertBox);
    const email = document.getElementById("classTeacherSelect").value;
    if (!email) return;
    try {
      await Api.post(`/api/teacher/classes/${CLASS_ID}/class-teacher`, { email });
      loadClass();
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  // --- Overview matrix (subjects as columns, students as rows) ------------
  function pctClass(pct) {
    if (pct >= 75) return "matrix-pct-good";
    if (pct >= 50) return "matrix-pct-warn";
    return "matrix-pct-bad";
  }

  let overviewLoaded = false;
  async function loadOverview() {
    if (overviewLoaded) return;
    try {
      const data = await Api.get(`/api/teacher/classes/${CLASS_ID}/attendance-overview`);
      const subjectNames = data.subjects.map(s => s.subject_name).join(", ") || "no subjects yet";
      document.getElementById("overviewSummary").textContent = `Combined across: ${subjectNames}`;

      // Build header row: Name | Enrollment | <one column per subject> | Overall
      const headerRow = document.getElementById("matrixHeaderRow");
      let headerHtml = `<th class="matrix-name-col">Name</th><th>Enrollment No</th>`;
      data.subjects.forEach((s) => {
        headerHtml += `<th>${escapeHtml(s.subject_name)}<br><span class="text-faint" style="font-weight:500; font-size:0.7rem;">(${s.total_sessions} session${s.total_sessions === 1 ? "" : "s"})</span></th>`;
      });
      headerHtml += `<th class="matrix-overall-col">Overall</th>`;
      headerRow.innerHTML = headerHtml;

      const body = document.getElementById("overviewBody");
      const empty = document.getElementById("emptyOverview");
      if (!data.rows.length) {
        empty.classList.remove("hidden");
        body.innerHTML = "";
        return;
      }
      empty.classList.add("hidden");

      body.innerHTML = data.rows.map((r) => {
        let cells = `<td class="matrix-name-col">${escapeHtml(r.name)}</td><td>${escapeHtml(r.enrollment_no || "—")}</td>`;
        data.subjects.forEach((s) => {
          const cell = r.per_subject[String(s.subject_id)];
          const pct = cell ? cell.attendance_percent : 0;
          const frac = cell ? `${cell.sessions_present}/${cell.total_sessions}` : "0/0";
          cells += `<td class="${pctClass(pct)}" title="${frac} sessions">${pct}%</td>`;
        });
        cells += `<td class="matrix-overall-col ${pctClass(r.overall_percent)}">${r.overall_percent}% <span class="text-faint" style="font-weight:500; font-size:0.72rem;">(${r.overall_present}/${r.overall_total})</span></td>`;
        return `<tr>${cells}</tr>`;
      }).join("");
      overviewLoaded = true;
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  document.getElementById("exportMatrixBtn").addEventListener("click", async () => {
    try {
      const res = await fetch(`/api/teacher/classes/${CLASS_ID}/attendance-overview/export`, {
        headers: { Authorization: `Bearer ${Auth.getToken()}` },
      });
      if (!res.ok) throw new Error("Could not export report");
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "attendance_matrix.csv";
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  });

  loadClass();
})();
