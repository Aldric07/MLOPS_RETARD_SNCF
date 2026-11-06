"""Fonctions partagées entre l'entraînement et l'API.

Le jeu de données SNCF « Régularité mensuelle TGV par liaison » contient
26 colonnes. On les renomme par position pour ne pas dépendre des accents
ou des libellés exacts de l'export.
"""
from __future__ import annotations

import pandas as pd

RAW_COLUMNS = [
    "date", "service", "gare_depart", "gare_arrivee", "duree_moyenne",
    "nb_prevus", "nb_annules", "comment_annulations",
    "nb_retard_depart", "retard_moy_retard_depart", "retard_moy_tous_depart",
    "comment_depart",
    "nb_retard_arrivee", "retard_moy_retard_arrivee", "retard_moy_tous_arrivee",
    "comment_arrivee",
    "nb_retard_15", "retard_moy_15", "nb_retard_30", "nb_retard_60",
    "prct_externe", "prct_infra", "prct_trafic", "prct_materiel",
    "prct_gare", "prct_voyageurs",
]

CAT_FEATURES = ["gare_depart", "gare_arrivee", "service"]
NUM_FEATURES = [
    "mois", "annee", "duree_moyenne", "nb_circulant",
    "lag_1", "lag_12", "moy_3", "moy_12", "nb_mois_historique",
]
FEATURES = CAT_FEATURES + NUM_FEATURES
DRIFT_FEATURES = ["mois", "duree_moyenne", "nb_circulant", "lag_1", "moy_3", "moy_12"]
TARGET = "taux_retard"  # % de trains en retard à l'arrivée


def _num(s: pd.Series) -> pd.Series:
    return pd.to_numeric(
        s.astype(str).str.replace(",", ".", regex=False).str.strip(), errors="coerce"
    )


def load_raw(path: str) -> pd.DataFrame:
    """Lit le CSV SNCF (séparateur ';' ou ',') et renomme les colonnes."""
    df = pd.read_csv(path, sep=";", dtype=str, encoding="utf-8-sig")
    if df.shape[1] < 26:
        df = pd.read_csv(path, sep=",", dtype=str, encoding="utf-8-sig")
    if df.shape[1] < 26:
        raise ValueError(f"Format inattendu : {df.shape[1]} colonnes au lieu de 26")
    df = df.iloc[:, :26].copy()
    df.columns = RAW_COLUMNS
    return df


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Nettoie les données et calcule la cible : taux de retard mensuel par liaison."""
    out = pd.DataFrame()
    out["date"] = pd.to_datetime(df["date"].astype(str).str[:7], format="%Y-%m", errors="coerce")
    for c in ["gare_depart", "gare_arrivee", "service"]:
        out[c] = df[c].astype(str).str.strip().str.upper()
    for c in ["duree_moyenne", "nb_prevus", "nb_annules", "nb_retard_arrivee"]:
        out[c] = _num(df[c])
    out["nb_annules"] = out["nb_annules"].fillna(0)
    out = out.dropna(subset=["date", "duree_moyenne", "nb_prevus", "nb_retard_arrivee"])
    out = out[(out["gare_depart"] != "0") & (out["gare_arrivee"] != "0")]
    out["nb_circulant"] = out["nb_prevus"] - out["nb_annules"]
    out = out[out["nb_circulant"] > 0]

    out = (
        out.groupby(["date", "gare_depart", "gare_arrivee"], as_index=False)
        .agg(service=("service", "first"), duree_moyenne=("duree_moyenne", "mean"),
             nb_circulant=("nb_circulant", "sum"), nb_retard_arrivee=("nb_retard_arrivee", "sum"))
    )
    out[TARGET] = (100 * out["nb_retard_arrivee"] / out["nb_circulant"]).clip(0, 100)
    cols = ["date", "gare_depart", "gare_arrivee", "service", "duree_moyenne", "nb_circulant", TARGET]
    return out[cols].sort_values(["gare_depart", "gare_arrivee", "date"]).reset_index(drop=True)


def features_from_past(past: pd.DataFrame, target_date: pd.Timestamp,
                       gare_depart: str, gare_arrivee: str) -> dict | None:
    """Construit les variables d'entrée pour prédire le mois `target_date`.

    `past` = historique de la liaison, strictement avant `target_date`, trié par date.
    Utilisée à l'identique pendant l'entraînement et dans l'API.
    """
    if past.empty:
        return None
    taux = past.set_index("date")[TARGET]
    last = past.iloc[-1]
    prev1 = target_date - pd.DateOffset(months=1)
    prev12 = target_date - pd.DateOffset(months=12)
    return {
        "gare_depart": gare_depart,
        "gare_arrivee": gare_arrivee,
        "service": last["service"],
        "mois": int(target_date.month),
        "annee": int(target_date.year),
        "duree_moyenne": float(last["duree_moyenne"]),
        "nb_circulant": float(last["nb_circulant"]),
        "lag_1": float(taux.get(prev1, taux.iloc[-1])),
        "lag_12": float(taux.get(prev12, taux.mean())),
        "moy_3": float(taux.iloc[-3:].mean()),
        "moy_12": float(taux.iloc[-12:].mean()),
        "nb_mois_historique": int(len(taux)),
    }


def build_training_set(history: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par (liaison, mois) avec les variables calculées sur le passé."""
    rows = []
    for (gd, ga), g in history.groupby(["gare_depart", "gare_arrivee"]):
        g = g.sort_values("date").reset_index(drop=True)
        for i in range(1, len(g)):
            f = features_from_past(g.iloc[:i], g.loc[i, "date"], gd, ga)
            f[TARGET] = float(g.loc[i, TARGET])
            f["date"] = g.loc[i, "date"]
            rows.append(f)
    return pd.DataFrame(rows)


def niveau(taux: float) -> str:
    if taux < 10:
        return "faible"
    if taux < 20:
        return "moyen"
    return "élevé"
