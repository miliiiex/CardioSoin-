/**
 * Page score médecin — graphique d’évolution indice ECG, onde, barres d’annotations,
 * appel API « quasi temps réel ».
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";

  function readJsonScript(id) {
    const el = document.getElementById(id);
    if (!el) return null;
    try {
      return JSON.parse(el.textContent);
    } catch (e) {
      return null;
    }
  }

  function drawEcgRiskChart() {
    const chartEl = document.getElementById("ecg-risk-chart");
    if (!chartEl) return;
    const data = readJsonScript("ecg-risk-data");
    const items = (data && data.items) || [];
    if (items.length < 2) {
      chartEl.innerHTML =
        '<p class="score-chart-empty">Au moins <strong>deux</strong> analyses ECG pour l’historique. Lancez des analyses ci-dessous.</p>';
      return;
    }

    const W = 900;
    const H = 260;
    const padL = 46;
    const padR = 22;
    const padT = 18;
    const padB = 46;
    const innerW = W - padL - padR;
    const innerH = H - padT - padB;
    const maxY = 100;

    const xs = (i) => padL + (innerW * i) / (items.length - 1);
    const yAt = (v) => padT + innerH * (1 - v / maxY);
    const ptRisk = items.map((d, i) => ({
      x: xs(i),
      y: yAt(Math.min(100, d.r)),
      r: d.r,
    }));

    function pathThrough(points) {
      if (points.length < 2) return "";
      if (points.length === 2) {
        return `M ${points[0].x} ${points[0].y} L ${points[1].x} ${points[1].y}`;
      }
      const p = points;
      let d = `M ${p[0].x} ${p[0].y}`;
      for (let i = 0; i < p.length - 1; i++) {
        const p0 = p[Math.max(0, i - 1)];
        const p1 = p[i];
        const p2 = p[i + 1];
        const p3 = p[Math.min(p.length - 1, i + 2)];
        const c1x = p1.x + (p2.x - p0.x) / 6;
        const c1y = p1.y + (p2.y - p0.y) / 6;
        const c2x = p2.x - (p3.x - p1.x) / 6;
        const c2y = p2.y - (p3.y - p1.y) / 6;
        d += ` C ${c1x} ${c1y} ${c2x} ${c2y} ${p2.x} ${p2.y}`;
      }
      return d;
    }

    function areaUnder(lineD, lastX, firstX, bottom) {
      return lineD + ` L ${lastX} ${bottom} L ${firstX} ${bottom} Z`;
    }

    const lineRisk = pathThrough(ptRisk);
    const bottomY = padT + innerH;
    const dAreaR = areaUnder(
      lineRisk,
      ptRisk[ptRisk.length - 1].x,
      ptRisk[0].x,
      bottomY
    );
    const y22 = yAt(22);
    const y48 = yAt(48);

    const svg = document.createElementNS(NS, "svg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.setAttribute("class", "score-chart__svg score-chart__svg--saas");
    svg.setAttribute("role", "img");
    svg.setAttribute("aria-label", "Indice ECG dans le temps");

    const th22 = document.createElementNS(NS, "line");
    th22.setAttribute("x1", String(padL));
    th22.setAttribute("x2", String(W - padR));
    th22.setAttribute("y1", String(y22));
    th22.setAttribute("y2", String(y22));
    th22.setAttribute("class", "score-chart__t score-chart__t--10");
    svg.appendChild(th22);
    const th48 = document.createElementNS(NS, "line");
    th48.setAttribute("x1", String(padL));
    th48.setAttribute("x2", String(W - padR));
    th48.setAttribute("y1", String(y48));
    th48.setAttribute("y2", String(y48));
    th48.setAttribute("class", "score-chart__t score-chart__t--20");
    svg.appendChild(th48);

    const aR = document.createElementNS(NS, "path");
    aR.setAttribute("d", dAreaR);
    aR.setAttribute("fill", "rgba(56, 189, 248, 0.25)");
    aR.setAttribute("class", "score-chart__area");
    svg.appendChild(aR);

    const pRi = document.createElementNS(NS, "path");
    pRi.setAttribute("d", lineRisk);
    pRi.setAttribute("fill", "none");
    pRi.setAttribute("stroke", "#38bdf8");
    pRi.setAttribute("stroke-width", "2.5");
    pRi.setAttribute("stroke-linecap", "round");
    svg.appendChild(pRi);

    for (const q of ptRisk) {
      const c = document.createElementNS(NS, "circle");
      c.setAttribute("cx", String(q.x));
      c.setAttribute("cy", String(q.y));
      c.setAttribute("r", "5");
      c.setAttribute("fill", "#0ea5e9");
      svg.appendChild(c);
    }

    const nIt = items.length;
    const xLabMax = nIt <= 8 ? nIt : 7;
    const xLabStep = nIt <= 1 ? 0 : (nIt - 1) / (xLabMax - 1);
    const seenX = new Set();
    for (let j = 0; j < xLabMax; j++) {
      const i = Math.min(nIt - 1, Math.round(j * xLabStep));
      if (seenX.has(i)) continue;
      seenX.add(i);
      const t = document.createElementNS(NS, "text");
      t.setAttribute("x", String(xs(i)));
      t.setAttribute("y", String(H - 12));
      t.setAttribute("text-anchor", "middle");
      t.setAttribute("class", "score-chart__x");
      try {
        const d0 = new Date(items[i].t);
        t.textContent = d0.toLocaleDateString("fr-FR", {
          day: "2-digit",
          month: "short",
        });
      } catch (e) {
        t.textContent = String(i + 1);
      }
      svg.appendChild(t);
    }

    chartEl.innerHTML = "";
    chartEl.appendChild(svg);
  }

  function drawWaveform(samples) {
    const canvas = document.getElementById("ecg-wave-canvas");
    if (!canvas || !samples || !samples.length) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const w = canvas.width;
    const h = canvas.height;
    ctx.fillStyle = "rgba(15, 23, 42, 0.92)";
    ctx.fillRect(0, 0, w, h);
    ctx.strokeStyle = "#5eead4";
    ctx.lineWidth = 1.1;
    ctx.beginPath();
    const mid = h / 2;
    const amp = h * 0.38;
    for (let i = 0; i < samples.length; i++) {
      const x = (i / (samples.length - 1)) * w;
      const y = mid - samples[i] * amp;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.fillStyle = "#94a3b8";
    ctx.font = "12px system-ui,sans-serif";
    ctx.fillText("Onde ECG (normalisée, sous-échantillonnée)", 10, 18);
  }

  function renderBeatBars(counts) {
    const host = document.getElementById("ecg-beat-bars");
    if (!host) return;
    host.innerHTML = "";
    if (!counts || typeof counts !== "object") {
      host.innerHTML =
        '<p class="cs-muted" style="margin:0;">Aucune annotation chargée.</p>';
      return;
    }
    const entries = Object.entries(counts).sort((a, b) => b[1] - a[1]);
    const maxv = Math.max(1, ...entries.map((e) => e[1]));
    for (const [sym, n] of entries.slice(0, 18)) {
      const row = document.createElement("div");
      row.className = "score-ecg-beat-row";
      const lab = document.createElement("span");
      lab.className = "score-ecg-beat-sym";
      lab.textContent = sym || "·";
      const bar = document.createElement("div");
      bar.className = "score-ecg-beat-bar";
      const inner = document.createElement("span");
      inner.style.width = `${(n / maxv) * 100}%`;
      bar.appendChild(inner);
      const num = document.createElement("span");
      num.className = "score-ecg-beat-n";
      num.textContent = String(n);
      row.appendChild(lab);
      row.appendChild(bar);
      row.appendChild(num);
      host.appendChild(row);
    }
  }

  drawEcgRiskChart();
  const wf = readJsonScript("ecg-waveform-data");
  if (wf && Array.isArray(wf)) drawWaveform(wf);
  const bc = readJsonScript("ecg-beat-data");
  if (bc) renderBeatBars(bc);

  const liveBtn = document.getElementById("ecg-analyze-live");
  const statusEl = document.getElementById("ecg-api-status");
  const url = window.CS_ECG_ANALYZE_URL;
  if (!liveBtn || !url) return;

  liveBtn.addEventListener("click", async function () {
    const patientEl = document.getElementById("ecg_patient");
    const recordEl = document.getElementById("mit_record");
    const blendEl = document.getElementById("blend_framingham");
    const tokenInput = document.querySelector(
      ".score-ecg-form input[name=csrfmiddlewaretoken]"
    );
    if (!patientEl || !recordEl || !tokenInput) return;
    if (statusEl) statusEl.textContent = "Analyse en cours…";
    liveBtn.disabled = true;
    try {
      const res = await fetch(url, {
        method: "POST",
        credentials: "same-origin",
        headers: {
          "Content-Type": "application/json",
          "X-CSRFToken": tokenInput.value,
        },
        body: JSON.stringify({
          patient_id: Number(patientEl.value),
          record: recordEl.value,
          blend_framingham: !!(blendEl && blendEl.checked),
          save: true,
        }),
      });
      const payload = await res.json();
      if (!res.ok || !payload.ok) {
        if (statusEl)
          statusEl.textContent =
            (payload && payload.error) || "Erreur lors de l’analyse.";
        return;
      }
      if (statusEl) {
        statusEl.textContent = `Indice ${Number(
          payload.risk_percent
        ).toFixed(1)} % (${payload.niveau}) — enregistrement effectué. Actualisation…`;
      }
      window.location.reload();
    } catch (e) {
      if (statusEl) statusEl.textContent = "Erreur réseau ou serveur.";
    } finally {
      liveBtn.disabled = false;
    }
  });
})();
