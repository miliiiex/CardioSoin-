/**
 * Mon compte : lecture, puis édition au clic sur « Modifier ».
 * data-start-edit="1" sur #paccArea → garder l’édition (erreur serveur).
 * Annuler → rechargement de la page.
 */
(function () {
  const area = document.getElementById("paccArea");
  const view = document.getElementById("paccView");
  const edit = document.getElementById("paccEdit");
  const btnEdit = document.getElementById("paccBtnEdit");
  const btnCancel = document.getElementById("paccBtnCancel");
  if (!area || !view || !edit) return;

  const startEdit = area.getAttribute("data-start-edit") === "1";

  function showView() {
    view.hidden = false;
    edit.hidden = true;
    if (btnEdit) btnEdit.hidden = false;
  }

  function showEdit() {
    view.hidden = true;
    edit.hidden = false;
    if (btnEdit) btnEdit.hidden = true;
  }

  if (startEdit) {
    showEdit();
  } else {
    showView();
  }

  if (btnEdit) {
    btnEdit.addEventListener("click", function () {
      showEdit();
    });
  }

  if (btnCancel) {
    btnCancel.addEventListener("click", function () {
      window.location.assign(window.location.pathname);
    });
  }
})();

(function () {
  const el = document.getElementById("pdash-date");
  if (!el) return;
  try {
    el.textContent = new Date().toLocaleDateString("fr-FR", {
      weekday: "long",
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch (e) {
    el.textContent = "";
  }
})();
