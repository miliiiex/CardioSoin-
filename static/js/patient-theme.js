(function () {
  "use strict";

  var STORAGE_KEY = "cardiosoin-patient-theme";

  function getTheme() {
    var t = document.documentElement.getAttribute("data-patient-theme");
    return t === "light" || t === "dark" ? t : "dark";
  }

  function setTheme(theme) {
    if (theme !== "light" && theme !== "dark") theme = "dark";
    document.documentElement.setAttribute("data-patient-theme", theme);
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (e) {}
    syncToggleUi(theme);
  }

  function syncToggleUi(theme) {
    var isLight = theme === "light";
    document.querySelectorAll("[data-patient-theme-toggle]").forEach(function (btn) {
      btn.setAttribute("aria-pressed", isLight ? "false" : "true");
      btn.setAttribute(
        "title",
        isLight ? "Passer au thème sombre (icône lune)" : "Passer au thème clair (icône soleil)"
      );
      btn.setAttribute(
        "aria-label",
        isLight ? "Activer le thème sombre" : "Activer le thème clair"
      );
    });
  }

  function initFromStorage() {
    var stored = null;
    try {
      stored = localStorage.getItem(STORAGE_KEY);
    } catch (e) {}
    var theme = stored === "light" || stored === "dark" ? stored : "dark";
    document.documentElement.setAttribute("data-patient-theme", theme);
    syncToggleUi(theme);
  }

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-patient-theme-toggle]");
    if (!btn) return;
    e.preventDefault();
    setTheme(getTheme() === "dark" ? "light" : "dark");
  });

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initFromStorage);
  } else {
    initFromStorage();
  }
})();
