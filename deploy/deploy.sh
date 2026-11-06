#!/usr/bin/env bash 
# Déploiement en une commande depuis ton Mac :
#   ./deploy/deploy.sh azureuser@IP_DE_LA_VM
set -euo pipefail
TARGET="${1:?Usage : ./deploy/deploy.sh utilisateur@ip}"
ssh "$TARGET" 'cd ~/sncf-retards-mlops && git pull origin main && docker compose up -d --build && docker compose ps'
