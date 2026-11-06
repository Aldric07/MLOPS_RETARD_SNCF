"""API de prédiction des retards TGV.

Sécurité : chaque appel doit envoyer une clé dans le header `X-API-Key`.
Les routes /admin/* demandent le header `X-Admin-Token`.
Chaque appel est enregistré en base (suivi d'usage par utilisateur).
"""
from __future__ import annotations

import logging
import os
import secrets
import socket
import time
from contextlib import asynccontextmanager

import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field

from app import db
from app.drift import compute_drift
from app.model_store import store
from common.features import FEATURES, TARGET, features_from_past, niveau

logging.basicConfig(level=logging.INFO)
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
INSTANCE = socket.gethostname()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
admin_header = APIKeyHeader(name="X-Admin-Token", auto_error=False)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_pool()
    store.load()
    store.start_watcher()
    yield
    db.close_pool()


app = FastAPI(title="API Retards TGV SNCF", version="1.0", lifespan=lifespan,
              description="Prévision du taux de retard mensuel d'une liaison TGV.")


@app.middleware("http")
async def add_instance_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Instance"] = INSTANCE  # montre quel conteneur a répondu
    return response


# ---------- Sécurité ----------
def require_user(key: str | None = Depends(api_key_header)) -> dict:
    if not key:
        raise HTTPException(401, "Clé API manquante : ajoute le header X-API-Key")
    user = db.get_user_by_key(key)
    if not user:
        raise HTTPException(403, "Clé API invalide")
    return user


def require_admin(token: str | None = Depends(admin_header)) -> None:
    if not ADMIN_TOKEN or not secrets.compare_digest(token or "", ADMIN_TOKEN):
        raise HTTPException(403, "Token admin invalide")


# ---------- Schémas ----------
class PredictIn(BaseModel):
    gare_depart: str = Field(..., examples=["PARIS LYON"])
    gare_arrivee: str = Field(..., examples=["MARSEILLE ST CHARLES"])
    annee: int = Field(..., ge=2015, le=2035, examples=[2026])
    mois: int = Field(..., ge=1, le=12, examples=[12])


class UserIn(BaseModel):
    nom: str = Field(..., min_length=2, max_length=60)


# ---------- Routes publiques ----------
@app.get("/health")
def health():
    _, version, groups, _ = store.snapshot()
    return {"status": "ok", "model_loaded": version is not None, "model_version": version,
            "liaisons": len(groups), "instance": INSTANCE}


# ---------- Routes utilisateur ----------
@app.get("/liaisons")
def liaisons(user: dict = Depends(require_user)):
    t0 = time.perf_counter()
    _, version, groups, _ = store.snapshot()
    data = [{"gare_depart": gd, "gare_arrivee": ga,
             "dernier_mois": str(g["date"].max().date())} for (gd, ga), g in groups.items()]
    db.log_usage(user["id"], "/liaisons", 200, (time.perf_counter() - t0) * 1000,
                 model_version=version, instance=INSTANCE)
    return {"nombre": len(data), "liaisons": data}


@app.post("/predict")
def predict(body: PredictIn, user: dict = Depends(require_user)):
    t0 = time.perf_counter()
    model, version, groups, _ = store.snapshot()
    status, feats, pred = 200, None, None
    try:
        if model is None:
            status = 503
            raise HTTPException(503, "Aucun modèle en production pour le moment")
        key = (body.gare_depart.strip().upper(), body.gare_arrivee.strip().upper())
        g = groups.get(key)
        if g is None:
            status = 404
            raise HTTPException(404, "Liaison inconnue (voir GET /liaisons)")
        target = pd.Timestamp(year=body.annee, month=body.mois, day=1)
        feats = features_from_past(g[g["date"] < target], target, *key)
        if feats is None:
            status = 404
            raise HTTPException(404, "Pas d'historique avant ce mois pour cette liaison")
        pred = float(np.clip(model.predict(pd.DataFrame([feats])[FEATURES])[0], 0, 100))
        hist = g[g["date"] < target].tail(12)
        return {
            "liaison": f"{key[0]} → {key[1]}",
            "mois_prevu": f"{body.annee}-{body.mois:02d}",
            "taux_retard_prevu_pct": round(pred, 2),
            "niveau": niveau(pred),
            "historique_12_mois": [{"mois": str(d.date())[:7], "taux_retard_pct": round(float(t), 2)}
                                   for d, t in zip(hist["date"], hist[TARGET])],
            "model_version": version,
            "instance": INSTANCE,
        }
    finally:
        db.log_usage(user["id"], "/predict", status, (time.perf_counter() - t0) * 1000,
                     features=feats, prediction=pred, model_version=version, instance=INSTANCE)


@app.get("/usage/me")
def my_usage(user: dict = Depends(require_user)):
    return {"utilisateur": user["name"], **db.usage_for_user(user["id"])}


# ---------- Routes admin ----------
@app.post("/admin/users", dependencies=[Depends(require_admin)])
def create_user(body: UserIn):
    key = "sk_" + secrets.token_urlsafe(24)
    uid = db.create_user(body.nom, key)
    return {"user_id": uid, "nom": body.nom, "api_key": key,
            "attention": "Note cette clé : elle n'est affichée qu'une seule fois."}


@app.get("/admin/usage", dependencies=[Depends(require_admin)])
def all_usage():
    return {"utilisateurs": db.usage_all()}


@app.get("/admin/drift", dependencies=[Depends(require_admin)])
def drift(limit: int = 500):
    _, version, _, reference = store.snapshot()
    if reference is None:
        raise HTTPException(503, "Aucun modèle chargé")
    current = pd.DataFrame(db.recent_features(limit))
    return {"model_version": version, **compute_drift(reference, current)}


@app.post("/admin/reload", dependencies=[Depends(require_admin)])
def reload_model():
    changed = store.load()
    return {"recharge": changed, "model_version": store.snapshot()[1], "instance": INSTANCE}
