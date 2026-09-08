/**
 * Live password strength checklist. Mirrors the server-side rules in
 * utils/validators.py exactly:
 *   - at least 7 characters
 *   - at least one uppercase letter
 *   - at least one digit
 *   - at least one special character
 *
 * Usage:
 *   const checker = attachPasswordStrengthChecklist(passwordInputEl, checklistContainerEl);
 *   checker.isValid()  -> true/false, call before submitting the form
 */
function checkPasswordRequirements(password) {
  password = password || "";
  return {
    length: password.length >= 7,
    uppercase: /[A-Z]/.test(password),
    digit: /[0-9]/.test(password),
    special: /[^A-Za-z0-9]/.test(password),
  };
}

function attachPasswordStrengthChecklist(inputEl, containerEl) {
  const rules = [
    { key: "length", label: "At least 7 characters" },
    { key: "uppercase", label: "At least one uppercase letter (A-Z)" },
    { key: "digit", label: "At least one number (0-9)" },
    { key: "special", label: "At least one special character (! @ # $ % etc.)" },
  ];

  containerEl.innerHTML = rules.map(r => `
    <div class="pw-rule" data-rule="${r.key}">
      <span class="pw-rule-icon">○</span>
      <span class="pw-rule-label">${r.label}</span>
    </div>
  `).join("");

  function render() {
    const status = checkPasswordRequirements(inputEl.value);
    rules.forEach(r => {
      const row = containerEl.querySelector(`[data-rule="${r.key}"]`);
      const icon = row.querySelector(".pw-rule-icon");
      const ok = status[r.key];
      row.classList.toggle("pw-rule-ok", ok);
      row.classList.toggle("pw-rule-bad", !ok);
      icon.textContent = ok ? "✓" : "○";
    });
    return status;
  }

  inputEl.addEventListener("input", render);
  render(); // initial state

  return {
    isValid() {
      const status = checkPasswordRequirements(inputEl.value);
      return Object.values(status).every(Boolean);
    },
    refresh: render,
  };
}
