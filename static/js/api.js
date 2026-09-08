/**
 * Thin fetch wrapper that attaches the JWT (stored in localStorage after
 * login/register) to every API call and centralizes error handling.
 */
function dashboardUrlForRole(role) {
  if (role === "admin") return "/admin/dashboard";
  if (role === "teacher") return "/teacher/dashboard";
  return "/student/dashboard";
}

const Auth = {
  getToken() { return localStorage.getItem("token"); },
  getUser() {
    const raw = localStorage.getItem("user");
    return raw ? JSON.parse(raw) : null;
  },
  setSession(token, user) {
    localStorage.setItem("token", token);
    localStorage.setItem("user", JSON.stringify(user));
  },
  clearSession() {
    localStorage.removeItem("token");
    localStorage.removeItem("user");
  },
  isLoggedIn() { return !!this.getToken(); },
  requireRole(role) {
    return this.requireAnyRole(role ? [role] : null);
  },
  requireAnyRole(roles) {
    const user = this.getUser();
    if (!this.isLoggedIn() || !user) {
      window.location.href = "/login";
      return null;
    }
    if (roles && !roles.includes(user.role)) {
      window.location.href = dashboardUrlForRole(user.role);
      return null;
    }
    return user;
  },
  logout() {
    this.clearSession();
    window.location.href = "/login";
  },
};

const Api = {
  async request(path, { method = "GET", body = null } = {}) {
    const headers = { "Content-Type": "application/json" };
    const token = Auth.getToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;

    let res;
    try {
      res = await fetch(path, {
        method,
        headers,
        body: body ? JSON.stringify(body) : undefined,
      });
    } catch (networkErr) {
      throw new Error("Could not reach the server. Please check your connection.");
    }

    let data = null;
    const contentType = res.headers.get("content-type") || "";
    if (contentType.includes("application/json")) {
      data = await res.json().catch(() => null);
    }

    if (res.status === 401 && path !== "/api/auth/login" && path !== "/api/auth/register") {
      // Token expired/invalid/missing — force a clean re-login rather than
      // letting the current page keep running with a stale session (which
      // previously showed a confusing error and still let you click
      // around before the redirect landed).
      const realReason = (data && data.error) || `HTTP 401 on ${path}`;
      console.error(`[auth] Redirecting to login because: ${realReason}`);
      Auth.clearSession();
      window.location.href = `/login?reason=session_expired&detail=${encodeURIComponent(realReason)}`;
      // Never resolve/reject — the page is navigating away now, so no
      // caller's .catch() should get a chance to render a stale error.
      return new Promise(() => {});
    }

    if (!res.ok) {
      const err = new Error((data && data.error) || `Request failed (${res.status})`);
      err.data = data;
      err.status = res.status;
      throw err;
    }
    return data;
  },
  get(path) { return this.request(path); },
  post(path, body) { return this.request(path, { method: "POST", body }); },
  del(path) { return this.request(path, { method: "DELETE" }); },
};

function showAlert(container, message, type = "error") {
  if (!container) return;
  container.innerHTML = `<div class="alert alert-${type === "error" ? "error" : type}">${escapeHtml(message)}</div>`;
}

function clearAlert(container) {
  if (container) container.innerHTML = "";
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    month: "short", day: "numeric", year: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

function initials(name) {
  if (!name) return "?";
  return name.trim().split(/\s+/).slice(0, 2).map(w => w[0].toUpperCase()).join("");
}
