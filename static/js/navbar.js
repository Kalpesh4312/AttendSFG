(function renderNav() {
  const el = document.getElementById("navLinks");
  if (!el) return;

  const user = Auth.getUser();
  if (!user) {
    el.innerHTML = `
      <a href="/login">Log in</a>
      <a href="/register" class="btn btn-teal btn-sm">Get started</a>
    `;
    return;
  }

  const dashboardUrl = dashboardUrlForRole(user.role);
  const roleLabel = user.role === "admin" ? '<span class="chip chip-amber" style="margin-left:6px;">Admin</span>' : "";
  el.innerHTML = `
    <a href="${dashboardUrl}">Dashboard</a>
    <div class="nav-pill">
      <span class="avatar-dot">${initials(user.name)}</span>
      <span>${escapeHtml(user.name)}</span>
      ${roleLabel}
    </div>
    <button id="logoutBtn">Log out</button>
  `;
  document.getElementById("logoutBtn").addEventListener("click", () => Auth.logout());
})();
