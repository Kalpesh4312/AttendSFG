(function () {
  const user = Auth.requireAnyRole(["teacher", "admin"]);
  if (!user) return;

  const isAdmin = user.role === "admin";
  document.getElementById("panelLabel").textContent = isAdmin ? "Admin panel" : "Teacher panel";
  document.getElementById("welcomeText").textContent = isAdmin
    ? "All classes"
    : `Welcome, ${user.name.split(" ")[0]}`;

  const grid = document.getElementById("classesGrid");
  const emptyState = document.getElementById("emptyState");
  const alertBox = document.getElementById("alertBox");
  const modal = document.getElementById("newClassBackdrop");
  const subjectRows = document.getElementById("subjectRows");

  if (isAdmin) {
    emptyState.querySelector("p").innerHTML = "<strong>No classes have been created yet.</strong><br>Create one to get started.";
  } else {
    document.getElementById("newClassBtn").classList.add("hidden");
    emptyState.querySelector("p").innerHTML = "<strong>You haven't been assigned to any classes yet.</strong><br>Ask your admin or class teacher to add you.";
  }

  function addSubjectRow(value = "") {
    const row = document.createElement("div");
    row.className = "flex gap-8 mb-8";
    row.innerHTML = `
      <input type="text" class="subject-name-input" placeholder="e.g. Data Ethics" value="${escapeHtml(value)}">
      <button type="button" class="btn btn-outline btn-sm remove-subject-row" title="Remove">✕</button>
    `;
    row.querySelector(".remove-subject-row").addEventListener("click", () => row.remove());
    subjectRows.appendChild(row);
  }

  document.getElementById("addSubjectRowBtn").addEventListener("click", () => addSubjectRow());

  function resetSubjectRows() {
    subjectRows.innerHTML = "";
    addSubjectRow();
  }

  document.getElementById("newClassBtn").addEventListener("click", () => {
    resetSubjectRows();
    modal.classList.remove("hidden");
  });
  document.getElementById("cancelNewClassBtn").addEventListener("click", () => modal.classList.add("hidden"));

  document.getElementById("newClassForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const newClassAlertBox = document.getElementById("newClassAlertBox");
    clearAlert(newClassAlertBox);

    const subjects = Array.from(document.querySelectorAll(".subject-name-input"))
      .map((input) => input.value.trim())
      .filter(Boolean);

    const payload = {
      name: document.getElementById("className").value.trim(),
      section: document.getElementById("classSection").value.trim(),
      subjects,
    };
    try {
      const data = await Api.post("/api/teacher/classes", payload);
      modal.classList.add("hidden");
      window.location.href = `/teacher/classes/${data.class.id}`;
    } catch (err) {
      showAlert(newClassAlertBox, err.message);
    }
  });

  function classCard(cls) {
    return `
      <a class="card-link" href="/teacher/classes/${cls.id}">
        <div class="flex justify-between items-center mb-16">
          <div class="icon-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V4H6.5A2.5 2.5 0 004 6.5v13z" stroke="currentColor" stroke-width="1.6"/></svg>
          </div>
          <span class="chip chip-muted mono">${escapeHtml(cls.join_code)}</span>
        </div>
        <div class="h-card">${escapeHtml(cls.name)}</div>
        <p class="text-sm mt-8">${cls.section ? escapeHtml(cls.section) : "&nbsp;"}</p>
        <p class="text-sm text-muted mt-8">${cls.class_teacher ? "Class teacher: " + escapeHtml(cls.class_teacher.name) : "No class teacher assigned"}</p>
        <div class="flex gap-16 mt-16 text-sm text-muted">
          <span>${cls.subject_count} subject${cls.subject_count === 1 ? "" : "s"}</span>
          <span>${cls.student_count} student${cls.student_count === 1 ? "" : "s"}</span>
          <span>${cls.teacher_count} teacher${cls.teacher_count === 1 ? "" : "s"}</span>
        </div>
      </a>
    `;
  }

  async function loadClasses() {
    try {
      const data = await Api.get("/api/teacher/classes");
      if (!data.classes.length) {
        emptyState.classList.remove("hidden");
        grid.innerHTML = "";
        return;
      }
      emptyState.classList.add("hidden");
      grid.innerHTML = data.classes.map(classCard).join("");
    } catch (err) {
      showAlert(alertBox, err.message);
    }
  }

  loadClasses();
})();
