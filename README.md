# 🚄 Prévision des retards TGV — Projet MLOps

Prévoir le **taux de trains en retard à l'arrivée** d'une liaison TGV pour un mois donné,
à partir des données ouvertes SNCF (Régularité mensuelle TGV par liaison).

## Architecture

```
Utilisateur ──► Streamlit (8501) ──► Nginx (8000) ──► API FastAPI × 3 ──► PostgreSQL
                                     répartiteur          │               (clés, usage)
                                                          ▼
                                     Trainer ──────────► MLflow (5000)
                                     (entraînement)      (registre de modèles)
```

| Brique | Rôle |
|---|---|
| `training/` | Télécharge les données, entraîne un Gradient Boosting, l'enregistre dans MLflow, le promeut en *production* s'il bat le modèle actuel |
| `api/` | FastAPI : clé `X-API-Key` obligatoire, suivi d'usage par utilisateur, détection de data drift, rechargement auto du modèle |
| `ui/` | Interface web Streamlit |
| `nginx/` | Répartit la charge entre les 3 copies de l'API (scaling horizontal) |
| `loadtest/` | Test de charge Locust |
| `deploy/` + `.github/workflows/` | Déploiement en une commande ou automatique (CD) sur la VM |
| `terraform/` | Création automatique de la VM Azure |

## Lancer en local (une seule commande)

```bash
cp .env.example .env
docker compose up -d --build
```

- API + documentation : http://localhost:8000/docs
- Interface : http://localhost:8501
- MLflow : http://localhost:5000

## Niveaux couverts

- **0** : tout tourne dans des conteneurs, lancé par `docker compose up`
- **1** : déploiement par commande (`deploy/`) ou pipeline CD (GitHub Actions), clé API, suivi d'usage, test Locust
- **2** : Terraform, interface Streamlit, data drift (test de Kolmogorov-Smirnov), MLflow (versionnement + mise à jour en production)
- **3** : scaling horizontal (3 replicas derrière Nginx), stratégie champion / challenger

## Modèle

- Cible : % de trains en retard à l'arrivée (mois M)
- Variables : liaison, mois, durée du trajet, retards des mois précédents (M-1, M-12, moyennes 3 et 12 mois)
- Algorithme : `HistGradientBoostingRegressor`, test sur les 12 derniers mois
- Comparé à une référence naïve (« même taux que le mois dernier ») dans MLflow
