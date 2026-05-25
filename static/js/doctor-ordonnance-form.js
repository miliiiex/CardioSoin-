/**

 * Documents médecin : onglets, synchronisation patient entre formulaires,

 * lignes médicaments, filtrage des RDV.

 */

(function () {

  const TAB_IDS = ["ordo", "bilan", "examens", "cert"];

  const HASH_MAP = {

    "#ordo": "ordo",

    "#bilan": "bilan",

    "#examens": "examens",

    "#exam": "examens",

    "#cert": "cert",

    "#certificat": "cert",

  };



  /* --- Onglets --- */

  const tabButtons = document.querySelectorAll(".doctor-docs-tab[data-tab-target]");

  const panels = document.querySelectorAll(".doctor-docs-panel[data-panel]");



  function showTab(key) {

    if (!TAB_IDS.includes(key)) key = "ordo";

    tabButtons.forEach(function (btn) {

      const on = btn.getAttribute("data-tab-target") === key;

      btn.classList.toggle("is-active", on);

      btn.setAttribute("aria-selected", on ? "true" : "false");

    });

    panels.forEach(function (panel) {

      const on = panel.getAttribute("data-panel") === key;

      panel.classList.toggle("is-active", on);

      panel.toggleAttribute("hidden", !on);

    });

    try {

      history.replaceState(null, "", "#" + (key === "examens" ? "examens" : key));

    } catch (e) {

      /* ignore */

    }

  }



  tabButtons.forEach(function (btn) {

    btn.addEventListener("click", function () {

      showTab(btn.getAttribute("data-tab-target") || "ordo");

    });

  });



  if (tabButtons.length) {

    let initial = "ordo";

    const h = (window.location.hash || "").toLowerCase();

    if (HASH_MAP[h]) initial = HASH_MAP[h];

    showTab(initial);

    window.addEventListener("hashchange", function () {

      const hh = (window.location.hash || "").toLowerCase();

      if (HASH_MAP[hh]) showTab(HASH_MAP[hh]);

    });

  }



  /* --- Lignes médicaments --- */

  const rows = document.getElementById("ordo-med-rows");

  const addBtn = document.getElementById("ordo-med-add");

  if (rows && addBtn) {

    addBtn.addEventListener("click", function () {

      const first = rows.querySelector(".ordo-med-row");

      if (!first) return;

      const clone = first.cloneNode(true);

      clone.querySelectorAll("input, textarea").forEach(function (el) {

        el.value = "";

      });

      rows.appendChild(clone);

    });

  }



  const rawEl = document.getElementById("rdvs-json-data");

  let rdvs = [];

  if (rawEl && rawEl.textContent) {

    try {

      rdvs = JSON.parse(rawEl.textContent);

    } catch (e) {

      rdvs = [];

    }

  }



  function fillRdvSelect(selectEl, patientId) {

    if (!selectEl) return;

    const pid = parseInt(String(patientId), 10);

    const prev = selectEl.value;

    selectEl.innerHTML = "";

    const optNone = document.createElement("option");

    optNone.value = "";

    optNone.textContent = "— Aucun —";

    selectEl.appendChild(optNone);

    if (!pid) return;

    rdvs

      .filter(function (r) {

        return r.patient_id === pid;

      })

      .forEach(function (r) {

        const o = document.createElement("option");

        o.value = String(r.id);

        const st = r.statut ? " (" + r.statut + ")" : "";

        o.textContent = r.label + st;

        selectEl.appendChild(o);

      });

    if (prev && [...selectEl.options].some(function (o) { return o.value === prev; })) {

      selectEl.value = prev;

    }

  }



  function refreshAllRdvsForPatient(patientId) {

    document.querySelectorAll(".doc-form").forEach(function (form) {

      const patientSel = form.querySelector(".doc-patient");

      const rdvSel = form.querySelector(".doc-rdv");

      if (!patientSel || !rdvSel) return;

      fillRdvSelect(rdvSel, patientId);

    });

  }



  document.querySelectorAll(".doc-patient").forEach(function (sel) {

    sel.addEventListener("change", function () {

      const pid = sel.value;

      document.querySelectorAll(".doc-patient").forEach(function (other) {

        if (other !== sel) other.value = pid;

      });

      refreshAllRdvsForPatient(pid);

    });

  });



  document.querySelectorAll(".doc-form").forEach(function (form) {

    const patientSel = form.querySelector(".doc-patient");

    const rdvSel = form.querySelector(".doc-rdv");

    if (!patientSel || !rdvSel) return;

    fillRdvSelect(rdvSel, patientSel.value);

  });



  /* --- Aperçu certificat (rédaction automatique) --- */

  const certApercuBox = document.getElementById("cert-apercu-box");

  const certApercuText = document.getElementById("cert-apercu-text");

  if (certApercuBox && certApercuText) {

    const apercuUrl = certApercuBox.getAttribute("data-apercu-url");

    let certPreviewTimer = null;



    function getCsrfToken() {

      const el = document.querySelector('input[name="csrfmiddlewaretoken"]');

      return el ? el.value : "";

    }



    function refreshCertificatApercu() {

      if (!apercuUrl) return;

      const patientEl = document.getElementById("patient-cert");

      const pid = patientEl ? patientEl.value : "";

      if (!pid) {

        certApercuText.textContent =

          "Sélectionnez un patient pour prévisualiser le certificat.";

        return;

      }

      const fd = new FormData();

      fd.append("cert_patient", pid);

      fd.append(

        "certificat_type",

        (document.getElementById("certificat_type") || {}).value || ""

      );

      fd.append(

        "cert_probleme",

        (document.getElementById("cert_probleme") || {}).value || ""

      );

      fd.append(

        "cert_duree_jours",

        (document.getElementById("cert_duree_jours") || {}).value || ""

      );

      fd.append(

        "cert_date_debut",

        (document.getElementById("cert_date_debut") || {}).value || ""

      );

      fd.append(

        "cert_precisions",

        (document.getElementById("cert_precisions") || {}).value || ""

      );

      const csrf = getCsrfToken();

      if (csrf) fd.append("csrfmiddlewaretoken", csrf);



      certApercuBox.classList.add("is-loading");

      fetch(apercuUrl, {

        method: "POST",

        body: fd,

        credentials: "same-origin",

        headers: { "X-Requested-With": "XMLHttpRequest" },

      })

        .then(function (res) {

          if (!res.ok) throw new Error("aperçu");

          return res.json();

        })

        .then(function (data) {

          certApercuText.textContent = data.texte || "";

        })

        .catch(function () {

          certApercuText.textContent =

            "Impossible de générer l’aperçu. Vérifiez les champs et réessayez.";

        })

        .finally(function () {

          certApercuBox.classList.remove("is-loading");

        });

    }



    function scheduleCertPreview() {

      clearTimeout(certPreviewTimer);

      certPreviewTimer = setTimeout(refreshCertificatApercu, 320);

    }



    document.querySelectorAll(".cert-preview-input").forEach(function (el) {

      el.addEventListener("input", scheduleCertPreview);

      el.addEventListener("change", scheduleCertPreview);

    });



    const patientCert = document.getElementById("patient-cert");

    if (patientCert) {

      patientCert.addEventListener("change", scheduleCertPreview);

    }



    const tabCert = document.getElementById("tab-cert");

    if (tabCert) {

      tabCert.addEventListener("click", function () {

        setTimeout(refreshCertificatApercu, 80);

      });

    }



    scheduleCertPreview();

  }

})();

