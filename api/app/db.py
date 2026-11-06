"""Accès PostgreSQL : utilisateurs (clés API) et journal d'usage."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from contextlib import contextmanager

import psycopg2
from psycopg2.pool import ThreadedConnectionPool

MAX_CONN = int(os.getenv("DB_POOL_SIZE", "10"))
_pool: ThreadedConnectionPool | None = None
_sem = threading.BoundedSemaphore(MAX_CONN)


def init_pool(retries: int = 30) -> None:
    global _pool
    for _ in range(retries):
        try:
            _pool = ThreadedConnectionPool(1, MAX_CONN, dsn=os.environ["DATABASE_URL"])
            return
        except psycopg2.OperationalError:
            time.sleep(2)
    raise RuntimeError("Impossible de se connecter à PostgreSQL")


def close_pool() -> None:
    if _pool:
        _pool.closeall()


@contextmanager
def cursor():
    with _sem:  # attend une connexion libre au lieu de planter sous forte charge
        conn = _pool.getconn()
        try:
            with conn:
                with conn.cursor() as cur:
                    yield cur
        finally:
            _pool.putconn(conn)


def hash_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def get_user_by_key(key: str):
    with cursor() as cur:
        cur.execute("SELECT id, name FROM users WHERE api_key_hash=%s AND active", (hash_key(key),))
        row = cur.fetchone()
    return {"id": row[0], "name": row[1]} if row else None


def create_user(name: str, key: str) -> int:
    with cursor() as cur:
        cur.execute("INSERT INTO users(name, api_key_hash) VALUES (%s, %s) RETURNING id",
                    (name, hash_key(key)))
        return cur.fetchone()[0]


def log_usage(user_id, endpoint, status, latency_ms, features=None, prediction=None,
              model_version=None, instance=None) -> None:
    with cursor() as cur:
        cur.execute(
            """INSERT INTO usage_logs(user_id, endpoint, status_code, latency_ms, features,
                                      prediction, model_version, instance)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
            (user_id, endpoint, status, latency_ms,
             json.dumps(features) if features else None, prediction, model_version, instance),
        )


def usage_for_user(user_id: int) -> dict:
    with cursor() as cur:
        cur.execute("""SELECT endpoint, COUNT(*), ROUND(AVG(latency_ms)::numeric, 1)
                       FROM usage_logs WHERE user_id=%s GROUP BY endpoint""", (user_id,))
        par_endpoint = [{"endpoint": e, "appels": n, "latence_moy_ms": float(l or 0)}
                        for e, n, l in cur.fetchall()]
        cur.execute("""SELECT created_at, endpoint, status_code, prediction FROM usage_logs
                       WHERE user_id=%s ORDER BY id DESC LIMIT 10""", (user_id,))
        derniers = [{"date": str(d), "endpoint": e, "status": s, "prediction": p}
                    for d, e, s, p in cur.fetchall()]
    return {"total": sum(x["appels"] for x in par_endpoint),
            "par_endpoint": par_endpoint, "derniers_appels": derniers}


def usage_all() -> list[dict]:
    with cursor() as cur:
        cur.execute("""SELECT u.id, u.name, COUNT(l.id), MAX(l.created_at),
                              ROUND(AVG(l.latency_ms)::numeric, 1)
                       FROM users u LEFT JOIN usage_logs l ON l.user_id = u.id
                       GROUP BY u.id, u.name ORDER BY COUNT(l.id) DESC""")
        return [{"user_id": i, "nom": n, "appels": c, "dernier_appel": str(d) if d else None,
                 "latence_moy_ms": float(l or 0)} for i, n, c, d, l in cur.fetchall()]


def recent_features(limit: int = 500) -> list[dict]:
    with cursor() as cur:
        cur.execute("""SELECT features FROM usage_logs
                       WHERE endpoint='/predict' AND status_code=200 AND features IS NOT NULL
                       ORDER BY id DESC LIMIT %s""", (limit,))
        return [r[0] for r in cur.fetchall()]
