"""Interface web Streamlit : prévision des retards TGV."""
import os
from datetime import date

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Retards TGV", page_icon="🚄", layout="wide")
st.title("🚄 Prévision des retards TGV")
st.caption("Taux de trains en retard à l'arrivée prévu pour une liaison et un mois donnés.")

with st.sidebar:
    st.header("Connexion")
    api_key = st.text_input("Clé API (X-API-Key)", type="password")
    st.caption(f"API : {API_URL}")

if not api_key:
    st.info("Entre ta clé API dans la barre latérale pour commencer.")
    st.stop()

headers = {"X-API-Key": api_key}


@st.cache_data(ttl=300)
def get_liaisons(key: str):
    r = requests.get(f"{API_URL}/liaisons", headers={"X-API-Key": key}, timeout=15)
    r.raise_for_status()
    return pd.DataFrame(r.json()["liaisons"])


try:
    liaisons = get_liaisons(api_key)
except requests.HTTPError as e:
    st.error(f"Accès refusé : {e.response.json().get('detail', e)}")
    st.stop()
except requests.RequestException as e:
    st.error(f"API injoignable : {e}")
    st.stop()

tab_pred, tab_usage, tab_admin = st.tabs(["Prévision", "Mon usage", "Admin (drift)"])

with tab_pred:
    c1, c2, c3, c4 = st.columns([3, 3, 1, 1])
    dep = c1.selectbox("Gare de départ", sorted(liaisons["gare_depart"].unique()))
    arr = c2.selectbox("Gare d'arrivée",
                       sorted(liaisons.loc[liaisons["gare_depart"] == dep, "gare_arrivee"]))
    today = date.today()
    annee = c3.number_input("Année", 2015, 2035, today.year)
    mois = c4.number_input("Mois", 1, 12, today.month)

    if st.button("Prévoir", type="primary"):
        r = requests.post(f"{API_URL}/predict", headers=headers, timeout=15,
                          json={"gare_depart": dep, "gare_arrivee": arr,
                                "annee": int(annee), "mois": int(mois)})
        if r.ok:
            res = r.json()
            m1, m2, m3 = st.columns(3)
            m1.metric("Taux de retard prévu", f"{res['taux_retard_prevu_pct']} %")
            m2.metric("Niveau", res["niveau"])
            m3.metric("Version du modèle", res["model_version"])
            hist = pd.DataFrame(res["historique_12_mois"])
            if not hist.empty:
                st.subheader("Historique des 12 derniers mois")
                st.line_chart(hist.set_index("mois")["taux_retard_pct"])
            st.caption(f"Réponse servie par le conteneur : {res['instance']}")
        else:
            st.error(r.json().get("detail", r.text))

with tab_usage:
    r = requests.get(f"{API_URL}/usage/me", headers=headers, timeout=15)
    if r.ok:
        u = r.json()
        st.metric("Appels totaux", u["total"])
        st.dataframe(pd.DataFrame(u["par_endpoint"]), use_container_width=True)
        st.dataframe(pd.DataFrame(u["derniers_appels"]), use_container_width=True)

with tab_admin:
    token = st.text_input("Token admin (X-Admin-Token)", type="password")
    if token:
        ah = {"X-Admin-Token": token}
        r = requests.get(f"{API_URL}/admin/drift", headers=ah, timeout=30)
        if r.ok:
            d = r.json()
            if d["statut"] != "ok":
                st.warning(f"Pas assez de prédictions pour mesurer le drift "
                           f"({d['n_current']}/{d['minimum']}).")
            else:
                (st.error if d["drift_global"] else st.success)(
                    f"Drift global : {'OUI' if d['drift_global'] else 'non'} "
                    f"({int(d['part_variables_en_drift'] * 100)} % des variables)")
                st.dataframe(pd.DataFrame(d["variables"]).T, use_container_width=True)
        else:
            st.error(r.json().get("detail", r.text))
        r = requests.get(f"{API_URL}/admin/usage", headers=ah, timeout=15)
        if r.ok:
            st.subheader("Usage par utilisateur")
            st.dataframe(pd.DataFrame(r.json()["utilisateurs"]), use_container_width=True)
