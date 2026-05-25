/**
 * Accueil public : modale RDV au-dessus de la page + validation locale date/heure non passées.
 */
(function () {
  const panel = document.getElementById("lp-rdv-panel");
  if (!panel) return;

  const openers = document.querySelectorAll(".lp-open-rdv");
  const closers = document.querySelectorAll(".lp-close-rdv");
  const form = document.getElementById("lp-rdv-form");
  const clientErr = document.getElementById("lp-rdv-client-error");
  const dialog = panel.querySelector(".lp-rdv-overlay__dialog");

  let previousFocus = null;

  function openPanel() {
    previousFocus = document.activeElement;
    panel.hidden = false;
    panel.removeAttribute("aria-hidden");
    document.body.classList.add("lp-rdv-open");
    if (clientErr) {
      clientErr.hidden = true;
      clientErr.textContent = "";
    }
    window.setTimeout(function () {
      const root = dialog || panel;
      let focusable =
        root.querySelector(
          "#lp-rdv-guest-nom, #lp-rdv-medecin, input:not([disabled]):not([type='hidden']), select:not([disabled]), textarea:not([disabled])"
        ) || root.querySelector("a.lp-rdv-panel__btn");
      focusable =
        focusable ||
        root.querySelector(".lp-close-rdv") ||
        root.querySelector("button, [href]");
      if (focusable && typeof focusable.focus === "function") focusable.focus();
    }, 10);
  }

  function closePanel() {
    panel.hidden = true;
    panel.setAttribute("aria-hidden", "true");
    document.body.classList.remove("lp-rdv-open");
    if (previousFocus && typeof previousFocus.focus === "function") previousFocus.focus();
    previousFocus = null;
  }

  openers.forEach(function (el) {
    el.addEventListener("click", openPanel);
  });
  closers.forEach(function (el) {
    el.addEventListener("click", function (e) {
      e.preventDefault();
      closePanel();
    });
  });

  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !panel.hidden) {
      closePanel();
    }
  });

  if (panel.getAttribute("data-lp-auto-open") === "1") {
    openPanel();
  }

  if (!form || !clientErr) return;

  const MSG_PAST =
    "Veuillez choisir une date et une heure dans le futur (une date ou un horaire déjà passés ne sont pas acceptés).";

  form.addEventListener("submit", function (e) {
    const dateEl = document.getElementById("lp-rdv-date");
    const timeEl = document.getElementById("lp-rdv-heure");
    if (!dateEl || !timeEl || !dateEl.value || !timeEl.value) return;

    const combined = new Date(dateEl.value + "T" + timeEl.value);
    if (Number.isNaN(combined.getTime())) return;

    const now = new Date();
    if (combined <= now) {
      e.preventDefault();
      clientErr.textContent = MSG_PAST;
      clientErr.hidden = false;
    }
  });
})();

/**
 * Bandeaux Django (messages) : fermeture au clic sur ×
 */
(function () {
  document.querySelectorAll(".lp-toast__close").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var toast = btn.closest(".lp-toast");
      var stack = document.getElementById("lp-toast-stack");
      if (!toast) return;
      toast.classList.add("lp-toast--out");
      window.setTimeout(function () {
        toast.remove();
        if (stack && !stack.querySelector(".lp-toast")) {
          stack.remove();
        }
      }, 260);
    });
  });
})();
