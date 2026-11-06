# Déploiement en une commande depuis Windows (PowerShell) : 
#   .\deploy\deploy.ps1 azureuser@IP_DE_LA_VM
param([Parameter(Mandatory = $true)][string]$Target)
ssh $Target 'cd ~/sncf-retards-mlops && git pull origin main && docker compose up -d --build && docker compose ps'
