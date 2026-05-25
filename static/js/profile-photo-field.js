/**
 * Met à jour le libellé du fichier choisi pour .prof-photo (staff + patient).
 */
(function () {
  document.querySelectorAll(".prof-photo__native").forEach(function (input) {
    const id = input.id;
    if (!id) return;
    const nameEl = document.getElementById(id + "_filename");
    if (!nameEl) return;
    const placeholder = nameEl.getAttribute("data-placeholder") || "Aucune image sélectionnée";
    const hadCurrent = nameEl.getAttribute("data-has-current") === "1";

    input.addEventListener("change", function () {
      const f = input.files && input.files[0];
      if (f) {
        nameEl.textContent = f.name;
      } else if (hadCurrent) {
        nameEl.textContent = "Photo actuelle";
      } else {
        nameEl.textContent = placeholder;
      }
    });
  });
})();
