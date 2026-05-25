/**
 * Framingham — style tableau SaaS (double aire lissée, grilles, fond clair),
 * proche d’un area chart "smooth" (orange = risque %, violet = points normalisés).
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const chartEl = document.getElementById("framingham-chart");
  if (!chartEl) return;
  const script = document.getElementById("framingham-data");
  if (!script) return;
  let data;
  try {
    data = JSON.parse(script.textContent);
  } catch (e) {
    return;
  }
  const items = (data && data.items) || [];
  if (items.length < 2) {
    chartEl.innerHTML =
      '<p class="score-chart-empty">Enregistrez au moins <strong>deux</strong> scores pour afficher l’évolution (courbe + aires).</p>';
    return;
  }

  const W = 900;
  const H = 280;
  const padL = 46;
  const padR = 22;
  const padT = 18;
  const padB = 46;
  const innerW = W - padL - padR;
  const innerH = H - padT - padB;

  const maxY = 100;
  const rawPts = items.map((d) => (typeof d.p === "number" ? d.p : 0));
  const pMax = Math.max(1, 25, Math.max.apply(null, rawPts) * 1.05);
  const ptsNorm = rawPts.map((p) => Math.min(100, (p / pMax) * 100));

  const xs = (i) => padL + (innerW * i) / (items.length - 1);
  const yAt = (v) => padT + innerH * (1 - v / maxY);
  const ptRisk = items.map((d, i) => ({ x: xs(i), y: yAt(d.r), r: d.r }));
  const ptP = items.map((d, i) => ({ x: xs(i), y: yAt(ptsNorm[i]), p: d.p }));

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
  const lineP = pathThrough(ptP);
  const bottomY = padT + innerH;
  const dAreaP = areaUnder(lineP, ptP[ptP.length - 1].x, ptP[0].x, bottomY);
  const dAreaR = areaUnder(lineRisk, ptRisk[ptRisk.length - 1].x, ptRisk[0].x, bottomY);
  const y10 = yAt(10);
  const y20 = yAt(20);

  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.setAttribute("class", "score-chart__svg score-chart__svg--saas");
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-label", "Risque à 10 ans et points Framingham sur le temps");

  const defs = document.createElementNS(NS, "defs");
  const gradO = makeLinear("saasAreaOrange", "0", "0", "0", "100");
  addStops(gradO, [
    ["0%", "rgba(249, 115, 22, 0.45)"],
    ["55%", "rgba(249, 115, 22, 0.12)"],
    ["100%", "rgba(255, 255, 255, 0)"],
  ]);
  const gradV = makeLinear("saasAreaViolet", "0", "0", "0", "100");
  addStops(gradV, [
    ["0%", "rgba(168, 85, 247, 0.38)"],
    ["50%", "rgba(168, 85, 247, 0.1)"],
    ["100%", "rgba(255, 255, 255, 0)"],
  ]);
  const strokeO = makeLinear("saasStrokeOrange", "0", "0", "100", "0");
  addStops(strokeO, [
    ["0%", "#fb923c"],
    ["50%", "#f97316"],
    ["100%", "#ea580c"],
  ]);
  const strokeV = makeLinear("saasStrokeViolet", "0", "0", "100", "0");
  addStops(strokeV, [
    ["0%", "#a855f7"],
    ["50%", "#9333ea"],
    ["100%", "#7c3aed"],
  ]);
  defs.appendChild(gradO);
  defs.appendChild(gradV);
  defs.appendChild(strokeO);
  defs.appendChild(strokeV);
  svg.appendChild(defs);

  // Grille : horizontale + verticale (pointillé)
  const gridH = 7;
  for (let g = 0; g < gridH; g++) {
    const gy = padT + (innerH * g) / (gridH - 1);
    const gr = document.createElementNS(NS, "line");
    gr.setAttribute("x1", String(padL));
    gr.setAttribute("x2", String(W - padR));
    gr.setAttribute("y1", String(gy));
    gr.setAttribute("y2", String(gy));
    gr.setAttribute("class", "score-chart__g score-chart__g--h");
    svg.appendChild(gr);
  }
  const nIt = items.length;
  const vCount = Math.min(7, nIt);
  const vStep = nIt <= 1 ? 1 : (nIt - 1) / (vCount - 1);
  const seenV = new Set();
  for (let j = 0; j < vCount; j++) {
    const i = Math.min(nIt - 1, Math.round(j * vStep));
    if (seenV.has(i)) continue;
    seenV.add(i);
    const gx = xs(i);
    const gr = document.createElementNS(NS, "line");
    gr.setAttribute("x1", String(gx));
    gr.setAttribute("x2", String(gx));
    gr.setAttribute("y1", String(padT));
    gr.setAttribute("y2", String(padT + innerH));
    gr.setAttribute("class", "score-chart__g score-chart__g--v");
    svg.appendChild(gr);
  }

  const th10 = elLine(padL, W - padR, y10, y10, "score-chart__t score-chart__t--10");
  const th20 = elLine(padL, W - padR, y20, y20, "score-chart__t score-chart__t--20");
  svg.appendChild(th10);
  svg.appendChild(th20);

  const aP = document.createElementNS(NS, "path");
  aP.setAttribute("d", dAreaP);
  aP.setAttribute("fill", "url(#saasAreaViolet)");
  aP.setAttribute("class", "score-chart__area score-chart__area--v");
  svg.appendChild(aP);

  const aR = document.createElementNS(NS, "path");
  aR.setAttribute("d", dAreaR);
  aR.setAttribute("fill", "url(#saasAreaOrange)");
  aR.setAttribute("class", "score-chart__area score-chart__area--o");
  svg.appendChild(aR);

  const pPl = document.createElementNS(NS, "path");
  pPl.setAttribute("d", lineP);
  pPl.setAttribute("fill", "none");
  pPl.setAttribute("stroke", "url(#saasStrokeViolet)");
  pPl.setAttribute("stroke-width", "2.5");
  pPl.setAttribute("stroke-linecap", "round");
  pPl.setAttribute("class", "score-chart__line score-chart__line--v");
  svg.appendChild(pPl);

  const pRi = document.createElementNS(NS, "path");
  pRi.setAttribute("d", lineRisk);
  pRi.setAttribute("fill", "none");
  pRi.setAttribute("stroke", "url(#saasStrokeOrange)");
  pRi.setAttribute("stroke-width", "2.75");
  pRi.setAttribute("stroke-linecap", "round");
  pRi.setAttribute("class", "score-chart__line score-chart__line--o");
  svg.appendChild(pRi);

  for (const q of ptP) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", String(q.x));
    c.setAttribute("cy", String(q.y));
    c.setAttribute("r", "5");
    c.setAttribute("class", "score-chart__pt score-chart__pt--v");
    svg.appendChild(c);
  }
  for (const q of ptRisk) {
    const c = document.createElementNS(NS, "circle");
    c.setAttribute("cx", String(q.x));
    c.setAttribute("cy", String(q.y));
    c.setAttribute("r", "5");
    c.setAttribute("class", "score-chart__pt score-chart__pt--o");
    svg.appendChild(c);
  }

  const nSteps = 5;
  for (let s = 0; s <= nSteps; s++) {
    const val = (maxY * s) / nSteps;
    const yy = yAt(val);
    const t = document.createElementNS(NS, "text");
    t.setAttribute("x", String(8));
    t.setAttribute("y", String(yy + 3));
    t.setAttribute("class", "score-chart__y");
    t.textContent = val === 0 ? "00" : String(Math.round(val));
    svg.appendChild(t);
  }

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
      t.textContent =
        nIt > 12
          ? d0.toLocaleDateString("fr-FR", { month: "short", year: "2-digit" })
          : d0.toLocaleDateString("fr-FR", { month: "short" });
    } catch (e) {
      t.textContent = String(i + 1);
    }
    svg.appendChild(t);
  }

  chartEl.appendChild(svg);

  function makeLinear(id, x1, y1, x2, y2) {
    const g = document.createElementNS(NS, "linearGradient");
    g.setAttribute("id", id);
    g.setAttribute("x1", x1);
    g.setAttribute("y1", y1);
    g.setAttribute("x2", x2);
    g.setAttribute("y2", y2);
    return g;
  }
  function addStops(el, arr) {
    for (const [o, c] of arr) {
      const s = document.createElementNS(NS, "stop");
      s.setAttribute("offset", o);
      s.setAttribute("stop-color", c);
      el.appendChild(s);
    }
  }
  function elLine(x1, x2, y1, y2, cls) {
    const line = document.createElementNS(NS, "line");
    line.setAttribute("x1", String(x1));
    line.setAttribute("x2", String(x2));
    line.setAttribute("y1", String(y1));
    line.setAttribute("y2", String(y2));
    line.setAttribute("class", cls);
    return line;
  }
})();
