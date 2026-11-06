"""Test de charge de l'API avec Locust.

Lancement (voir le guide) :
    locust -f loadtest/locustfile.py --host http://IP_DE_LA_VM:8000
"""
import os
import random
from datetime import date

from locust import HttpUser, between, task

API_KEY = os.environ.get("API_KEY", "")


class Voyageur(HttpUser):
    wait_time = between(0.5, 2)

    def on_start(self):
        self.client.headers.update({"X-API-Key": API_KEY})
        r = self.client.get("/liaisons")
        self.liaisons = r.json()["liaisons"] if r.ok else []

    @task(5)
    def predire(self):
        if not self.liaisons:
            return
        l = random.choice(self.liaisons)
        today = date.today()
        self.client.post("/predict", name="/predict", json={
            "gare_depart": l["gare_depart"], "gare_arrivee": l["gare_arrivee"],
            "annee": today.year, "mois": today.month,
        })

    @task(1)
    def sante(self):
        self.client.get("/health")
