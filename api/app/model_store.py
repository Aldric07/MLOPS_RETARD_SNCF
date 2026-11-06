"""Chargement du modèle « production » depuis MLflow, avec mise à jour automatique.

Toutes les 60 s, chaque instance de l'API vérifie si l'alias « production »
pointe vers une nouvelle version. Si oui, elle la charge sans redémarrer.
"""
from __future__ import annotations

import logging
import os
import threading
import time

import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.tracking import MlflowClient

log = logging.getLogger("model_store")
MODEL_NAME = os.getenv("MODEL_NAME", "sncf-retards")
ALIAS = "production"
RELOAD_INTERVAL = int(os.getenv("MODEL_RELOAD_INTERVAL", "60"))


class ModelStore:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.model = None
        self.version: str | None = None
        self.groups: dict = {}
        self.reference: pd.DataFrame | None = None

    def load(self) -> bool:
        """Charge la version 'production' si elle a changé. Renvoie True si rechargé."""
        try:
            mv = MlflowClient().get_model_version_by_alias(MODEL_NAME, ALIAS)
            if mv.version == self.version:
                return False
            model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{mv.version}")
            hist = pd.read_csv(mlflow.artifacts.download_artifacts(
                run_id=mv.run_id, artifact_path="history.csv"), parse_dates=["date"])
            ref = pd.read_csv(mlflow.artifacts.download_artifacts(
                run_id=mv.run_id, artifact_path="reference.csv"))
            groups = {k: g.sort_values("date").reset_index(drop=True)
                      for k, g in hist.groupby(["gare_depart", "gare_arrivee"])}
            with self.lock:
                self.model, self.version, self.groups, self.reference = model, mv.version, groups, ref
            log.warning("Modèle %s version %s chargé (%d liaisons)", MODEL_NAME, mv.version, len(groups))
            return True
        except Exception as e:  # noqa: BLE001
            log.warning("Chargement du modèle impossible : %s", e)
            return False

    def snapshot(self):
        with self.lock:
            return self.model, self.version, self.groups, self.reference

    def start_watcher(self) -> None:
        def loop():
            while True:
                time.sleep(RELOAD_INTERVAL)
                self.load()
        threading.Thread(target=loop, daemon=True).start()


store = ModelStore()
