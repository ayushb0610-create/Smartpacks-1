-- SmartPack Postgres schema.
--
-- This is a plain-SQL mirror of app/models.py, provided for review and for
-- anyone who wants to `psql -f schema.sql` directly instead of letting
-- SQLAlchemy's create_all() (or scripts/seed_db.py) create it. If you edit
-- one, edit the other — models.py is the version actually used at runtime.

CREATE TABLE IF NOT EXISTS commodities (
    id                     SERIAL PRIMARY KEY,
    name                   VARCHAR(120) NOT NULL UNIQUE,
    category               VARCHAR(40)  NOT NULL,
    moisture_pct           DOUBLE PRECISION NOT NULL,
    fat_pct                DOUBLE PRECISION NOT NULL,
    ph                     DOUBLE PRECISION,
    ph_range               VARCHAR(60),
    ph_source              TEXT,
    water_activity         DOUBLE PRECISION NOT NULL,
    respiration_rate       DOUBLE PRECISION NOT NULL,
    o2_target_pct          DOUBLE PRECISION,
    co2_target_pct         DOUBLE PRECISION,
    base_shelf_life_days   DOUBLE PRECISION NOT NULL,
    source                 VARCHAR(200) NOT NULL,
    usda_temp_note         TEXT,
    usda_rh_note           TEXT,
    usda_life_note         TEXT,
    respiration_curve      JSONB,                 -- [[temp_c, resp_rate], ...] or NULL
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS materials (
    id                SERIAL PRIMARY KEY,
    name              VARCHAR(120) NOT NULL UNIQUE,
    bis_standard      VARCHAR(120),
    otr               DOUBLE PRECISION NOT NULL,   -- cc/m2/day
    wvtr              DOUBLE PRECISION NOT NULL,   -- g/m2/day
    thickness_um      DOUBLE PRECISION NOT NULL,
    cost_index        DOUBLE PRECISION NOT NULL,   -- 1-5
    sustainability    DOUBLE PRECISION NOT NULL,   -- 1-10
    strength          DOUBLE PRECISION NOT NULL,   -- 1-10
    sealability       DOUBLE PRECISION NOT NULL,   -- 1-10
    light_barrier     DOUBLE PRECISION NOT NULL,   -- 1-10
    temp_min_c        DOUBLE PRECISION NOT NULL,
    temp_max_c        DOUBLE PRECISION NOT NULL,
    recyclable        VARCHAR(60) NOT NULL,
    note              TEXT NOT NULL,
    source            VARCHAR(200) NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cities (
    id             SERIAL PRIMARY KEY,
    state          VARCHAR(80) NOT NULL,
    city           VARCHAR(80) NOT NULL,
    lat            DOUBLE PRECISION NOT NULL,
    lon            DOUBLE PRECISION NOT NULL,
    peak_temp_c    DOUBLE PRECISION NOT NULL,
    peak_rh_pct    DOUBLE PRECISION NOT NULL,
    climate_note   VARCHAR(200) NOT NULL,
    UNIQUE (state, city)
);

CREATE TABLE IF NOT EXISTS recommendation_runs (
    id                              VARCHAR(36) PRIMARY KEY,
    created_at                      TIMESTAMPTZ NOT NULL DEFAULT now(),

    commodity                       VARCHAR(120) NOT NULL,
    commodity_id                    INTEGER REFERENCES commodities(id) ON DELETE SET NULL,
    storage_type                    VARCHAR(20) NOT NULL,
    storage_temp_c                  DOUBLE PRECISION NOT NULL,
    transport_mode                  VARCHAR(20) NOT NULL,
    priority                        VARCHAR(20) NOT NULL,
    weight_g                        DOUBLE PRECISION NOT NULL,
    rh_pct                          DOUBLE PRECISION NOT NULL,
    water_activity                  DOUBLE PRECISION NOT NULL,
    ph                              DOUBLE PRECISION NOT NULL,
    ox_sensitivity                  DOUBLE PRECISION NOT NULL,
    light_sensitivity               DOUBLE PRECISION NOT NULL,
    target_life_days                DOUBLE PRECISION NOT NULL,

    route_from_city                 VARCHAR(80),
    route_from_state                VARCHAR(80),
    route_to_city                   VARCHAR(80),
    route_to_state                  VARCHAR(80),
    route_km                        DOUBLE PRECISION,
    route_transit_days              DOUBLE PRECISION,

    top_material_id                 INTEGER REFERENCES materials(id) ON DELETE SET NULL,
    top_material                    VARCHAR(120),
    top_score                       DOUBLE PRECISION,
    predicted_shelf_life_days       DOUBLE PRECISION,
    ml_predicted_shelf_life_days    DOUBLE PRECISION,
    actual_shelf_life_days          DOUBLE PRECISION,
    feedback_recorded_at            TIMESTAMPTZ,

    results_json                    JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_recommendation_runs_created_at
    ON recommendation_runs (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_recommendation_runs_feedback
    ON recommendation_runs (actual_shelf_life_days)
    WHERE actual_shelf_life_days IS NOT NULL;
