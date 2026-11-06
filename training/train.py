"""Entraînement du modèle de prédiction des retards TGV + enregistrement dans MLflow.

- Télécharge les données SNCF (si absentes)
- Entraîne un modèle Gradient Boosting sur les 12 derniers mois en test
- Enregistre le modèle dans le registre MLflow « sncf-retards »
- Le promeut en « production » seulement s'il est meilleur que le modèle actuel
"""
from __future__ import annotations

import math
import os
import sys
import tempfile
import urllib.request

import mlflow
import mlflow.sklearn
import numpy as np
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

from common.features import (CAT_FEATURES, FEATURES, NUM_FEATURES, TARGET,
                             build_training_set, clean, load_raw)

DATA_URL = os.getenv(
    "DATA_URL",
    "https://ressources.data.sncf.com/api/explore/v2.1/catalog/datasets/"
    "regularite-mensuelle-tgv-aqst/exports/csv?delimiter=%3B",
)
DATA_PATH = os.getenv("DATA_PATH", "data/regularite-mensuelle-tgv-aqst.csv")
MODEL_NAME = os.getenv("MODEL_NAME", "sncf-retards")
ALIAS = "production"
RETRAIN = os.getenv("RETRAIN", "0") == "1"
REFRESH_DATA = os.getenv("REFRESH_DATA", "0") == "1"


def download_data() -> None:
    if os.path.exists(DATA_PATH) and not REFRESH_DATA:
        print(f"Données déjà présentes : {DATA_PATH}")
        return
    os.makedirs(os.path.dirname(DATA_PATH) or ".", exist_ok=True)
    print(f"Téléchargement des données SNCF depuis {DATA_URL}")
    req = urllib.request.Request(DATA_URL, headers={"User-Agent": "sncf-retards-mlops"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r, open(DATA_PATH, "wb") as f:
            f.write(r.read())
    except Exception as e:  # noqa: BLE001
        sys.exit(
            f"Échec du téléchargement ({e}). Télécharge le CSV à la main depuis "
            "data.gouv.fr (Régularité mensuelle TGV par liaisons) et place-le dans "
            f"{DATA_PATH}"
        )


def production_version(client: MlflowClient):
    try:
        return client.get_model_version_by_alias(MODEL_NAME, ALIAS)
    except Exception:  # noqa: BLE001
        return None


def make_model() -> Pipeline:
    pre = ColumnTransformer([
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
        ("num", "passthrough", NUM_FEATURES),
    ])
    reg = HistGradientBoostingRegressor(
        max_iter=400, learning_rate=0.05, max_leaf_nodes=31,
        l2_regularization=1.0, random_state=42,
    )
    return Pipeline([("pre", pre), ("model", reg)])


def main() -> None:
    client = MlflowClient()
    if not RETRAIN and production_version(client) is not None:
        print("Un modèle 'production' existe déjà : pas de réentraînement (RETRAIN=1 pour forcer).")
        return

    download_data()
    history = clean(load_raw(DATA_PATH))
    ds = build_training_set(history)
    print(f"{len(history)} lignes nettoyées, {len(ds)} exemples d'entraînement, "
          f"{history.groupby(['gare_depart', 'gare_arrivee']).ngroups} liaisons")

    cutoff = ds["date"].max() - np.timedelta64(365, "D")
    train, test = ds[ds["date"] <= cutoff], ds[ds["date"] > cutoff]

    mlflow.set_experiment("sncf-retards")
    with mlflow.start_run() as run:
        model = make_model()
        model.fit(train[FEATURES], train[TARGET])
        pred = np.clip(model.predict(test[FEATURES]), 0, 100)

        mae = mean_absolute_error(test[TARGET], pred)
        metrics = {
            "mae": mae,
            "rmse": math.sqrt(mean_squared_error(test[TARGET], pred)),
            "r2": r2_score(test[TARGET], pred),
            # Référence naïve : « le mois prochain = le mois dernier »
            "baseline_mae": mean_absolute_error(test[TARGET], test["lag_1"]),
        }
        mlflow.log_metrics(metrics)
        mlflow.log_params({
            "algo": "HistGradientBoostingRegressor", "max_iter": 400, "learning_rate": 0.05,
            "n_train": len(train), "n_test": len(test),
            "date_max": str(ds["date"].max().date()),
        })
        print("Métriques :", {k: round(v, 3) for k, v in metrics.items()})

        with tempfile.TemporaryDirectory() as tmp:
            history.to_csv(f"{tmp}/history.csv", index=False)
            train[FEATURES].sample(min(3000, len(train)), random_state=42).to_csv(
                f"{tmp}/reference.csv", index=False)
            mlflow.log_artifact(f"{tmp}/history.csv")
            mlflow.log_artifact(f"{tmp}/reference.csv")

        example = train[FEATURES].head(3)
        mlflow.sklearn.log_model(
            model, artifact_path="model",
            signature=infer_signature(example, model.predict(example)),
            registered_model_name=MODEL_NAME,
        )

    version = client.search_model_versions(f"run_id='{run.info.run_id}'")[0].version
    champion = production_version(client)
    promote = True
    if champion is not None:
        champ_mae = client.get_run(champion.run_id).data.metrics.get("mae", float("inf"))
        promote = mae <= champ_mae
        print(f"Champion v{champion.version} MAE={champ_mae:.3f} / challenger v{version} MAE={mae:.3f}")
    if promote:
        client.set_registered_model_alias(MODEL_NAME, ALIAS, version)
        print(f"Version {version} promue en '{ALIAS}'.")
    else:
        print(f"Version {version} enregistrée mais NON promue (moins bonne que la production).")


if __name__ == "__main__":
    main()
