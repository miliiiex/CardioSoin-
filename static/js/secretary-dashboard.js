/**
 * CardioSoin — tableau de bord secrétaire (date du jour + calendrier des RDV).
 */
(function () {
  const el = document.getElementById("sdash-date");
  if (el) {
    try {
      el.textContent = new Date().toLocaleDateString("fr-FR", {
        weekday: "long",
        day: "numeric",
        month: "long",
        year: "numeric",
      });
    } catch (_e) {
      el.textContent = "";
    }
  }
})();

(function () {
  const script = document.getElementById("sdash-rdv-dates");
  let marks = [];
  if (script && script.textContent) {
    try {
      marks = JSON.parse(script.textContent);
    } catch (_e) {
      marks = [];
    }
  }
  const markSet = {};
  for (let i = 0; i < marks.length; i++) markSet[marks[i]] = true;

  const grid = document.getElementById("sdash-cal-grid");
  const label = document.getElementById("sdash-cal-label");
  const prev = document.getElementById("sdash-cal-prev");
  const next = document.getElementById("sdash-cal-next");
  const reset = document.getElementById("sdash-cal-reset");
  if (!grid || !label) return;

  const now = new Date();
  let viewY = now.getFullYear();
  let viewM = now.getMonth();
  let selectedIso = null;

  function pad(n) {
    return n < 10 ? "0" + n : "" + n;
  }
  function iso(y, m, d) {
    return y + "-" + pad(m + 1) + "-" + pad(d);
  }

  const apptList = document.getElementById("sdash-appt-list");
  const emptyFilter = document.getElementById("sdash-appt-empty-filter");
  const filterLabel = document.getElementById("sdash-appt-filter-label");

  function filterAppts(isoVal) {
    if (!apptList) return;
    const cards = apptList.querySelectorAll(".sec-dash-appt");
    let n = 0;
    for (let i = 0; i < cards.length; i++) {
      const c = cards[i];
      const show = !isoVal || c.getAttribute("data-date") === isoVal;
      c.style.display = show ? "" : "none";
      if (show) n++;
    }
    if (filterLabel) {
      if (!isoVal) {
        filterLabel.textContent =
          "Tous les autres rendez-vous (hors jour actuel, filtre calendrier)";
      } else {
        try {
          const dt = new Date(isoVal + "T12:00:00");
          filterLabel.textContent =
            "Après sélection dans le calendrier : le " +
            dt.toLocaleDateString("fr-FR", {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            });
        } catch (_e) {
          filterLabel.textContent = "Date sélectionnée";
        }
      }
    }
    if (emptyFilter) {
      emptyFilter.hidden = !(isoVal && n === 0);
    }
  }

  function render() {
    label.textContent = new Date(viewY, viewM, 1).toLocaleDateString(
      "fr-FR",
      { month: "long", year: "numeric" }
    );
    const first = new Date(viewY, viewM, 1);
    const startPad = (first.getDay() + 6) % 7;
    const daysInMonth = new Date(viewY, viewM + 1, 0).getDate();
    grid.innerHTML = "";
    for (let p = 0; p < startPad; p++) {
      const ph = document.createElement("span");
      ph.className = "sec-cal__cell sec-cal__cell--pad";
      grid.appendChild(ph);
    }
    const todayIso = iso(now.getFullYear(), now.getMonth(), now.getDate());
    for (let d = 1; d <= daysInMonth; d++) {
      const cellIso = iso(viewY, viewM, d);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "sec-cal__cell";
      btn.setAttribute("data-date", cellIso);
      btn.textContent = String(d);
      if (cellIso === todayIso) btn.classList.add("sec-cal__cell--today");
      if (markSet[cellIso]) btn.classList.add("sec-cal__cell--mark");
      if (selectedIso && cellIso === selectedIso) {
        btn.classList.add("sec-cal__cell--picked");
      }
      btn.addEventListener("click", function (ev) {
        const isoVal = ev.currentTarget.getAttribute("data-date");
        selectedIso = isoVal;
        filterAppts(isoVal);
        render();
      });
      grid.appendChild(btn);
    }
  }

  function clearFilter() {
    selectedIso = null;
    filterAppts(null);
    render();
  }

  if (prev) {
    prev.addEventListener("click", function () {
      viewM--;
      if (viewM < 0) {
        viewM = 11;
        viewY--;
      }
      render();
    });
  }
  if (next) {
    next.addEventListener("click", function () {
      viewM++;
      if (viewM > 11) {
        viewM = 0;
        viewY++;
      }
      render();
    });
  }
  if (reset) reset.addEventListener("click", clearFilter);
  const emptyBtn = document.getElementById("sdash-appt-empty-btn");
  if (emptyBtn) emptyBtn.addEventListener("click", clearFilter);

  render();
  filterAppts(null);
})();

(function () {
  const form = document.getElementById("sec-cabinet-stat-form");
  const cb = document.getElementById("sec-cabinet-open-switch");
  const hidden = document.getElementById("sec-cabinet-stat-hidden");
  if (!form || !cb || !hidden) return;

  cb.addEventListener("change", function () {
    hidden.value = cb.checked ? "ouvert" : "fermé";
    cb.setAttribute("aria-checked", cb.checked ? "true" : "false");
    cb.disabled = true;
    form.submit();
  });
})();
