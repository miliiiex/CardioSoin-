"""Chemins SVG pour l’aperçu « courbe de risque » sur le bureau médecin."""

from __future__ import annotations

from typing import Any


def _y_display_range(risk_values: list[float]) -> tuple[float, float]:
    """Plage d’affichage : zoom sur les données, pas 0–100 (sinon courbe aplatie)."""
    if not risk_values:
        return 0.0, 100.0
    lo, hi = min(risk_values), max(risk_values)
    if lo == hi:
        m = lo
        margin = 2.0 if m < 5 else max(0.35 * m, 1.0)
        return max(0.0, m - margin), min(100.0, m + margin)
    span = hi - lo
    pad = max(span * 0.18, 0.5, hi * 0.04)
    return max(0.0, lo - pad), min(100.0, hi + pad)


def _fmt_pct(v: float) -> str:
    return f"{v:.1f}".replace(".", ",") + " %"


def build_risk_trend_svg(
    risk_values: list[float],
    x_labels: list[str] | None = None,
    *,
    w: int = 420,
    h: int = 168,
) -> dict[str, Any] | None:
    """
    Ligne lisse (courbes) + aire, avec axe Y (zoom sur les données) et libellés X.
    Y : r_lo (bas) → r_hi (haut) — l’échelle s’adapte pour rendre la tendance visible.
    """
    if not risk_values:
        return None
    n = len(risk_values)
    r_lo, r_hi = _y_display_range(risk_values)
    if r_hi - r_lo < 1e-6:
        r_hi = r_lo + 0.1

    labels: list[str] = (
        [str(x) for x in x_labels]
        if (x_labels and len(x_labels) == n)
        else [str(i + 1) for i in range(n)]
    )

    # Marges minimales : la courbe va de plot_left à (w - plot_right) pour remplir le bloc.
    plot_left, plot_right = 40.0, 4.0
    plot_top, plot_bot = 8.0, 34.0
    y_bottom = h - plot_bot
    y_top = plot_top
    inner_w = w - plot_left - plot_right
    inner_h = y_bottom - y_top

    def y_at_r(r: float) -> float:
        v = min(r_hi, max(r_lo, r))
        return y_bottom - (v - r_lo) / (r_hi - r_lo) * inner_h

    y10 = y_at_r(10.0) if r_lo <= 10.0 <= r_hi else None
    y20 = y_at_r(20.0) if r_lo <= 20.0 <= r_hi else None

    y_ticks: list[dict[str, Any]] = []
    for k in (0, 1, 2):
        frac = k / 2.0
        rp = r_lo + frac * (r_hi - r_lo)
        yp = y_at_r(rp)
        y_ticks.append({"y": round(yp, 2), "text": _fmt_pct(rp)})

    if n == 1:
        # Une seule mesure : ligne et aire sur toute la largeur du tracé (bord à bord du bloc).
        xL = plot_left
        xR = w - plot_right
        y0 = y_at_r(risk_values[0])
        d_line = f"M {xL},{y0} L {xR},{y0}"
        d_area = f"M {xL},{y_bottom} L {xL},{y0} L {xR},{y0} L {xR},{y_bottom} Z"
        xm = (xL + xR) * 0.5
        dots = [{"x": round(xm, 2), "y": round(y0, 2)}]
        x_marks = [{"x": round(xm, 2), "label": (labels[0] if labels else "1")[:20]}]
    else:
        xs = [plot_left + (i * inner_w) / (n - 1) for i in range(n)]
        ys = [y_at_r(r) for r in risk_values]
        pts: list[tuple[float, float]] = list(zip(xs, ys, strict=True))
        d_l = f"M {pts[0][0]},{pts[0][1]}"
        for i in range(1, n):
            a, b = pts[i - 1], pts[i]
            cc = (b[0] - a[0]) * 0.45
            d_l += f" C {a[0] + cc},{a[1]} {b[0] - cc},{b[1]} {b[0]},{b[1]}"
        d_line = d_l
        d_area = d_l + f" L {pts[-1][0]},{y_bottom} L {pts[0][0]},{y_bottom} Z"
        dots = [{"x": round(p[0], 2), "y": round(p[1], 2)} for p in pts]
        x_marks = [
            {"x": round(xs[i], 2), "label": (labels[i] if i < len(labels) else str(i + 1))[:20]}
            for i in range(n)
        ]

    rlo_s = f"{r_lo:.1f}".replace(".", ",")
    rhi_s = f"{r_hi:.1f}".replace(".", ",")
    x_label_y = float(h) - 12.0
    return {
        "d_line": d_line,
        "d_area": d_area,
        "w": w,
        "h": h,
        "y10": y10,
        "y20": y20,
        "show_y10": y10 is not None,
        "show_y20": y20 is not None,
        "y_ticks": y_ticks,
        "x_marks": x_marks,
        "plot_left": round(plot_left, 2),
        "x_right": round(w - plot_right, 2),
        "dots": dots,
        "r_lo": r_lo,
        "r_hi": r_hi,
        "r_lo_s": rlo_s,
        "r_hi_s": rhi_s,
        "y_bottom": round(y_bottom, 2),
        "x_label_y": round(x_label_y, 2),
    }
