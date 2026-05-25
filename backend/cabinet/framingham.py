"""
Score de risque cardiovasculaire 10 ans — Framingham (ATP-III) pour CHD dur.
Formules de points d’âge, lipides, TA, tabac et diabète (NHLBI) ;
risque estimé d’après le tableau 10 ans par sexe.
Réf. : http://www.nhlbi.nih.gov/health-pro/guidelines/current/cholesterol-guidelines/ (approximation standard).
"""
from __future__ import annotations

import math
from typing import Tuple


def _age_points(age: int, sex: str) -> int:
    if age < 20 or age > 79:
        return 0
    if sex == "M":
        for lo, hi, p in [
            (20, 34, 0),
            (35, 39, 2),
            (40, 44, 5),
            (45, 49, 6),
            (50, 54, 8),
            (55, 59, 10),
            (60, 64, 11),
            (65, 69, 12),
            (70, 74, 14),
        ]:
            if lo <= age <= hi:
                return p
        return 15
    # Femme
    for lo, hi, p in [
        (20, 34, 0),
        (35, 39, 2),
        (40, 44, 4),
        (45, 49, 5),
        (50, 54, 7),
        (55, 59, 8),
        (60, 64, 9),
        (65, 69, 10),
        (70, 74, 12),
    ]:
        if lo <= age <= hi:
            return p
    return 14


def _tc_points(tc: float, sex: str) -> int:
    if sex == "M":
        if tc < 160:
            return 0
        if tc < 200:
            return 0
        if tc < 240:
            return 1
        if tc < 280:
            return 1
        return 2
    if tc < 200:
        return 0
    if tc < 240:
        return 1
    if tc < 280:
        return 2
    return 3


def _hdl_points(hdl: float, sex: str) -> int:
    if hdl < 40:
        return 2 if sex == "M" else 2
    if hdl < 50:
        return 1 if sex == "M" else 1
    if hdl < 60:
        return 0
    return -1 if sex == "F" else -1  # 60+ → -1 les deux (ATP-III M/F légèrement diff — simplif.)


def _sbp_points(sbp: int, tx_hta: bool, sex: str) -> int:
    if sex == "M":
        if not tx_hta:
            for lo, hi, p in [
                (0, 119, 0),
                (120, 129, 0),
                (130, 139, 1),
                (140, 159, 1),
            ]:
                if lo <= sbp <= hi:
                    return p
            return 2 if sbp >= 160 else 0
        for lo, hi, p in [
            (0, 119, 0),
            (120, 129, 1),
            (130, 139, 2),
            (140, 159, 2),
        ]:
            if lo <= sbp <= hi:
                return p
        return 3 if sbp >= 160 else 0
    if not tx_hta:
        for lo, hi, p in [
            (0, 119, 0),
            (120, 129, 1),
            (130, 139, 2),
            (140, 159, 3),
        ]:
            if lo <= sbp <= hi:
                return p
        return 4 if sbp >= 160 else 0
    for lo, hi, p in [
        (0, 119, 0),
        (120, 129, 1),
        (130, 139, 2),
        (140, 159, 2),
    ]:
        if lo <= sbp <= hi:
            return p
    return 2 if sbp >= 160 else 0


def _smoke_points(sex: str, smoking: bool) -> int:
    if not smoking:
        return 0
    return 2 if sex == "M" else 2


def _diab_points(sex: str, diabete: bool) -> int:
    if not diabete:
        return 0
    return 0 if sex == "M" else 4  # Framingham original: diabète surtout côté femme dans score CHD classique


def compute_framingham_points(
    age: int,
    sex: str,
    cholesterol_total: float,
    hdl: float,
    tension_systolique: int,
    traitement_hta: bool,
    tabagisme: bool,
    diabete: bool,
) -> int:
    sex = "M" if sex.upper() == "M" else "F"
    pts = 0
    pts += _age_points(age, sex)
    pts += _tc_points(cholesterol_total, sex)
    pts += _hdl_points(hdl, sex)
    pts += _sbp_points(tension_systolique, traitement_hta, sex)
    pts += _smoke_points(sex, tabagisme)
    pts += _diab_points(sex, diabete)
    return int(max(0, pts))


# Risque CHD 10 ans (%) — table NHLBI simplifiée par points (hommes)
_MEN_RISK = {
    0: 1,
    1: 1,
    2: 1,
    3: 1,
    4: 1,
    5: 2,
    6: 2,
    7: 3,
    8: 4,
    9: 5,
    10: 6,
    11: 8,
    12: 10,
    13: 12,
    14: 16,
    15: 20,
    16: 25,
    17: 30,
}

# Femme
_WOMEN_RISK = {
    0: 0,
    1: 0,
    2: 0,
    3: 0,
    4: 0,
    5: 0,
    6: 0,
    7: 0,
    8: 0,
    9: 0,
    10: 1,
    11: 1,
    12: 1,
    13: 1,
    14: 1,
    15: 1,
    16: 2,
    17: 2,
    18: 2,
    19: 2,
    20: 2,
    21: 3,
    22: 3,
    23: 3,
    24: 4,
    25: 4,
    26: 5,
    27: 5,
    28: 6,
    29: 6,
    30: 6,
    31: 8,
    32: 8,
    33: 10,
    34: 10,
    35: 10,
    36: 12,
    37: 12,
    38: 14,
    39: 14,
    40: 16,
    41: 16,
    42: 18,
    43: 18,
    44: 20,
    45: 20,
    46: 22,
    47: 22,
    48: 25,
    49: 25,
    50: 30,
}


def points_to_10y_risk_percent(
    total_points: int, age: int, sex: str
) -> float:
    """Table NHLBI par point total (risque 10 ans CHD) ; légère pénalisation au-delà des maxima tablés."""
    del age  # réservé si extension future
    sex = "M" if sex.upper() == "M" else "F"
    p = int(max(0, total_points))
    if sex == "M":
        p_tab = min(p, 17)
        r = float(_MEN_RISK.get(p_tab, 30))
        if p > 17:
            r = min(60.0, r + (p - 17) * 0.4)
        return r
    p_tab = min(p, 50)
    r = float(_WOMEN_RISK.get(p_tab, 30))
    if p > 50:
        r = min(60.0, r + (p - 50) * 0.3)
    return r


def niveau_risque(risk_percent: float) -> str:
    if risk_percent < 10:
        return "faible"
    if risk_percent <= 20:
        return "modéré"
    return "élevé"


def compute_framingham_full(
    age: int,
    sex: str,
    cholesterol_total: float,
    hdl: float,
    tension_systolique: int,
    traitement_hta: bool,
    tabagisme: bool,
    diabete: bool,
) -> Tuple[int, float, str]:
    pts = compute_framingham_points(
        age,
        sex,
        cholesterol_total,
        hdl,
        tension_systolique,
        traitement_hta,
        tabagisme,
        diabete,
    )
    risk = points_to_10y_risk_percent(pts, age, sex)
    if not math.isfinite(risk):
        risk = 0.0
    return pts, float(round(risk, 2)), niveau_risque(risk)
