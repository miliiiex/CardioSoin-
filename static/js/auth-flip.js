/**
 * CardioSoin — onglets Connexion / Inscription (page login).
 */
(function () {
  const card = document.getElementById("medFlip");
  if (!card) return;
  const btnUp = document.getElementById("medBtnRegister");
  const btnIn = document.getElementById("medBtnLogin");
  const panelLogin = document.getElementById("cauth-form-login");
  const panelReg = document.getElementById("cauth-form-reg");

  function setMode(isReg) {
    if (isReg) {
      card.classList.add("is-register");
    } else {
      card.classList.remove("is-register");
    }
    if (btnIn) {
      btnIn.setAttribute("aria-selected", isReg ? "false" : "true");
    }
    if (btnUp) {
      btnUp.setAttribute("aria-selected", isReg ? "true" : "false");
    }
    if (panelLogin) {
      panelLogin.setAttribute("aria-hidden", isReg ? "true" : "false");
    }
    if (panelReg) {
      panelReg.setAttribute("aria-hidden", isReg ? "false" : "true");
    }
  }

  if (btnUp) {
    btnUp.addEventListener("click", function () {
      setMode(true);
    });
  }
  if (btnIn) {
    btnIn.addEventListener("click", function () {
      setMode(false);
    });
  }

  // Recharge la page si elle vient du cache (bfcache) : le jeton CSRF du
  // formulaire ne correspond plus à la session après login/déco dans un autre onglet.
  window.addEventListener("pageshow", function (e) {
    if (e.persisted) {
      window.location.reload();
    }
  });
})();
