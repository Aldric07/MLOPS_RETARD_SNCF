#!/usr/bin/env bash
# À lancer UNE SEULE FOIS sur la VM (Ubuntu) pour l'installer.
# Usage : bash setup_vm.sh https://github.com/TON_PSEUDO/sncf-retards-mlops.git
set -euo pipefail
REPO_URL="${1:?Donne l'URL du repo GitHub}"

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sudo sh        # installe Docker + docker compose
  sudo usermod -aG docker "$USER"                     # docker sans sudo
fi

if [ ! -d "$HOME/sncf-retards-mlops" ]; then
  git clone "$REPO_URL" "$HOME/sncf-retards-mlops"
fi

cd "$HOME/sncf-retards-mlops"
if [ ! -f .env ]; then
  cp .env.example .env
  # mots de passe aléatoires
  sed -i "s/change-moi-postgres/$(openssl rand -hex 16)/" .env
  sed -i "s/change-moi-admin/$(openssl rand -hex 16)/" .env
fi
echo "OK. Ton token admin :"
grep ADMIN_TOKEN .env
echo "Déconnecte-toi puis reconnecte-toi (pour les droits docker), puis : cd ~/sncf-retards-mlops && docker compose up -d --build"
