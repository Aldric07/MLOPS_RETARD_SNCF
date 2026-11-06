# Guide pas à pas — Projet MLOps Retards TGV

Chaque commande est donnée pour **Mac** (Terminal) et **Windows** (PowerShell). Sous chaque commande : ce qu'elle fait, en une phrase.

---

## Étape 0 — Installer les outils (15 min)

**Mac**
```bash
brew install git python@3.11
```
Installe Git (gestion du code) et Python 3.11.

Puis installe **Docker Desktop** depuis https://www.docker.com/products/docker-desktop et lance-le.

**Windows**
```powershell
winget install Git.Git
winget install Python.Python.3.11
winget install Docker.DockerDesktop
```
Installe Git, Python 3.11 et Docker Desktop. Redémarre le PC, puis lance Docker Desktop (il doit afficher « Engine running »).

**Vérifier (Mac et Windows)**
```bash
git --version
docker --version
docker compose version
```
Affiche les versions : si les 3 commandes répondent, tout est installé.

---

## Étape 1 — Créer le repository GitHub (5 min)

1. Sur github.com → **New repository** → nom : `sncf-retards-mlops` → **Public** → ne coche rien → **Create**.

2. Récupère le repo sur ton PC :

**Mac**
```bash
cd ~/Documents
git clone https://github.com/Aldric07/sncf-retards-mlops.git
cd sncf-retards-mlops
```
**Windows**
```powershell
cd $HOME\Documents
git clone https://github.com/Aldric07/sncf-retards-mlops.git
cd sncf-retards-mlops
```
Va dans Documents, télécharge le repo vide, puis entre dedans.

3. Copie le code du projet (le fichier zip) dans ce dossier :

**Mac**
```bash
unzip ~/Downloads/sncf-retards-mlops.zip -d .
```
**Windows**
```powershell
Expand-Archive $HOME\Downloads\sncf-retards-mlops.zip -DestinationPath . -Force
```
Décompresse le zip dans le dossier du repo.

4. Envoie le code sur GitHub (identique Mac et Windows) :
```bash
git add .
git commit -m "Projet MLOps retards TGV"
git branch -M main
git push -u origin main
```
`add` prépare tous les fichiers, `commit` les enregistre avec un message, `branch -M main` nomme la branche « main », `push` les envoie sur GitHub.

---

## Étape 2 — Lancer tout le système en local : Niveau 0 (10 min)

**Mac**
```bash
cp .env.example .env
```
**Windows**
```powershell
copy .env.example .env
```
Crée le fichier de configuration (mots de passe) à partir du modèle.

**Mac et Windows**
```bash
docker compose up -d --build
```
Construit les images et lance **tous les conteneurs** en arrière-plan : PostgreSQL, MLflow, entraînement, 3 API, Nginx, interface. C'est la « commande unique » du niveau 0. La première fois : 5 à 10 min.

```bash
docker compose ps
```
Liste les conteneurs et leur état. Tu dois voir `api` ×3, `nginx`, `ui`, `mlflow`, `postgres` en « running » et `trainer` en « exited (0) » (il a fini d'entraîner).

```bash
docker compose logs trainer
```
Affiche ce qu'a fait l'entraînement : nombre de liaisons, scores (MAE, R²), « Version 1 promue en 'production' ».

Ouvre dans ton navigateur :
- http://localhost:8000/docs → documentation de l'API
- http://localhost:8501 → interface web
- http://localhost:5000 → MLflow (modèles et métriques)

> **Si l'entraînement échoue au téléchargement** : télécharge le CSV « Régularité mensuelle TGV par liaisons » sur data.gouv.fr, renomme-le `regularite-mensuelle-tgv-aqst.csv`, mets-le dans le dossier `data/`, puis relance `docker compose up -d`.

---

## Étape 3 — Créer une clé API et tester la sécurité (5 min)

Le token admin est celui du fichier `.env` (par défaut `change-moi-admin`).

**Créer un utilisateur et sa clé**

Mac
```bash
curl -X POST http://localhost:8000/admin/users -H "X-Admin-Token: change-moi-admin" -H "Content-Type: application/json" -d '{"nom":"yoann"}'
```
Windows
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/admin/users -Headers @{"X-Admin-Token"="change-moi-admin"} -ContentType "application/json" -Body '{"nom":"yoann"}'
```
Crée l'utilisateur « yoann » et renvoie sa clé `sk_...`. **Copie-la**, elle n'est affichée qu'une fois.

**Appel sans clé → refusé (preuve de sécurité)**

Mac
```bash
curl http://localhost:8000/liaisons
```
Windows
```powershell
Invoke-RestMethod http://localhost:8000/liaisons
```
Renvoie une erreur 401 « Clé API manquante ».

**Prédiction avec la clé**

Mac
```bash
curl -X POST http://localhost:8000/predict -H "X-API-Key: TA_CLE" -H "Content-Type: application/json" -d '{"gare_depart":"PARIS LYON","gare_arrivee":"MARSEILLE ST CHARLES","annee":2026,"mois":12}'
```
Windows
```powershell
Invoke-RestMethod -Method Post -Uri http://localhost:8000/predict -Headers @{"X-API-Key"="TA_CLE"} -ContentType "application/json" -Body '{"gare_depart":"PARIS LYON","gare_arrivee":"MARSEILLE ST CHARLES","annee":2026,"mois":12}'
```
Demande le taux de retard prévu pour Paris → Marseille en décembre 2026. Si la liaison n'existe pas, appelle d'abord `/liaisons` pour voir les noms exacts.

**Voir ton usage (suivi par utilisateur)**

Mac
```bash
curl http://localhost:8000/usage/me -H "X-API-Key: TA_CLE"
```
Windows
```powershell
Invoke-RestMethod http://localhost:8000/usage/me -Headers @{"X-API-Key"="TA_CLE"}
```
Affiche le nombre d'appels et les derniers appels de cet utilisateur (stockés dans PostgreSQL).

Tu peux aussi tout faire depuis l'interface http://localhost:8501 : colle la clé dans la barre de gauche.

---

## Étape 4 — Créer la VM

Deux options. **B rapporte des points au niveau 2** ; si tu manques de temps, fais **A**.

### Option A — VM créée à la main (portail Azure)
1. portal.azure.com → **Machines virtuelles** → **Créer**.
2. Image **Ubuntu 22.04**, taille **Standard_B2s**, authentification **clé SSH**, utilisateur `azureuser`. Télécharge la clé `.pem` proposée.
3. Onglet Réseau : ouvre les ports **22, 8000, 8501, 5000**.
4. Crée, puis note l'**IP publique**.

### Option B — VM créée par Terraform (niveau 2)

**Installer Terraform et Azure CLI**

Mac
```bash
brew tap hashicorp/tap && brew install hashicorp/tap/terraform azure-cli
```
Windows
```powershell
winget install Hashicorp.Terraform
winget install Microsoft.AzureCLI
```
Installe Terraform (crée l'infrastructure par du code) et l'outil en ligne de commande Azure. Sous Windows, ferme et rouvre PowerShell après.

**Créer une clé SSH (Mac et Windows)**
```bash
ssh-keygen -t ed25519
```
Crée une paire de clés pour te connecter à la VM sans mot de passe. Appuie sur Entrée à chaque question.

**Se connecter à Azure**
```bash
az login
az account show --query id -o tsv
```
Ouvre le navigateur pour te connecter, puis affiche l'ID de ta souscription : copie-le.

**Configurer Terraform**

Mac
```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
```
Windows
```powershell
cd terraform
copy terraform.tfvars.example terraform.tfvars
```
Ouvre `terraform.tfvars` et remplis : l'ID de souscription, l'URL de ton repo. Sous Windows, mets `ssh_public_key_path = "C:/Users/TON_NOM/.ssh/id_ed25519.pub"`.

**Créer la VM (Mac et Windows)**
```bash
terraform init
terraform apply
```
`init` télécharge le plugin Azure ; `apply` affiche ce qui va être créé : tape `yes`. Au bout de 2 min, il affiche `public_ip`. Attends encore 3 min (installation automatique de Docker et clonage du repo).

```bash
cd ..
```
Revient à la racine du projet.

---

## Étape 5 — Installer le projet sur la VM (10 min)

**Se connecter à la VM**

Option B (Terraform), Mac et Windows :
```bash
ssh azureuser@IP_DE_LA_VM
```
Option A (clé .pem du portail) :
```bash
ssh -i ~/Downloads/ta-cle.pem azureuser@IP_DE_LA_VM
```
Ouvre un terminal **sur la VM**. Les commandes suivantes sont tapées sur la VM (Linux), donc identiques pour tous.

**Option A seulement** (avec Terraform c'est déjà fait) :
```bash
sudo apt update && sudo apt install -y git
git clone https://github.com/Aldric07/sncf-retards-mlops.git
```
Installe Git et récupère ton code sur la VM.

**Préparer la VM**
```bash
bash ~/sncf-retards-mlops/deploy/setup_vm.sh https://github.com/Aldric07/sncf-retards-mlops.git
```
Installe Docker si besoin, crée le fichier `.env` avec des mots de passe aléatoires et **affiche ton token admin : note-le**.

```bash
exit
```
Se déconnecte (nécessaire pour que les droits Docker s'appliquent). Reconnecte-toi avec la même commande `ssh` qu'avant.

**Premier lancement sur la VM**
```bash
cd ~/sncf-retards-mlops
docker compose up -d --build
```
Lance tout le système sur la VM (5 à 10 min la première fois).

Teste depuis ton navigateur : `http://IP_DE_LA_VM:8501`. Crée une clé API comme à l'étape 3 en remplaçant `localhost` par l'IP de la VM et `change-moi-admin` par le token affiché.

---

## Étape 6 — Déploiement automatique : Niveau 1

### Version « une commande »
Depuis ton PC, à la racine du projet :

Mac
```bash
chmod +x deploy/deploy.sh
./deploy/deploy.sh azureuser@IP_DE_LA_VM
```
Windows
```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\deploy\deploy.ps1 azureuser@IP_DE_LA_VM
```
Se connecte à la VM, récupère le dernier code et relance les conteneurs. (`chmod` rend le script exécutable ; `Set-ExecutionPolicy` autorise le script pour cette fenêtre seulement.)

### Version pipeline CD (GitHub Actions)
Sur GitHub : **Settings → Secrets and variables → Actions → New repository secret**. Crée 3 secrets :
- `VM_HOST` : l'IP de la VM
- `VM_USER` : `azureuser`
- `VM_SSH_KEY` : le contenu de ta clé **privée** :

Mac
```bash
cat ~/.ssh/id_ed25519
```
Windows
```powershell
Get-Content $HOME\.ssh\id_ed25519
```
Affiche la clé privée : copie **tout**, y compris les lignes `-----BEGIN` et `-----END`. (Option A : affiche plutôt ton fichier `.pem`.)

Ensuite, à chaque modification :
```bash
git add .
git commit -m "Mise à jour"
git push
```
Le push déclenche la pipeline : onglet **Actions** sur GitHub pour la voir vérifier le code puis déployer sur la VM.

---

## Étape 7 — Test de charge (10 min)

**Créer un environnement Python**

Mac
```bash
python3.11 -m venv .venv
source .venv/bin/activate
```
Windows
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
```
Crée un environnement Python isolé pour le projet et l'active.

**Installer Locust (Mac et Windows)**
```bash
pip install -r loadtest/requirements.txt
```
Installe l'outil de test de charge.

**Donner la clé API à Locust**

Mac
```bash
export API_KEY=TA_CLE
```
Windows
```powershell
$env:API_KEY="TA_CLE"
```
Met ta clé dans une variable que Locust lira.

**Lancer le test (Mac et Windows)**
```bash
locust -f loadtest/locustfile.py --host http://IP_DE_LA_VM:8000 --headless -u 100 -r 10 -t 2m --html rapport_locust.html
```
Simule **100 utilisateurs** (10 nouveaux par seconde) pendant 2 minutes, puis crée le rapport `rapport_locust.html` (graphiques à mettre dans le PowerPoint).

Variante avec interface graphique : enlève `--headless -u 100 -r 10 -t 2m --html rapport_locust.html`, puis ouvre http://localhost:8089.

---

## Étape 8 — Montrer les briques du Niveau 2 et 3

Les commandes de cette étape se tapent **sur la VM** (connecté avec `ssh`), donc identiques pour Mac et Windows.

**MLflow** : `http://IP_DE_LA_VM:5000` → expérience « sncf-retards » (métriques : MAE du modèle vs MAE de la référence naïve) et onglet **Models** (versions, alias `production`).

**Mettre à jour le modèle en production** (sur la VM) :
```bash
docker compose run --rm -e RETRAIN=1 -e REFRESH_DATA=1 trainer
```
Retélécharge les données SNCF, réentraîne, crée une nouvelle version dans MLflow et la passe en `production` **seulement si elle est meilleure** (champion / challenger). Les API chargent la nouvelle version seules en moins d'une minute, sans redémarrer : vérifie avec `curl http://localhost:8000/health` (champ `model_version`).

**Data drift** : interface → onglet « Admin (drift) » avec le token admin, ou :
```bash
curl http://localhost:8000/admin/drift -H "X-Admin-Token: TON_TOKEN"
```
Compare les données reçues en production à celles de l'entraînement (test de Kolmogorov-Smirnov). Il faut au moins 30 prédictions : le test Locust en génère assez.

**Scaling horizontal** :
```bash
for i in 1 2 3 4 5 6; do curl -s -D - -o /dev/null http://localhost:8000/health | grep -i x-instance; done
```
Appelle l'API 6 fois et affiche quel conteneur a répondu : tu vois 3 noms différents (Nginx répartit la charge).

```bash
docker compose up -d --scale api=5
```
Passe de 3 à 5 copies de l'API en une commande.

**Usage de tous les utilisateurs** :
```bash
curl http://localhost:8000/admin/usage -H "X-Admin-Token: TON_TOKEN"
```

---

## Étape 9 — À la fin : éviter de payer

Option B :
```bash
cd terraform
terraform destroy
```
Supprime toute l'infrastructure Azure (tape `yes`). Option A : supprime le groupe de ressources dans le portail. **À faire après la soutenance.**

---

## Commandes utiles

| Commande | Ce qu'elle fait |
|---|---|
| `docker compose logs -f api` | Suit les logs des API en direct (Ctrl+C pour quitter) |
| `docker compose down` | Arrête tous les conteneurs (les données restent) |
| `docker compose down -v` | Arrête et **efface** les données (base, MLflow) : repart de zéro |
| `docker compose restart api` | Redémarre les API |

## Problèmes fréquents

- **« Cannot connect to the Docker daemon »** : Docker Desktop n'est pas lancé.
- **« port is already allocated »** : un autre programme utilise le port 8000, 8501 ou 5000. Ferme-le ou change le port dans `docker-compose.yml`.
- **`trainer` en « exited (1) »** : regarde `docker compose logs trainer` ; souvent un problème de téléchargement (voir l'encadré de l'étape 2).
- **L'interface dit « Clé API invalide »** : la base a été recréée (`down -v`), recrée une clé.

## Checklist des niveaux

| Niveau | Exigence | Où |
|---|---|---|
| 0 | Une commande, tout en conteneurs | `docker compose up -d --build` |
| 1 | Déploiement par commande / CD | `deploy/deploy.sh`, `.github/workflows/deploy.yml` |
| 1 | Clé dans le header | `X-API-Key` (hash SHA-256 en base) |
| 1 | Usage par utilisateur | `/usage/me`, `/admin/usage` |
| 1 | Test de charge | `loadtest/locustfile.py` |
| 2 | Terraform | `terraform/` |
| 2 | Interface | Streamlit (`ui/`) |
| 2 | Data drift | `/admin/drift` |
| 2 | MLflow | Versionnement + mise à jour auto en production |
| 3 | Scaling horizontal | 3 replicas + Nginx |
| 3 | Bonus | Champion / challenger, rechargement à chaud |
