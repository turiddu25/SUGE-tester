// Global keyboard shortcuts. Added in Phase 5 step 4 — see BUILD_NOTES.
(function () {
  let buffer = "";
  let bufferTimer = null;

  function isTyping(el) {
    if (!el) return false;
    const tag = el.tagName;
    return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable;
  }

  function go(path) {
    window.location.href = path;
  }

  function openHelp() {
    let modal = document.getElementById("shortcuts-modal");
    if (!modal) {
      modal = document.createElement("div");
      modal.id = "shortcuts-modal";
      modal.className = "fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4";
      modal.innerHTML = `
        <div class="w-full max-w-md rounded-lg bg-white p-5 shadow-xl dark:bg-neutral-900 dark:text-neutral-100">
          <div class="mb-3 flex items-center justify-between">
            <div class="font-semibold">Keyboard shortcuts</div>
            <button id="shortcuts-close" class="text-neutral-500 hover:text-neutral-900 dark:hover:text-white">✕</button>
          </div>
          <ul class="space-y-1.5 text-sm">
            <li class="flex items-center justify-between"><span>Open this help</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">?</kbd></li>
            <li class="flex items-center justify-between"><span>Toggle dark mode</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">d</kbd></li>
            <li class="flex items-center justify-between"><span>Random question</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">r</kbd></li>
            <li class="flex items-center justify-between"><span>Go to home</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g h</kbd></li>
            <li class="flex items-center justify-between"><span>Go to questions</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g q</kbd></li>
            <li class="flex items-center justify-between"><span>Go to review</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g v</kbd></li>
            <li class="flex items-center justify-between"><span>Go to exam sim</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g e</kbd></li>
            <li class="flex items-center justify-between"><span>Go to reference</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g r</kbd></li>
            <li class="flex items-center justify-between"><span>Go to products</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">g p</kbd></li>
            <li class="flex items-center justify-between"><span>Submit answer (in practice)</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">Ctrl/⌘ + Enter</kbd></li>
            <li class="flex items-center justify-between"><span>Close modal</span><kbd class="rounded bg-neutral-200 px-1.5 py-0.5 font-mono text-xs dark:bg-neutral-800">Esc</kbd></li>
          </ul>
        </div>`;
      document.body.appendChild(modal);
      modal.addEventListener("click", (e) => {
        if (e.target === modal) modal.remove();
      });
      modal.querySelector("#shortcuts-close").addEventListener("click", () => modal.remove());
    }
  }

  function closeAnyModal() {
    const modal = document.getElementById("shortcuts-modal");
    if (modal) modal.remove();
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAnyModal();
      return;
    }
    // Ctrl/Cmd+Enter triggers submit on practice mode if a textarea has focus.
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") {
      const ta = document.activeElement;
      if (ta && ta.tagName === "TEXTAREA") {
        const form = ta.closest("[x-data]");
        if (form && form.__x) {
          // Alpine root: try to call submit()
          try { form.__x.$data.submit && form.__x.$data.submit(); return; } catch (_) {}
        }
      }
    }
    if (isTyping(e.target)) return;
    if (e.metaKey || e.ctrlKey || e.altKey) return;
    const k = e.key;
    if (k === "?") { e.preventDefault(); openHelp(); return; }
    if (k === "d") { e.preventDefault(); window.toggleTheme && window.toggleTheme(); return; }
    if (k === "r") { e.preventDefault(); go("/practice/random"); return; }

    if (buffer === "g") {
      buffer = "";
      clearTimeout(bufferTimer);
      const map = { h: "/", q: "/questions", v: "/review", e: "/exam-sim", r: "/reference", p: "/products" };
      if (map[k]) { e.preventDefault(); go(map[k]); }
      return;
    }
    if (k === "g") {
      buffer = "g";
      clearTimeout(bufferTimer);
      bufferTimer = setTimeout(() => { buffer = ""; }, 1200);
      e.preventDefault();
    }
  });
})();
