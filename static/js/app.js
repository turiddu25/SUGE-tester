window.renderMarkdown = function (text) {
  if (!text) return "";
  try {
    if (window.marked) {
      return window.marked.parse(text);
    }
  } catch (e) {
    console.warn("markdown render failed", e);
  }
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
};

document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".markdown-target[data-md]").forEach((el) => {
    el.innerHTML = window.renderMarkdown(el.dataset.md);
  });
});

window.formatSeconds = function (s) {
  s = Math.max(0, Math.floor(s));
  const m = Math.floor(s / 60);
  const sec = s % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
};

window.toggleTheme = function () {
  const isDark = document.documentElement.classList.toggle("dark");
  try { localStorage.setItem("suge_theme", isDark ? "dark" : "light"); } catch (e) {}
};

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("theme-toggle");
  if (btn) btn.addEventListener("click", window.toggleTheme);
});
