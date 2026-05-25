"""
Analyse d’enregistrements WFDB type MIT-BIH (PhysioNet).

L’indice produit est un score pédagogique basé sur les annotations de battements
(PVC, etc.) et la fréquence cardiaque — il ne constitue pas un diagnostic médical
ni un risque d’« arrêt cardiaque » validé cliniquement.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Symboles MIT-BIH / AAMI (simplifié)
PVC_SYMBOLS = frozenset({"V", "E"})
PAC_SYMBOLS = frozenset({"A", "a", "J", "S", "e"})


@dataclass
class ECGAnalysisResult:
    ok: bool
    error: str = ""
    fs: float = 360.0
    duree_s: float = 0.0
    waveform: list[float] = field(default_factory=list)
    beat_counts: dict[str, int] = field(default_factory=dict)
    metrics: dict[str, Any] = field(default_factory=dict)
    risk_ecg_seul: float = 0.0
    risk_percent: float = 0.0
    niveau: str = "faible"

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "error": self.error,
            "fs": self.fs,
            "duree_s": self.duree_s,
            "waveform": self.waveform,
            "beat_counts": self.beat_counts,
            "metrics": self.metrics,
            "risk_ecg_seul": self.risk_ecg_seul,
            "risk_percent": self.risk_percent,
            "niveau": self.niveau,
        }


def _downsample(signal: list[float], max_points: int = 2800) -> list[float]:
    n = len(signal)
    if n <= max_points:
        return [float(x) for x in signal]
    step = max(1, n // max_points)
    out = [float(signal[i]) for i in range(0, n, step)]
    if len(out) > max_points:
        out = out[:max_points]
    return out


def _compute_hr_bpm(samples: list[int], fs: float) -> tuple[float, float]:
    """FC médiane et écart-type (bpm) à partir des indices d’annotations."""
    if len(samples) < 3 or fs <= 0:
        return 0.0, 0.0
    rr_s: list[float] = []
    for a, b in zip(samples, samples[1:]):
        d = (b - a) / fs
        if 0.25 < d < 2.5:
            rr_s.append(d)
    if not rr_s:
        return 0.0, 0.0
    bpm_list = [60.0 / r for r in rr_s]
    bpm_list.sort()
    med = bpm_list[len(bpm_list) // 2]
    mean = sum(bpm_list) / len(bpm_list)
    var = sum((x - mean) ** 2 for x in bpm_list) / max(1, len(bpm_list) - 1)
    std = math.sqrt(var)
    return float(med), float(std)


def _risk_from_signal_features(
    pvc_ratio: float,
    pac_ratio: float,
    hr_med: float,
    hr_std: float,
) -> float:
    """Heuristique 0–100 : plus de PVC / instabilité / extrêmes FC → score plus haut."""
    base = 6.0
    base += min(48.0, 220.0 * pvc_ratio)
    base += min(22.0, 90.0 * pac_ratio)
    if hr_med > 0:
        if hr_med > 105:
            base += min(18.0, (hr_med - 105) * 0.55)
        elif hr_med < 52:
            base += min(18.0, (52 - hr_med) * 0.45)
    base += min(14.0, hr_std * 0.35)
    return float(max(0.0, min(99.0, round(base, 2))))


def _combine_with_framingham(ecg_risk: float, framingham_risk: float | None) -> float:
    if framingham_risk is None or not math.isfinite(framingham_risk):
        return ecg_risk
    w_ecg, w_clin = 0.52, 0.48
    return float(max(0.0, min(99.0, round(w_ecg * ecg_risk + w_clin * framingham_risk, 2))))


def analyze_physionet_mit_record(
    record_id: str,
    *,
    pn_dir: str = "mitdb",
    local_dir: str | Path | None = None,
    framingham_risk_percent: float | None = None,
    waveform_max: int = 2800,
) -> ECGAnalysisResult:
    """
    Lit un enregistrement MIT-BIH via wfdb (PhysioNet en ligne ou copie locale).
    """
    try:
        import numpy as np
        import wfdb  # type: ignore[import-untyped]
    except ImportError:
        return ECGAnalysisResult(
            ok=False,
            error="Les paquets « numpy » et « wfdb » sont requis. Ex. : pip install numpy wfdb",
        )

    record_id = (record_id or "").strip()
    if not record_id or not record_id.replace("_", "").isalnum():
        return ECGAnalysisResult(ok=False, error="Identifiant d’enregistrement invalide.")

    try:
        if local_dir:
            rec = wfdb.rdrecord(str(Path(local_dir) / record_id))
        else:
            rec = wfdb.rdrecord(record_id, pn_dir=pn_dir)
    except Exception as e:
        return ECGAnalysisResult(
            ok=False,
            error=f"Lecture WFDB impossible ({e}). Vérifiez la connexion PhysioNet ou un dossier local.",
        )

    fs = float(rec.fs) if rec.fs else 360.0
    sig = getattr(rec, "p_signal", None)
    if sig is None and getattr(rec, "d_signal", None) is not None:
        sig = np.asarray(rec.d_signal, dtype=np.float64)
    else:
        sig = np.asarray(rec.p_signal, dtype=np.float64)
    if sig is None or sig.size == 0:
        return ECGAnalysisResult(ok=False, error="Signal vide.")

    # Premier canal (souvent MLII sur MIT-BIH)
    ch0 = sig[:, 0].astype("float64")
    n = ch0.shape[0]
    duree = float(n / fs) if fs else 0.0
    ch0 = ch0 - float(ch0.mean())
    std = float(ch0.std()) or 1.0
    ch0_norm = (ch0 / std).tolist()
    waveform = _downsample(ch0_norm, waveform_max)

    beat_counts: dict[str, int] = {}
    hr_med, hr_std = 0.0, 0.0
    ann_symbols: list[str] = []

    try:
        if local_dir:
            ann = wfdb.rdann(str(Path(local_dir) / record_id), "atr")
        else:
            ann = wfdb.rdann(record_id, "atr", pn_dir=pn_dir)
        ann_symbols = [str(s) for s in ann.symbol if s]
        beat_counts = dict(Counter(ann_symbols))
        hr_med, hr_std = _compute_hr_bpm(list(ann.sample), fs)
    except Exception:
        pass

    n_beats = sum(beat_counts.values()) or 1
    pvc = sum(beat_counts.get(s, 0) for s in PVC_SYMBOLS)
    pac = sum(beat_counts.get(s, 0) for s in PAC_SYMBOLS)
    pvc_ratio = pvc / n_beats
    pac_ratio = pac / n_beats

    risk_ecg = _risk_from_signal_features(pvc_ratio, pac_ratio, hr_med, hr_std)
    risk_final = _combine_with_framingham(risk_ecg, framingham_risk_percent)
    # Seuils pour l’indice ECG (0–100), distincts du risque CHD Framingham
    if risk_final < 22:
        niv = "faible"
    elif risk_final <= 48:
        niv = "modéré"
    else:
        niv = "élevé"

    metrics: dict[str, Any] = {
        "hr_median_bpm": hr_med,
        "hr_std_bpm": round(hr_std, 2),
        "pvc_ratio": round(pvc_ratio, 4),
        "pac_ratio": round(pac_ratio, 4),
        "n_beats_annotated": n_beats,
        "framingham_blend": framingham_risk_percent is not None,
        "framingham_risk_used": framingham_risk_percent,
    }

    return ECGAnalysisResult(
        ok=True,
        fs=fs,
        duree_s=round(duree, 2),
        waveform=waveform,
        beat_counts=beat_counts,
        metrics=metrics,
        risk_ecg_seul=risk_ecg,
        risk_percent=risk_final,
        niveau=niv,
    )

