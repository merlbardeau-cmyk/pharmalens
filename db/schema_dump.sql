--
-- PostgreSQL database dump
--

\restrict vK4vBJsyhKs9aDMnQEDHQcrlFacUK0mMBQggamEKVDkRhPnYqSSt1hGFRHxVncY

-- Dumped from database version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA public;


--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: data_status; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.data_status AS ENUM (
    'official',
    'secondary',
    'derived',
    'gap'
);


--
-- Name: link_confidence; Type: TYPE; Schema: public; Owner: -
--

CREATE TYPE public.link_confidence AS ENUM (
    'confirmed',
    'derived',
    'hypothesis'
);


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: api; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api (
    row_id bigint NOT NULL,
    api_id bigint NOT NULL,
    inn text NOT NULL,
    salt_form text,
    parent_api_id bigint,
    cas text,
    unii text,
    atc text[],
    ph_eur_monograph text,
    drugcentral_id integer,
    pubchem_cid bigint,
    synonyms text[],
    is_veterinary boolean,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: api_certificate; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.api_certificate (
    row_id bigint NOT NULL,
    api_id bigint,
    holder_company_id bigint,
    site_id bigint,
    cert_type text NOT NULL,
    number text,
    cert_status text,
    issue_date date,
    substance_raw text,
    holder_raw text,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    natural_key text
);


--
-- Name: api_certificate_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_certificate_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_certificate_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_certificate_row_id_seq OWNED BY public.api_certificate.row_id;


--
-- Name: api_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.api_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: api_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.api_row_id_seq OWNED BY public.api.row_id;


--
-- Name: company; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company (
    row_id bigint NOT NULL,
    company_id bigint NOT NULL,
    name_normalized text NOT NULL,
    name_raw text[] NOT NULL,
    country character(2),
    country_basis text,
    lei character(20),
    vat_or_uid text,
    website text,
    roles text[],
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: company_relation; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.company_relation (
    row_id bigint NOT NULL,
    parent_id bigint NOT NULL,
    child_id bigint NOT NULL,
    relation_type text NOT NULL,
    ownership_pct numeric,
    event_date date,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: company_relation_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_relation_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_relation_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_relation_row_id_seq OWNED BY public.company_relation.row_id;


--
-- Name: company_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.company_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: company_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.company_row_id_seq OWNED BY public.company.row_id;


--
-- Name: entity_merge_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.entity_merge_log (
    merge_id bigint NOT NULL,
    entity_type text NOT NULL,
    kept_id bigint NOT NULL,
    merged_id bigint NOT NULL,
    score numeric NOT NULL,
    reasons jsonb NOT NULL,
    decision text NOT NULL,
    decided_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT entity_merge_log_decision_check CHECK ((decision = ANY (ARRAY['auto_merged'::text, 'review'::text, 'rejected'::text, 'manual_merged'::text])))
);


--
-- Name: entity_merge_log_merge_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_merge_log_merge_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: entity_merge_log_merge_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.entity_merge_log_merge_id_seq OWNED BY public.entity_merge_log.merge_id;


--
-- Name: entity_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.entity_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: eu_dmf_hint; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.eu_dmf_hint (
    row_id bigint NOT NULL,
    api_id bigint NOT NULL,
    company_id bigint NOT NULL,
    score integer NOT NULL,
    reasons text[] NOT NULL,
    evidence_ids bigint[] NOT NULL,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status DEFAULT 'derived'::public.data_status NOT NULL,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    CONSTRAINT eu_dmf_hint_score_check CHECK (((score >= 0) AND (score <= 100))),
    CONSTRAINT eu_dmf_hint_status_check CHECK ((status = 'derived'::public.data_status))
);


--
-- Name: eu_dmf_hint_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.eu_dmf_hint_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: eu_dmf_hint_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.eu_dmf_hint_row_id_seq OWNED BY public.eu_dmf_hint.row_id;


--
-- Name: event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.event (
    row_id bigint NOT NULL,
    event_type text NOT NULL,
    event_date date,
    entity_type text NOT NULL,
    entity_ref bigint,
    detail jsonb,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: event_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.event_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: event_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.event_row_id_seq OWNED BY public.event.row_id;


--
-- Name: evidence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.evidence (
    evidence_id bigint NOT NULL,
    kind text NOT NULL,
    entity_type text,
    entity_ref bigint,
    evidence_quote text,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint
);


--
-- Name: evidence_evidence_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.evidence_evidence_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: evidence_evidence_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.evidence_evidence_id_seq OWNED BY public.evidence.evidence_id;


--
-- Name: gap; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.gap (
    gap_id bigint NOT NULL,
    area text NOT NULL,
    entity_type text,
    entity_ref text,
    reason text NOT NULL,
    where_obtainable text,
    source_name text,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone
);


--
-- Name: gap_gap_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.gap_gap_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: gap_gap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.gap_gap_id_seq OWNED BY public.gap.gap_id;


--
-- Name: market_metric; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.market_metric (
    row_id bigint NOT NULL,
    api_id bigint,
    country character(2),
    metric text NOT NULL,
    unit text NOT NULL,
    period text NOT NULL,
    value numeric,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: market_metric_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.market_metric_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: market_metric_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.market_metric_row_id_seq OWNED BY public.market_metric.row_id;


--
-- Name: patent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.patent (
    row_id bigint NOT NULL,
    api_id bigint,
    number text NOT NULL,
    jurisdiction text NOT NULL,
    patent_type text NOT NULL,
    basic_patent text,
    expiry date,
    patent_status text,
    legal_events jsonb,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: patent_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.patent_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: patent_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.patent_row_id_seq OWNED BY public.patent.row_id;


--
-- Name: product; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product (
    row_id bigint NOT NULL,
    product_id bigint NOT NULL,
    name text NOT NULL,
    country character(2) NOT NULL,
    mah_company_id bigint,
    mah_raw text,
    authorisation_no text,
    strength text,
    form text,
    procedure text,
    procedure_no text,
    product_status text,
    is_veterinary boolean,
    leaflet_url text,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    natural_key text,
    atc text
);


--
-- Name: product_api; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_api (
    product_id bigint NOT NULL,
    api_id bigint NOT NULL,
    substance_raw text
);


--
-- Name: product_manufacturer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.product_manufacturer (
    row_id bigint NOT NULL,
    product_id bigint NOT NULL,
    company_id bigint,
    site_id bigint,
    role text NOT NULL,
    manufacturer_raw text NOT NULL,
    leaflet_url text NOT NULL,
    evidence_quote text NOT NULL,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    site_address_raw text,
    site_country character(2),
    country_basis text
);


--
-- Name: product_manufacturer_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_manufacturer_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_manufacturer_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_manufacturer_row_id_seq OWNED BY public.product_manufacturer.row_id;


--
-- Name: product_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.product_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: product_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.product_row_id_seq OWNED BY public.product.row_id;


--
-- Name: raw_object; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.raw_object (
    raw_id bigint NOT NULL,
    source_id integer,
    url text NOT NULL,
    sha256 character(64) NOT NULL,
    path text NOT NULL,
    content_type text,
    bytes bigint,
    http_status integer,
    retrieved_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: raw_object_raw_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.raw_object_raw_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: raw_object_raw_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.raw_object_raw_id_seq OWNED BY public.raw_object.raw_id;


--
-- Name: site; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.site (
    row_id bigint NOT NULL,
    site_id bigint NOT NULL,
    company_id bigint,
    address text,
    city text,
    postal_code text,
    country character(2),
    fei_number text,
    eudragmdp_id text,
    gmp_status text,
    last_inspection date,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: site_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.site_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: site_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.site_row_id_seq OWNED BY public.site.row_id;


--
-- Name: source; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.source (
    source_id integer NOT NULL,
    name text NOT NULL,
    category text NOT NULL,
    jurisdiction text,
    base_url text NOT NULL,
    probe_url text,
    access_method text,
    http_status integer,
    final_url text,
    robots_status text,
    licence_note text,
    update_frequency text,
    traffic_light text,
    traffic_reason text,
    last_checked timestamp with time zone,
    last_success timestamp with time zone,
    row_count bigint,
    CONSTRAINT source_traffic_light_check CHECK ((traffic_light = ANY (ARRAY['green'::text, 'yellow'::text, 'red'::text])))
);


--
-- Name: source_source_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.source_source_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: source_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.source_source_id_seq OWNED BY public.source.source_id;


--
-- Name: supply_link; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.supply_link (
    row_id bigint NOT NULL,
    from_type text NOT NULL,
    from_id bigint NOT NULL,
    to_type text NOT NULL,
    to_id bigint NOT NULL,
    link_type text NOT NULL,
    confidence public.link_confidence NOT NULL,
    rationale text NOT NULL,
    evidence_ids bigint[] NOT NULL,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone,
    CONSTRAINT supply_link_check CHECK (((confidence = 'confirmed'::public.link_confidence) OR (status = 'derived'::public.data_status))),
    CONSTRAINT supply_link_status_check CHECK ((status = ANY (ARRAY['official'::public.data_status, 'derived'::public.data_status])))
);


--
-- Name: supply_link_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.supply_link_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: supply_link_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.supply_link_row_id_seq OWNED BY public.supply_link.row_id;


--
-- Name: tender; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.tender (
    row_id bigint NOT NULL,
    api_id bigint,
    country character(2),
    buyer text,
    winner_company_id bigint,
    winner_raw text,
    value numeric,
    currency character(3),
    award_date date,
    notice_id text,
    source_url text NOT NULL,
    source_name text NOT NULL,
    retrieved_at timestamp with time zone NOT NULL,
    status public.data_status NOT NULL,
    raw_id bigint,
    valid_from timestamp with time zone DEFAULT now() NOT NULL,
    valid_to timestamp with time zone
);


--
-- Name: tender_row_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.tender_row_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: tender_row_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.tender_row_id_seq OWNED BY public.tender.row_id;


--
-- Name: api row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api ALTER COLUMN row_id SET DEFAULT nextval('public.api_row_id_seq'::regclass);


--
-- Name: api_certificate row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_certificate ALTER COLUMN row_id SET DEFAULT nextval('public.api_certificate_row_id_seq'::regclass);


--
-- Name: company row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company ALTER COLUMN row_id SET DEFAULT nextval('public.company_row_id_seq'::regclass);


--
-- Name: company_relation row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_relation ALTER COLUMN row_id SET DEFAULT nextval('public.company_relation_row_id_seq'::regclass);


--
-- Name: entity_merge_log merge_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_merge_log ALTER COLUMN merge_id SET DEFAULT nextval('public.entity_merge_log_merge_id_seq'::regclass);


--
-- Name: eu_dmf_hint row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eu_dmf_hint ALTER COLUMN row_id SET DEFAULT nextval('public.eu_dmf_hint_row_id_seq'::regclass);


--
-- Name: event row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event ALTER COLUMN row_id SET DEFAULT nextval('public.event_row_id_seq'::regclass);


--
-- Name: evidence evidence_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence ALTER COLUMN evidence_id SET DEFAULT nextval('public.evidence_evidence_id_seq'::regclass);


--
-- Name: gap gap_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gap ALTER COLUMN gap_id SET DEFAULT nextval('public.gap_gap_id_seq'::regclass);


--
-- Name: market_metric row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_metric ALTER COLUMN row_id SET DEFAULT nextval('public.market_metric_row_id_seq'::regclass);


--
-- Name: patent row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patent ALTER COLUMN row_id SET DEFAULT nextval('public.patent_row_id_seq'::regclass);


--
-- Name: product row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product ALTER COLUMN row_id SET DEFAULT nextval('public.product_row_id_seq'::regclass);


--
-- Name: product_manufacturer row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_manufacturer ALTER COLUMN row_id SET DEFAULT nextval('public.product_manufacturer_row_id_seq'::regclass);


--
-- Name: raw_object raw_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_object ALTER COLUMN raw_id SET DEFAULT nextval('public.raw_object_raw_id_seq'::regclass);


--
-- Name: site row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site ALTER COLUMN row_id SET DEFAULT nextval('public.site_row_id_seq'::regclass);


--
-- Name: source source_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source ALTER COLUMN source_id SET DEFAULT nextval('public.source_source_id_seq'::regclass);


--
-- Name: supply_link row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supply_link ALTER COLUMN row_id SET DEFAULT nextval('public.supply_link_row_id_seq'::regclass);


--
-- Name: tender row_id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tender ALTER COLUMN row_id SET DEFAULT nextval('public.tender_row_id_seq'::regclass);


--
-- Name: api_certificate api_certificate_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_certificate
    ADD CONSTRAINT api_certificate_pkey PRIMARY KEY (row_id);


--
-- Name: api api_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api
    ADD CONSTRAINT api_pkey PRIMARY KEY (row_id);


--
-- Name: company company_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company
    ADD CONSTRAINT company_pkey PRIMARY KEY (row_id);


--
-- Name: company_relation company_relation_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_relation
    ADD CONSTRAINT company_relation_pkey PRIMARY KEY (row_id);


--
-- Name: entity_merge_log entity_merge_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.entity_merge_log
    ADD CONSTRAINT entity_merge_log_pkey PRIMARY KEY (merge_id);


--
-- Name: eu_dmf_hint eu_dmf_hint_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.eu_dmf_hint
    ADD CONSTRAINT eu_dmf_hint_pkey PRIMARY KEY (row_id);


--
-- Name: event event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT event_pkey PRIMARY KEY (row_id);


--
-- Name: evidence evidence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_pkey PRIMARY KEY (evidence_id);


--
-- Name: gap gap_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.gap
    ADD CONSTRAINT gap_pkey PRIMARY KEY (gap_id);


--
-- Name: market_metric market_metric_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_metric
    ADD CONSTRAINT market_metric_pkey PRIMARY KEY (row_id);


--
-- Name: patent patent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patent
    ADD CONSTRAINT patent_pkey PRIMARY KEY (row_id);


--
-- Name: product_api product_api_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_api
    ADD CONSTRAINT product_api_pkey PRIMARY KEY (product_id, api_id);


--
-- Name: product_manufacturer product_manufacturer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_manufacturer
    ADD CONSTRAINT product_manufacturer_pkey PRIMARY KEY (row_id);


--
-- Name: product product_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_pkey PRIMARY KEY (row_id);


--
-- Name: raw_object raw_object_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_object
    ADD CONSTRAINT raw_object_pkey PRIMARY KEY (raw_id);


--
-- Name: raw_object raw_object_url_sha256_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_object
    ADD CONSTRAINT raw_object_url_sha256_key UNIQUE (url, sha256);


--
-- Name: site site_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_pkey PRIMARY KEY (row_id);


--
-- Name: source source_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source
    ADD CONSTRAINT source_name_key UNIQUE (name);


--
-- Name: source source_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.source
    ADD CONSTRAINT source_pkey PRIMARY KEY (source_id);


--
-- Name: supply_link supply_link_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.supply_link
    ADD CONSTRAINT supply_link_pkey PRIMARY KEY (row_id);


--
-- Name: tender tender_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tender
    ADD CONSTRAINT tender_pkey PRIMARY KEY (row_id);


--
-- Name: api_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX api_current ON public.api USING btree (api_id) WHERE (valid_to IS NULL);


--
-- Name: api_inn_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX api_inn_trgm ON public.api USING gin (inn public.gin_trgm_ops);


--
-- Name: cert_nk_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX cert_nk_current ON public.api_certificate USING btree (natural_key) WHERE (valid_to IS NULL);


--
-- Name: company_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX company_current ON public.company USING btree (company_id) WHERE (valid_to IS NULL);


--
-- Name: company_name_trgm; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX company_name_trgm ON public.company USING gin (name_normalized public.gin_trgm_ops);


--
-- Name: product_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX product_current ON public.product USING btree (product_id) WHERE (valid_to IS NULL);


--
-- Name: product_nk_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX product_nk_current ON public.product USING btree (natural_key) WHERE (valid_to IS NULL);


--
-- Name: site_current; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX site_current ON public.site USING btree (site_id) WHERE (valid_to IS NULL);


--
-- Name: api_certificate api_certificate_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api_certificate
    ADD CONSTRAINT api_certificate_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: api api_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.api
    ADD CONSTRAINT api_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: company company_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company
    ADD CONSTRAINT company_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: company_relation company_relation_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.company_relation
    ADD CONSTRAINT company_relation_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: event event_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.event
    ADD CONSTRAINT event_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: evidence evidence_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.evidence
    ADD CONSTRAINT evidence_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: market_metric market_metric_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.market_metric
    ADD CONSTRAINT market_metric_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: patent patent_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.patent
    ADD CONSTRAINT patent_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: product_manufacturer product_manufacturer_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product_manufacturer
    ADD CONSTRAINT product_manufacturer_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: product product_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.product
    ADD CONSTRAINT product_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: raw_object raw_object_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.raw_object
    ADD CONSTRAINT raw_object_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.source(source_id);


--
-- Name: site site_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.site
    ADD CONSTRAINT site_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- Name: tender tender_raw_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.tender
    ADD CONSTRAINT tender_raw_id_fkey FOREIGN KEY (raw_id) REFERENCES public.raw_object(raw_id);


--
-- PostgreSQL database dump complete
--

\unrestrict vK4vBJsyhKs9aDMnQEDHQcrlFacUK0mMBQggamEKVDkRhPnYqSSt1hGFRHxVncY

