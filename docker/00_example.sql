--
-- PostgreSQL database dump
--

-- Dumped from database version 9.6.10
-- Dumped by pg_dump version 9.6.10

-- Started on 2018-09-16 14:30:09 EDT

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET client_min_messages = warning;
SET row_security = off;

--
-- TOC entry 1 (class 3079 OID 12393)
-- Name: plpgsql; Type: EXTENSION; Schema: -; Owner: 
--

CREATE EXTENSION IF NOT EXISTS plpgsql WITH SCHEMA pg_catalog;


--
-- TOC entry 2213 (class 0 OID 0)
-- Dependencies: 1
-- Name: EXTENSION plpgsql; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION plpgsql IS 'PL/pgSQL procedural language';


SET default_tablespace = '';

SET default_with_oids = false;

--
-- TOC entry 185 (class 1259 OID 16386)
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO argus;

--
-- TOC entry 187 (class 1259 OID 16393)
-- Name: alert; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.alert (
    id integer NOT NULL,
    arm_type character varying,
    start_time timestamp with time zone,
    end_time timestamp with time zone
);


ALTER TABLE public.alert OWNER TO argus;

--
-- TOC entry 186 (class 1259 OID 16391)
-- Name: alert_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.alert_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.alert_id_seq OWNER TO argus;

--
-- TOC entry 2214 (class 0 OID 0)
-- Dependencies: 186
-- Name: alert_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.alert_id_seq OWNED BY public.alert.id;


--
-- TOC entry 198 (class 1259 OID 16464)
-- Name: alert_sensor; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.alert_sensor (
    alert_id integer NOT NULL,
    sensor_id integer NOT NULL,
    channel integer,
    description character varying
);


ALTER TABLE public.alert_sensor OWNER TO argus;

--
-- TOC entry 189 (class 1259 OID 16404)
-- Name: option; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.option (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    section character varying(32) NOT NULL,
    value character varying
);


ALTER TABLE public.option OWNER TO argus;

--
-- TOC entry 188 (class 1259 OID 16402)
-- Name: option_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.option_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.option_id_seq OWNER TO argus;

--
-- TOC entry 2215 (class 0 OID 0)
-- Dependencies: 188
-- Name: option_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.option_id_seq OWNED BY public.option.id;


--
-- TOC entry 197 (class 1259 OID 16445)
-- Name: sensor; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.sensor (
    id integer NOT NULL,
    channel integer NOT NULL,
    reference_value double precision,
    alert boolean,
    enabled boolean,
    deleted boolean,
    description character varying NOT NULL,
    zone_id integer NOT NULL,
    type_id integer NOT NULL
);


ALTER TABLE public.sensor OWNER TO argus;

--
-- TOC entry 196 (class 1259 OID 16443)
-- Name: sensor_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.sensor_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sensor_id_seq OWNER TO argus;

--
-- TOC entry 2216 (class 0 OID 0)
-- Dependencies: 196
-- Name: sensor_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.sensor_id_seq OWNED BY public.sensor.id;


--
-- TOC entry 191 (class 1259 OID 16415)
-- Name: sensor_type; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.sensor_type (
    id integer NOT NULL,
    name character varying(16),
    description character varying
);


ALTER TABLE public.sensor_type OWNER TO argus;

--
-- TOC entry 190 (class 1259 OID 16413)
-- Name: sensor_type_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.sensor_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.sensor_type_id_seq OWNER TO argus;

--
-- TOC entry 2217 (class 0 OID 0)
-- Dependencies: 190
-- Name: sensor_type_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.sensor_type_id_seq OWNED BY public.sensor_type.id;


--
-- TOC entry 193 (class 1259 OID 16426)
-- Name: user; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public."user" (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    role character varying(12) NOT NULL,
    access_code character varying NOT NULL
);


ALTER TABLE public."user" OWNER TO argus;

--
-- TOC entry 192 (class 1259 OID 16424)
-- Name: user_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.user_id_seq OWNER TO argus;

--
-- TOC entry 2218 (class 0 OID 0)
-- Dependencies: 192
-- Name: user_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.user_id_seq OWNED BY public."user".id;


--
-- TOC entry 195 (class 1259 OID 16437)
-- Name: zone; Type: TABLE; Schema: public; Owner: argus
--

CREATE TABLE public.zone (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    description character varying(128) NOT NULL,
    disarmed_delay integer,
    away_delay integer,
    stay_delay integer,
    deleted boolean
);


ALTER TABLE public.zone OWNER TO argus;

--
-- TOC entry 194 (class 1259 OID 16435)
-- Name: zone_id_seq; Type: SEQUENCE; Schema: public; Owner: argus
--

CREATE SEQUENCE public.zone_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER TABLE public.zone_id_seq OWNER TO argus;

--
-- TOC entry 2219 (class 0 OID 0)
-- Dependencies: 194
-- Name: zone_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: argus
--

ALTER SEQUENCE public.zone_id_seq OWNED BY public.zone.id;


--
-- TOC entry 2049 (class 2604 OID 16396)
-- Name: alert id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alert ALTER COLUMN id SET DEFAULT nextval('public.alert_id_seq'::regclass);


--
-- TOC entry 2050 (class 2604 OID 16407)
-- Name: option id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.option ALTER COLUMN id SET DEFAULT nextval('public.option_id_seq'::regclass);


--
-- TOC entry 2054 (class 2604 OID 16448)
-- Name: sensor id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor ALTER COLUMN id SET DEFAULT nextval('public.sensor_id_seq'::regclass);


--
-- TOC entry 2051 (class 2604 OID 16418)
-- Name: sensor_type id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor_type ALTER COLUMN id SET DEFAULT nextval('public.sensor_type_id_seq'::regclass);


--
-- TOC entry 2052 (class 2604 OID 16429)
-- Name: user id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public."user" ALTER COLUMN id SET DEFAULT nextval('public.user_id_seq'::regclass);


--
-- TOC entry 2053 (class 2604 OID 16440)
-- Name: zone id; Type: DEFAULT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.zone ALTER COLUMN id SET DEFAULT nextval('public.zone_id_seq'::regclass);


--
-- TOC entry 2192 (class 0 OID 16386)
-- Dependencies: 185
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: argus
--

INSERT INTO public.alembic_version VALUES ('4a8924399555');


--
-- TOC entry 2194 (class 0 OID 16393)
-- Dependencies: 187
-- Data for Name: alert; Type: TABLE DATA; Schema: public; Owner: argus
--



--
-- TOC entry 2220 (class 0 OID 0)
-- Dependencies: 186
-- Name: alert_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.alert_id_seq', 1, false);


--
-- TOC entry 2205 (class 0 OID 16464)
-- Dependencies: 198
-- Data for Name: alert_sensor; Type: TABLE DATA; Schema: public; Owner: argus
--



--
-- TOC entry 2196 (class 0 OID 16404)
-- Dependencies: 189
-- Data for Name: option; Type: TABLE DATA; Schema: public; Owner: argus
--



--
-- TOC entry 2221 (class 0 OID 0)
-- Dependencies: 188
-- Name: option_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.option_id_seq', 1, false);


--
-- TOC entry 2204 (class 0 OID 16445)
-- Dependencies: 197
-- Data for Name: sensor; Type: TABLE DATA; Schema: public; Owner: argus
--



--
-- TOC entry 2222 (class 0 OID 0)
-- Dependencies: 196
-- Name: sensor_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.sensor_id_seq', 1, false);


--
-- TOC entry 2198 (class 0 OID 16415)
-- Dependencies: 191
-- Data for Name: sensor_type; Type: TABLE DATA; Schema: public; Owner: argus
--

INSERT INTO public.sensor_type VALUES (1, 'Motion sensor', 'Detect motion');
INSERT INTO public.sensor_type VALUES (2, 'Break sensor', 'Detect glass break');
INSERT INTO public.sensor_type VALUES (3, 'Tamper', 'Detect sabotage');


--
-- TOC entry 2223 (class 0 OID 0)
-- Dependencies: 190
-- Name: sensor_type_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.sensor_type_id_seq', 3, true);


--
-- TOC entry 2200 (class 0 OID 16426)
-- Dependencies: 193
-- Data for Name: user; Type: TABLE DATA; Schema: public; Owner: argus
--

INSERT INTO public."user" VALUES (1, 'Administrator', 'admin', 'e759a98f792dbc86a16fb0d09df886bd2c5ebc72657794f63293ab7c5cb7caee');


--
-- TOC entry 2224 (class 0 OID 0)
-- Dependencies: 192
-- Name: user_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.user_id_seq', 1, true);


--
-- TOC entry 2202 (class 0 OID 16437)
-- Dependencies: 195
-- Data for Name: zone; Type: TABLE DATA; Schema: public; Owner: argus
--



--
-- TOC entry 2225 (class 0 OID 0)
-- Dependencies: 194
-- Name: zone_id_seq; Type: SEQUENCE SET; Schema: public; Owner: argus
--

SELECT pg_catalog.setval('public.zone_id_seq', 1, false);


--
-- TOC entry 2056 (class 2606 OID 16390)
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- TOC entry 2058 (class 2606 OID 16401)
-- Name: alert alert_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alert
    ADD CONSTRAINT alert_pkey PRIMARY KEY (id);


--
-- TOC entry 2070 (class 2606 OID 16471)
-- Name: alert_sensor alert_sensor_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alert_sensor
    ADD CONSTRAINT alert_sensor_pkey PRIMARY KEY (alert_id, sensor_id);


--
-- TOC entry 2060 (class 2606 OID 16412)
-- Name: option option_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.option
    ADD CONSTRAINT option_pkey PRIMARY KEY (id);


--
-- TOC entry 2068 (class 2606 OID 16453)
-- Name: sensor sensor_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor
    ADD CONSTRAINT sensor_pkey PRIMARY KEY (id);


--
-- TOC entry 2062 (class 2606 OID 16423)
-- Name: sensor_type sensor_type_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor_type
    ADD CONSTRAINT sensor_type_pkey PRIMARY KEY (id);


--
-- TOC entry 2064 (class 2606 OID 16434)
-- Name: user user_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public."user"
    ADD CONSTRAINT user_pkey PRIMARY KEY (id);


--
-- TOC entry 2066 (class 2606 OID 16442)
-- Name: zone zone_pkey; Type: CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.zone
    ADD CONSTRAINT zone_pkey PRIMARY KEY (id);


--
-- TOC entry 2073 (class 2606 OID 16472)
-- Name: alert_sensor alert_sensor_alert_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alert_sensor
    ADD CONSTRAINT alert_sensor_alert_id_fkey FOREIGN KEY (alert_id) REFERENCES public.alert(id);


--
-- TOC entry 2074 (class 2606 OID 16477)
-- Name: alert_sensor alert_sensor_sensor_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.alert_sensor
    ADD CONSTRAINT alert_sensor_sensor_id_fkey FOREIGN KEY (sensor_id) REFERENCES public.sensor(id);


--
-- TOC entry 2071 (class 2606 OID 16454)
-- Name: sensor sensor_type_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor
    ADD CONSTRAINT sensor_type_id_fkey FOREIGN KEY (type_id) REFERENCES public.sensor_type(id);


--
-- TOC entry 2072 (class 2606 OID 16459)
-- Name: sensor sensor_zone_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: argus
--

ALTER TABLE ONLY public.sensor
    ADD CONSTRAINT sensor_zone_id_fkey FOREIGN KEY (zone_id) REFERENCES public.zone(id);


-- Completed on 2018-09-16 14:30:11 EDT

--
-- PostgreSQL database dump complete
--
