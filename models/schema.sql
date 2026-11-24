-- PharmaLens schema v0.1
-- Rules enforced here:
--   * every row carries provenance (source_url, source_name, retrieved_at, status)
--   * nothing is overwritten: versioned rows via valid_from / valid_to (SCD type 2)
--   * every value is traceable to a hashed raw object (raw_object)

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

DO $$ BEGIN
  CREATE TYPE data_status AS ENUM ('official','secondary','derived','gap');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE link_confidence AS ENUM ('confirmed','derived','hypothesis');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ---------------------------------------------------------------- source register
CREATE TABLE IF NOT EXISTS source (
  source_id        serial PRIMARY KEY,
  name             text UNIQUE NOT NULL,
  category         text NOT NULL,           -- substance, certificate, approval_eu, national, patent, shortage, tender, volume, company
  jurisdiction     text,                    -- ISO country / 'EU' / 'INT'
  base_url         text NOT NULL,
  probe_url        text,                    -- URL actually tested
  access_method    text,                    -- download | api | html | none
  http_status      int,
  final_url        text,
  robots_status    text,                    -- allowed | disallowed | no_robots | unreachable
  licence_note     text,
  update_frequency text,
  traffic_light    text CHECK (traffic_light IN ('green','yellow','red')),
  traffic_reason   text,
  last_checked     timestamptz,
  last_success     timestamptz,
  row_count        bigint
);

-- ---------------------------------------------------------------- raw storage index
CREATE TABLE IF NOT EXISTS raw_object (
  raw_id       bigserial PRIMARY KEY,
  source_id    int REFERENCES source(source_id),
  url          text NOT NULL,
  sha256       char(64) NOT NULL,
  path         text NOT NULL,               -- raw/<source>/<yyyy-mm-dd>/<sha256>.<ext>
  content_type text,
  bytes        bigint,
  http_status  int,
  retrieved_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (url, sha256)
);

-- ---------------------------------------------------------------- provenance mixin
-- Postgres has no mixins; every entity table repeats these columns:
--   source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
--   status data_status NOT NULL, raw_id bigint, valid_from timestamptz NOT NULL default now(), valid_to timestamptz
-- "current" view of a table = WHERE valid_to IS NULL.

CREATE TABLE IF NOT EXISTS api (
  row_id           bigserial PRIMARY KEY,
  api_id           bigint NOT NULL,         -- stable entity key across versions
  inn              text NOT NULL,
  salt_form        text,
  parent_api_id    bigint,                  -- salt -> base
  cas              text,
  unii             text,
  atc              text[],
  ph_eur_monograph text,
  drugcentral_id   int,
  pubchem_cid      bigint,
  synonyms         text[],
  is_veterinary    boolean,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS api_current ON api(api_id) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS api_inn_trgm ON api USING gin (inn gin_trgm_ops);

CREATE TABLE IF NOT EXISTS company (
  row_id           bigserial PRIMARY KEY,
  company_id       bigint NOT NULL,
  name_normalized  text NOT NULL,
  name_raw         text[] NOT NULL,
  country          char(2),                 -- ISO 3166-1 alpha-2 of the legal seat (NOT agent country)
  country_basis    text,                    -- how country was determined (lei, register, address, ...)
  lei              char(20),
  vat_or_uid       text,
  website          text,
  roles            text[],                  -- api_manufacturer, fdf_manufacturer, mah, cdmo, distributor, importer
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS company_current ON company(company_id) WHERE valid_to IS NULL;
CREATE INDEX IF NOT EXISTS company_name_trgm ON company USING gin (name_normalized gin_trgm_ops);

CREATE TABLE IF NOT EXISTS company_relation (
  row_id         bigserial PRIMARY KEY,
  parent_id      bigint NOT NULL,
  child_id       bigint NOT NULL,
  relation_type  text NOT NULL,             -- subsidiary | branch | acquisition | ultimate_parent
  ownership_pct  numeric,
  event_date     date,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS site (
  row_id          bigserial PRIMARY KEY,
  site_id         bigint NOT NULL,
  company_id      bigint,
  address         text,
  city            text,
  postal_code     text,
  country         char(2),
  fei_number      text,
  eudragmdp_id    text,
  gmp_status      text,
  last_inspection date,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS site_current ON site(site_id) WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS api_certificate (
  row_id            bigserial PRIMARY KEY,
  api_id            bigint,
  holder_company_id bigint,
  site_id           bigint,
  cert_type         text NOT NULL,          -- CEP | US_DMF | JDMF | KDMF | WHO_PQ | WRITTEN_CONFIRMATION | EU_GMP
  number            text,
  cert_status       text,
  issue_date        date,
  substance_raw     text,                   -- name exactly as in source, before API mapping
  holder_raw        text,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS product (
  row_id            bigserial PRIMARY KEY,
  product_id        bigint NOT NULL,
  name              text NOT NULL,
  country           char(2) NOT NULL,
  mah_company_id    bigint,
  mah_raw           text,
  authorisation_no  text,
  strength          text,
  form              text,
  procedure         text,                   -- centralised | DCP | MRP | national
  procedure_no      text,
  product_status    text,
  is_veterinary     boolean,
  leaflet_url       text,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);
CREATE UNIQUE INDEX IF NOT EXISTS product_current ON product(product_id) WHERE valid_to IS NULL;

CREATE TABLE IF NOT EXISTS product_api (
  product_id bigint NOT NULL,
  api_id     bigint NOT NULL,
  substance_raw text,
  PRIMARY KEY (product_id, api_id)
);

CREATE TABLE IF NOT EXISTS product_manufacturer (
  row_id          bigserial PRIMARY KEY,
  product_id      bigint NOT NULL,
  company_id      bigint,
  site_id         bigint,
  role            text NOT NULL,            -- batch_release | manufacturer | packager | importer
  manufacturer_raw text NOT NULL,
  leaflet_url     text NOT NULL,
  evidence_quote  text NOT NULL,            -- verbatim quote from leaflet / SmPC / Annex IIA
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS patent (
  row_id        bigserial PRIMARY KEY,
  api_id        bigint,
  number        text NOT NULL,
  jurisdiction  text NOT NULL,
  patent_type   text NOT NULL,              -- basic | SPC | formulation | salt_polymorph | process | use
  basic_patent  text,                       -- for SPC: underlying patent
  expiry        date,
  patent_status text,
  legal_events  jsonb,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS event (
  row_id      bigserial PRIMARY KEY,
  event_type  text NOT NULL,                -- new_cep | withdrawal | shortage | warning_letter | inspection | new_authorisation | import_alert
  event_date  date,
  entity_type text NOT NULL,
  entity_ref  bigint,
  detail      jsonb,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS market_metric (
  row_id   bigserial PRIMARY KEY,
  api_id   bigint,
  country  char(2),
  metric   text NOT NULL,                   -- DDD | items | packs | units | rx_cost
  unit     text NOT NULL,
  period   text NOT NULL,
  value    numeric,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS tender (
  row_id            bigserial PRIMARY KEY,
  api_id            bigint,
  country           char(2),
  buyer             text,                   -- public body (no persons)
  winner_company_id bigint,
  winner_raw        text,
  value             numeric,
  currency          char(3),
  award_date        date,
  notice_id         text,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

-- Evidence: atomic, citable facts that derived rows point to
CREATE TABLE IF NOT EXISTS evidence (
  evidence_id    bigserial PRIMARY KEY,
  kind           text NOT NULL,
  entity_type    text,
  entity_ref     bigint,
  evidence_quote text,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL, raw_id bigint REFERENCES raw_object(raw_id)
);

CREATE TABLE IF NOT EXISTS supply_link (
  row_id        bigserial PRIMARY KEY,
  from_type     text NOT NULL,
  from_id       bigint NOT NULL,
  to_type       text NOT NULL,
  to_id         bigint NOT NULL,
  link_type     text NOT NULL,              -- api_to_api_site | api_site_to_fdf_site | fdf_site_to_mah | mah_to_market
  confidence    link_confidence NOT NULL,
  rationale     text NOT NULL,
  evidence_ids  bigint[] NOT NULL,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL CHECK (status IN ('official','derived')),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz,
  CHECK (confidence = 'confirmed' OR status = 'derived')
);

CREATE TABLE IF NOT EXISTS eu_dmf_hint (
  row_id       bigserial PRIMARY KEY,
  api_id       bigint NOT NULL,
  company_id   bigint NOT NULL,
  score        int NOT NULL CHECK (score BETWEEN 0 AND 100),
  reasons      text[] NOT NULL,
  evidence_ids bigint[] NOT NULL,
  source_url text NOT NULL, source_name text NOT NULL, retrieved_at timestamptz NOT NULL,
  status data_status NOT NULL DEFAULT 'derived' CHECK (status = 'derived'),
  valid_from timestamptz NOT NULL DEFAULT now(), valid_to timestamptz
);

CREATE TABLE IF NOT EXISTS entity_merge_log (
  merge_id     bigserial PRIMARY KEY,
  entity_type  text NOT NULL,
  kept_id      bigint NOT NULL,
  merged_id    bigint NOT NULL,
  score        numeric NOT NULL,
  reasons      jsonb NOT NULL,
  decision     text NOT NULL CHECK (decision IN ('auto_merged','review','rejected','manual_merged')),
  decided_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gap (
  gap_id            bigserial PRIMARY KEY,
  area              text NOT NULL,
  entity_type       text,
  entity_ref        text,
  reason            text NOT NULL,
  where_obtainable  text,
  source_name       text,
  recorded_at       timestamptz NOT NULL DEFAULT now(),
  resolved_at       timestamptz
);

-- v0.2: natural keys for idempotent, versioned imports
ALTER TABLE product ADD COLUMN IF NOT EXISTS natural_key text;
CREATE UNIQUE INDEX IF NOT EXISTS product_nk_current ON product(natural_key) WHERE valid_to IS NULL;
ALTER TABLE api_certificate ADD COLUMN IF NOT EXISTS natural_key text;
CREATE UNIQUE INDEX IF NOT EXISTS cert_nk_current ON api_certificate(natural_key) WHERE valid_to IS NULL;
ALTER TABLE product ADD COLUMN IF NOT EXISTS atc text;
ALTER TABLE product_manufacturer ADD COLUMN IF NOT EXISTS site_address_raw text;
ALTER TABLE product_manufacturer ADD COLUMN IF NOT EXISTS site_country char(2);
ALTER TABLE product_manufacturer ADD COLUMN IF NOT EXISTS country_basis text;
