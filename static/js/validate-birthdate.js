/**
 * Validation cohérente : jour réel du mois (y compris bissextile), pas de date future.
 * Complète type="date" (certains navigateurs laissent saisir des jours incohérents).
 */
(function () {
  function lastDayOfMonth(y, m) {
    return new Date(y, m, 0).getDate();
  }

  function validateEl(el) {
    if (!el) return;
    const v = (el.value || "").trim();
    if (!v) {
      el.setCustomValidity("");
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(v)) {
      el.setCustomValidity("Utilisez le format AAAA-MM-JJ.");
      return;
    }
    const y = parseInt(v.slice(0, 4), 10);
    const m = parseInt(v.slice(5, 7), 10);
    const d = parseInt(v.slice(8, 10), 10);
    if (m < 1 || m > 12) {
      el.setCustomValidity("Le mois doit être entre 1 et 12.");
      return;
    }
    const maxD = lastDayOfMonth(y, m);
    if (d < 1 || d > maxD) {
      el.setCustomValidity("Jour entre 1 et " + maxD + " pour ce mois (ex. 31, 30, 28 ou 29, pas 45 ni 56).");
      return;
    }
    const birth = new Date(y, m - 1, d);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    birth.setHours(0, 0, 0, 0);
    if (birth.getTime() > today.getTime()) {
      el.setCustomValidity("La date de naissance ne peut pas être après aujourd’hui.");
      return;
    }
    el.setCustomValidity("");
  }

  function wire(id) {
    const el = document.getElementById(id);
    if (!el) return;
    const run = function () {
      validateEl(el);
    };
    el.addEventListener("input", run);
    el.addEventListener("change", run);
    const form = el.form;
    if (form) {
      form.addEventListener(
        "submit",
        function (e) {
          validateEl(el);
          if (!el.checkValidity()) {
            e.preventDefault();
            e.stopPropagation();
            el.reportValidity();
          }
        },
        { capture: true }
      );
    }
  }

  wire("id_date_naissance");
  wire("r_dob");
})();
