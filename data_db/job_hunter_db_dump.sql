--
-- PostgreSQL database cluster dump
--

\restrict wAoX3xmHfFXMh7ffFgwflOHkOhd88SnMqxY3IhUVrgCiWWfKqOh761uTNZdxLaU

SET default_transaction_read_only = off;

SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;

--
-- Roles
--

CREATE ROLE jh_user;
ALTER ROLE jh_user WITH SUPERUSER INHERIT CREATEROLE CREATEDB LOGIN REPLICATION BYPASSRLS PASSWORD 'SCRAM-SHA-256$4096:gJKMyxLM07RBsTOaccF1OQ==$T9t2yMjmnxdPyvSUVzSYBwW5jpaxpV7Y1jeei4NIAQ4=:j8t2X8k3mdu+jYfyKrM82SEjhictiW2GB6RQ62bLOZA=';

--
-- User Configurations
--








\unrestrict wAoX3xmHfFXMh7ffFgwflOHkOhd88SnMqxY3IhUVrgCiWWfKqOh761uTNZdxLaU

--
-- Databases
--

--
-- Database "template1" dump
--

\connect template1

--
-- PostgreSQL database dump
--

\restrict d93UeYaoI8zlgFnaQ46TVZT9sS1oUSMPijHTTyvhXuUryKTIzJGYPLhlyxhYRhM

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

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
-- PostgreSQL database dump complete
--

\unrestrict d93UeYaoI8zlgFnaQ46TVZT9sS1oUSMPijHTTyvhXuUryKTIzJGYPLhlyxhYRhM

--
-- Database "job_hunter_stats" dump
--

--
-- PostgreSQL database dump
--

\restrict BIMUcbONWcgbulDBnIMlqTV4FAINBBAcRiZISPBI5NnoPvxXw2YZW9kFSqpO7Tr

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

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
-- Name: job_hunter_stats; Type: DATABASE; Schema: -; Owner: jh_user
--

CREATE DATABASE job_hunter_stats WITH TEMPLATE = template0 ENCODING = 'UTF8' LOCALE_PROVIDER = libc LOCALE = 'en_US.utf8';


ALTER DATABASE job_hunter_stats OWNER TO jh_user;

\unrestrict BIMUcbONWcgbulDBnIMlqTV4FAINBBAcRiZISPBI5NnoPvxXw2YZW9kFSqpO7Tr
\connect job_hunter_stats
\restrict BIMUcbONWcgbulDBnIMlqTV4FAINBBAcRiZISPBI5NnoPvxXw2YZW9kFSqpO7Tr

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: portfolio_stats; Type: TABLE; Schema: public; Owner: jh_user
--

CREATE TABLE public.portfolio_stats (
    key character varying(50) NOT NULL,
    value integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.portfolio_stats OWNER TO jh_user;

--
-- Name: stats; Type: TABLE; Schema: public; Owner: jh_user
--

CREATE TABLE public.stats (
    key character varying(50) NOT NULL,
    value integer DEFAULT 0 NOT NULL
);


ALTER TABLE public.stats OWNER TO jh_user;

--
-- Data for Name: portfolio_stats; Type: TABLE DATA; Schema: public; Owner: jh_user
--

COPY public.portfolio_stats (key, value) FROM stdin;
visitors	84
\.


--
-- Data for Name: stats; Type: TABLE DATA; Schema: public; Owner: jh_user
--

COPY public.stats (key, value) FROM stdin;
visitors	12780
\.


--
-- Name: portfolio_stats portfolio_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: jh_user
--

ALTER TABLE ONLY public.portfolio_stats
    ADD CONSTRAINT portfolio_stats_pkey PRIMARY KEY (key);


--
-- Name: stats stats_pkey; Type: CONSTRAINT; Schema: public; Owner: jh_user
--

ALTER TABLE ONLY public.stats
    ADD CONSTRAINT stats_pkey PRIMARY KEY (key);


--
-- PostgreSQL database dump complete
--

\unrestrict BIMUcbONWcgbulDBnIMlqTV4FAINBBAcRiZISPBI5NnoPvxXw2YZW9kFSqpO7Tr

--
-- Database "postgres" dump
--

\connect postgres

--
-- PostgreSQL database dump
--

\restrict MH4LDLnu1Eti7UIXTgQ4rsqCS5jMrvR4YnFIQKvfchdoAARU3xoYBh9Dbyf4HCH

-- Dumped from database version 15.18
-- Dumped by pg_dump version 15.18

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
-- PostgreSQL database dump complete
--

\unrestrict MH4LDLnu1Eti7UIXTgQ4rsqCS5jMrvR4YnFIQKvfchdoAARU3xoYBh9Dbyf4HCH

--
-- PostgreSQL database cluster dump complete
--

