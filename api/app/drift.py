"""Détection de data drift : test de Kolmogorov-Smirnov.

On compare la distribution des données reçues en production (dernières
prédictions) à celle des données d'entraînement. Si p-value < 0.05, la
distribution a significativement changé : il y a drift sur cette variable.
"""
from __future__ import annotations

import pandas as pd
from scipy.stats import ks_2samp

from common.features import DRIFT_FEATURES


def compute_drift(reference: pd.DataFrame, current: pd.DataFrame,
                  alpha: float = 0.05, min_samples: int = 30) -> dict:
    if len(current) < min_samples:
        return {"statut": "pas_assez_de_donnees", "n_current": len(current),
                "minimum": min_samples}
    res = {}
    for f in DRIFT_FEATURES:
        r = pd.to_numeric(reference[f], errors="coerce").dropna()
        c = pd.to_numeric(current[f], errors="coerce").dropna()
        stat, p = ks_2samp(r, c)
        res[f] = {"ks_stat": round(float(stat), 4), "p_value": round(float(p), 4),
                  "drift": bool(p < alpha)}
    share = sum(v["drift"] for v in res.values()) / len(res)
    return {"statut": "ok", "n_reference": len(reference), "n_current": len(current),
            "variables": res, "part_variables_en_drift": round(share, 2),
            "drift_global": share >= 0.5}
