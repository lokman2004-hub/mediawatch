-- =============================================================================
-- CRÉATION DES TABLES — Projet : architecture
-- Base de données : mabd
-- Tables : publications, stats_quotidiennes, termes_frequents, executions
-- =============================================================================

-- ── Table principale : publications ───────────────────────────
CREATE TABLE IF NOT EXISTS publications (
    id               VARCHAR(20)  PRIMARY KEY,
    titre            TEXT         NOT NULL,
    auteur           VARCHAR(255) DEFAULT 'Inconnu',
    date_publication TIMESTAMPTZ,
    categorie        VARCHAR(100),
    description      TEXT,
    contenu          TEXT,
    source           VARCHAR(100),
    pays             VARCHAR(100),
    url              TEXT         UNIQUE,
    langue           VARCHAR(10),
    nb_mots          INTEGER      DEFAULT 0,
    date_collecte    TIMESTAMPTZ  DEFAULT NOW(),
    date_insertion   TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pub_source   ON publications(source);
CREATE INDEX IF NOT EXISTS idx_pub_langue   ON publications(langue);
CREATE INDEX IF NOT EXISTS idx_pub_date     ON publications(date_publication);
CREATE INDEX IF NOT EXISTS idx_pub_categorie ON publications(categorie);
CREATE INDEX IF NOT EXISTS idx_pub_pays     ON publications(pays);

-- ── Table analytique : stats_quotidiennes ─────────────────────
CREATE TABLE IF NOT EXISTS stats_quotidiennes (
    id              SERIAL       PRIMARY KEY,
    date_rapport    DATE         DEFAULT CURRENT_DATE,
    source          VARCHAR(100),
    pays            VARCHAR(100),
    langue          VARCHAR(10),
    nb_publications INTEGER      DEFAULT 0,
    moy_mots        FLOAT        DEFAULT 0,
    date_insertion  TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stats_date   ON stats_quotidiennes(date_rapport);
CREATE INDEX IF NOT EXISTS idx_stats_source ON stats_quotidiennes(source);

-- ── Table analytique : termes_frequents ───────────────────────
CREATE TABLE IF NOT EXISTS termes_frequents (
    id             SERIAL      PRIMARY KEY,
    date_rapport   DATE        DEFAULT CURRENT_DATE,
    terme          VARCHAR(100),
    occurrences    INTEGER     DEFAULT 0,
    source         VARCHAR(100) DEFAULT 'all',
    date_insertion TIMESTAMPTZ  DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_termes_date  ON termes_frequents(date_rapport);
CREATE INDEX IF NOT EXISTS idx_termes_terme ON termes_frequents(terme);

-- ── Table de suivi : executions ───────────────────────────────
CREATE TABLE IF NOT EXISTS executions (
    id               SERIAL       PRIMARY KEY,
    date_execution   TIMESTAMPTZ  DEFAULT NOW(),
    etape            VARCHAR(100),
    statut           VARCHAR(20)  DEFAULT 'success',
    nb_articles      INTEGER      DEFAULT 0,
    duree_secondes   FLOAT        DEFAULT 0,
    message          TEXT,
    projet           VARCHAR(100) DEFAULT 'architecture'
);

-- ── Vue analytique : publications par source et jour ──────────
CREATE OR REPLACE VIEW vue_publications_par_jour AS
SELECT
    DATE(date_publication) AS jour,
    source,
    pays,
    langue,
    COUNT(*)               AS nb_publications,
    AVG(nb_mots)           AS moy_mots
FROM publications
WHERE date_publication IS NOT NULL
GROUP BY DATE(date_publication), source, pays, langue
ORDER BY jour DESC, nb_publications DESC;

-- ── Vue : top termes du jour ──────────────────────────────────
CREATE OR REPLACE VIEW vue_top_termes AS
SELECT terme, SUM(occurrences) AS total_occurrences
FROM termes_frequents
WHERE date_rapport = CURRENT_DATE
GROUP BY terme
ORDER BY total_occurrences DESC
LIMIT 20;

-- ── Confirmation ──────────────────────────────────────────────
SELECT
    table_name AS "Table",
    CASE
        WHEN table_name = 'publications'      THEN 'Articles collectés'
        WHEN table_name = 'stats_quotidiennes' THEN 'Statistiques par jour'
        WHEN table_name = 'termes_frequents'  THEN 'Mots-clés fréquents'
        WHEN table_name = 'executions'        THEN 'Historique pipeline'
    END AS "Description"
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_type = 'BASE TABLE'
ORDER BY table_name;