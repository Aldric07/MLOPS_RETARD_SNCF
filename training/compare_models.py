"""Compare plusieurs modèles sur les vraies données SNCF et enregistre chacun dans MLflow.

Usage (sur la VM) :
    docker compose run --rm trainer python compare_models.py

Ne touche pas au modèle en production : les runs vont dans l'expérience
« sncf-comparaison-modeles ». Le résultat est aussi écrit dans
data/resultats_modeles.json et affiché sous forme de tableau.
"""
from __future__ import annotations

import json
import math
import os
import time

import mlflow
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from common.features import CAT_FEATURES, FEATURES, NUM_FEATURES, TARGET, build_training_set, clean, load_raw

DATA_PATH = os.getenv("DATA_PATH", "data/regularite-mensuelle-tgv-aqst.csv")
OUT_PATH = os.getenv("OUT_PATH", "data/resultats_modeles.json")


def pre(scale: bool) -> ColumnTransformer:
    return ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
        ("num", StandardScaler() if scale else "passthrough", NUM_FEATURES),
    ])


MODELS = {
    "Régression linéaire": lambda: Pipeline([("pre", pre(True)), ("model", LinearRegression())]),
    "Random Forest": lambda: Pipeline([("pre", pre(False)), ("model", RandomForestRegressor(
        n_estimators=200, max_depth=15, min_samples_leaf=3, n_jobs=1, random_state=42))]),
    "Gradient Boosting": lambda: Pipeline([("pre", pre(False)), ("model", HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31, l2_regularization=1.0, random_state=42))]),
}


def metrics(y, p) -> dict:
    return {"mae": float(mean_absolute_error(y, p)),
            "rmse": float(math.sqrt(mean_squared_error(y, p))),
            "r2": float(r2_score(y, p))}


def main() -> None:
    history = clean(load_raw(DATA_PATH))
    ds = build_training_set(history)
    cutoff = ds["date"].max() - np.timedelta64(365, "D")
    train, test = ds[ds["date"] <= cutoff], ds[ds["date"] > cutoff]
    print(f"Entraînement : {len(train)} lignes · Test (12 derniers mois) : {len(test)} lignes")

    mlflow.set_experiment("sncf-comparaison-modeles")
    results = []

    # Référence naïve : « le mois prochain = le mois dernier »
    m = metrics(test[TARGET], test["lag_1"])
    with mlflow.start_run(run_name="Méthode naïve (M-1)"):
        mlflow.log_param("modele", "Méthode naïve (M-1)")
        mlflow.log_metrics(m)
    results.append({"modele": "Méthode naïve (M-1)", **m, "temps_s": 0.0})

    for name, make in MODELS.items():
        t0 = time.perf_counter()
        model = make()
        model.fit(train[FEATURES], train[TARGET])
        p = np.clip(model.predict(test[FEATURES]), 0, 100)
        dt = time.perf_counter() - t0
        m = metrics(test[TARGET], p)
        with mlflow.start_run(run_name=name):
            mlflow.log_param("modele", name)
            mlflow.log_metrics({**m, "temps_entrainement_s": dt})
        results.append({"modele": name, **m, "temps_s": round(dt, 1)})

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump({"n_train": len(train), "n_test": len(test), "resultats": results}, f, ensure_ascii=False, indent=2)

    print("\n" + f"{'Modèle':<22}{'MAE':>8}{'RMSE':>8}{'R²':>8}{'Temps (s)':>11}")
    for r in results:
        print(f"{r['modele']:<22}{r['mae']:>8.2f}{r['rmse']:>8.2f}{r['r2']:>8.3f}{r['temps_s']:>11}")
    print(f"\nRésultats enregistrés dans {OUT_PATH} et dans MLflow (expérience sncf-comparaison-modeles).")


if __name__ == "__main__":
    main()
