(function () {
  const user = Auth.requireRole("student");
  if (!user) return;

  document.getElementById("welcomeText").textContent = `Welcome, ${user.name.split(" ")[0]}`;

  const grid = document.getElementById("classesGrid");
  const emptyState = document.getElementById("emptyState");
  const alertBox = document.getElementById("alertBox");
  const bannerEl = document.getElementById("activeSessionBanner");

  const joinModal = document.getElementById("joinModalBackdrop");
  document.getElementById("joinClassBtn").addEventListener("click", () => joinModal.classList.remove("hidden"));
  document.getElementById("cancelJoinBtn").addEventListener("click", () => joinModal.classList.add("hidden"));

  document.getElementById("faceStatusBtn").addEventListener("click", () => {
    window.location.href = "/student/enroll-face";
  });

  document.getElementById("joinForm").addEventListener("submit", async (e) => {
    e.preventDefault();
    const joinAlertBox = document.getElementById("joinAlertBox");
    clearAlert(joinAlertBox);
    const code = document.getElementById("joinCode").value.trim();
    try {
      await Api.post("/api/student/classes/join", { join_code: code });
      joinModal.classList.add("hidden");
      document.getElementById("joinCode").value = "";
      loadClasses();
    } catch (err) {
      showAlert(joinAlertBox, err.message);
    }
  });

  function classCard(cls) {
    return `
      <a class="card-link" href="/student/classes/${cls.id}">
        <div class="flex justify-between items-center mb-16">
          <div class="icon-badge">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none"><path d="M4 19.5A2.5 2.5 0 016.5 17H20M4 19.5A2.5 2.5 0 006.5 22H20V4H6.5A2.5 2.5 0 004 6.5v13z" stroke="currentColor" stroke-width="1.6"/></svg>
          </div>
          <span class="chip chip-muted mono">${escapeHtml(cls.join_code)}</span>
        </div>
        <div class="h-card">${escapeHtml(cls.name)}</div>
        <p class="text-sm mt-8">${cls.section ? escapeHtml(cls.section) : "&nbsp;"}</p>
        <div class="text-sm text-muted mt-16">${cls.subject_count} subject${cls.subject_count === 1 ? "" : "s"}</div>
      </a>
    `;
  }

  async function loadActiveSessions() {
    try {
      const data = await Api.get("/api/student/active-sessions");
      if (data.active && data.active.length) {
        bannerEl.innerHTML = data.active.map(a => `
          <div class="alert alert-info flex justify-between items-center" style="flex-wrap:wrap; gap:12px;">
            <span><strong>${escapeHtml(a.subject.name)}</strong> (${escapeHtml(a.class.name)}) has an attendance session open right now.</span>
            <a href="/student/mark-attendance" class="btn btn-teal btn-sm">Mark attendance</a>
          </div>
        `).join("");
      } else {
        bannerEl.innerHTML = "";
      }
    } catch (err) { /* non-fatal */ }
  }

  async function loadClasses() {
    try {
      const data = await Api.get("/api/student/classes");
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
  loadActiveSessions();
  setInterval(loadActiveSessions, 15000);
})();
