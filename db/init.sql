-- Exécuté automatiquement au premier démarrage de PostgreSQL
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    api_key_hash  CHAR(64) UNIQUE NOT NULL,   -- on stocke le hash, jamais la clé
    active        BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS usage_logs (
    id            BIGSERIAL PRIMARY KEY,
    user_id       INT REFERENCES users(id),
    endpoint      TEXT NOT NULL,
    status_code   INT NOT NULL,
    latency_ms    REAL,
    features      JSONB,
    prediction    REAL,
    model_version TEXT,
    instance      TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_usage_user ON usage_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_usage_endpoint ON usage_logs(endpoint, id DESC);
