/**

 * Envoi / validation de codes e-mail (inscription, changement MDP en 2 étapes).

 */

(function () {

  function getCsrf() {

    const inp = document.querySelector("[name=csrfmiddlewaretoken]");

    if (inp && inp.value) return inp.value;

    const m = document.cookie.match(/csrftoken=([^;]+)/);

    return m ? decodeURIComponent(m[1]) : "";

  }



  function setStatus(box, text, ok) {

    const el = box.querySelector("[data-email-status]");

    if (!el) return;

    const msg = text || "";

    if (!ok && msg.indexOf("http://") !== -1) {

      el.innerHTML = msg.replace(

        /(https?:\/\/[^\s]+)/g,

        '<a href="$1" target="_blank" rel="noopener">$1</a>'

      );

    } else {

      el.textContent = msg;

    }

    el.classList.toggle("is-ok", !!ok);

    el.classList.toggle("is-err", msg && !ok);

  }



  function resolveEmail(box) {

    const pwdEmail = box.querySelector("[data-pwd-verify-email]");

    if (pwdEmail) return (pwdEmail.value || "").trim();

    const profile = box.getAttribute("data-profile-email");

    if (profile) return profile.trim();

    const sel = box.getAttribute("data-email-input");

    if (sel) {

      const input = document.querySelector(sel);

      if (input) return (input.value || "").trim();

    }

    return "";

  }



  function showPasswordStep(box) {

    const stepVerify = box.querySelector("[data-pwd-step-verify]");

    const stepPassword = box.querySelector("[data-pwd-step-password]");

    if (!stepPassword) return;

    if (stepVerify) stepVerify.hidden = true;

    stepPassword.hidden = false;

    const first = stepPassword.querySelector("input");

    if (first) first.focus();

  }



  document.querySelectorAll("[data-email-verify]").forEach(function (box) {

    const sendUrl = box.getAttribute("data-send-url");

    const confirmUrl = box.getAttribute("data-confirm-url");

    const purpose = box.getAttribute("data-purpose");

    const sendBtn = box.querySelector("[data-email-send]");

    const confirmBtn = box.querySelector("[data-email-confirm]");

    const codeInput = box.querySelector("[data-email-code]");



    if (!sendUrl || !confirmUrl || !purpose) return;



    if (sendBtn) {

      sendBtn.addEventListener("click", function () {

        const email = resolveEmail(box);

        if ((purpose === "register" || purpose === "change_password") && !email) {

          setStatus(box, "Saisissez d'abord une adresse e-mail.", false);

          return;

        }

        const fd = new FormData();

        fd.append("purpose", purpose);

        if (email) fd.append("email", email);

        const csrf = getCsrf();

        if (csrf) fd.append("csrfmiddlewaretoken", csrf);



        sendBtn.disabled = true;

        setStatus(box, "Envoi en cours…", false);



        fetch(sendUrl, {

          method: "POST",

          body: fd,

          credentials: "same-origin",

          headers: { "X-Requested-With": "XMLHttpRequest" },

        })

          .then(function (r) {

            return r.json();

          })

          .then(function (data) {

            setStatus(box, data.message || "", !!data.ok);

          })

          .catch(function () {

            setStatus(box, "Erreur réseau. Réessayez.", false);

          })

          .finally(function () {

            sendBtn.disabled = false;

          });

      });

    }



    if (confirmBtn && codeInput) {

      confirmBtn.addEventListener("click", function () {

        const email = resolveEmail(box);

        const code = (codeInput.value || "").trim();

        if (!email && purpose === "change_password") {

          setStatus(box, "Saisissez l'adresse e-mail.", false);

          return;

        }

        if (!code) {

          setStatus(box, "Saisissez le code reçu.", false);

          return;

        }

        const fd = new FormData();

        fd.append("purpose", purpose);

        fd.append("code", code);

        if (email) fd.append("email", email);

        const csrf = getCsrf();

        if (csrf) fd.append("csrfmiddlewaretoken", csrf);



        confirmBtn.disabled = true;

        fetch(confirmUrl, {

          method: "POST",

          body: fd,

          credentials: "same-origin",

          headers: { "X-Requested-With": "XMLHttpRequest" },

        })

          .then(function (r) {

            return r.json();

          })

          .then(function (data) {

            setStatus(box, data.message || "", !!data.ok);

            if (data.ok) {

              box.classList.add("is-verified");

              if (purpose === "change_password" && box.hasAttribute("data-password-wizard")) {

                showPasswordStep(box);

              }

            }

          })

          .catch(function () {

            setStatus(box, "Erreur réseau. Réessayez.", false);

          })

          .finally(function () {

            confirmBtn.disabled = false;

          });

      });

    }

  });

})();


