-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database formula_1.
-- Written by database/import_bird.py.

CREATE TABLE public.circuits (
    circuitid bigint NOT NULL,
    circuitref text DEFAULT ''::text,
    name text DEFAULT ''::text,
    location text,
    country text,
    lat real,
    lng real,
    alt bigint,
    url text DEFAULT ''::text
);

CREATE TABLE public.constructors (
    constructorid bigint NOT NULL,
    constructorref text DEFAULT ''::text,
    name text DEFAULT ''::text,
    nationality text,
    url text DEFAULT ''::text
);

CREATE TABLE public.drivers (
    driverid bigint NOT NULL,
    driverref text DEFAULT ''::text,
    number bigint,
    code text,
    forename text DEFAULT ''::text,
    surname text DEFAULT ''::text,
    dob date,
    nationality text,
    url text DEFAULT ''::text
);

CREATE TABLE public.seasons (
    year bigint DEFAULT '0'::bigint NOT NULL,
    url text DEFAULT ''::text
);

CREATE TABLE public.races (
    raceid bigint NOT NULL,
    year bigint DEFAULT '0'::bigint,
    round bigint DEFAULT '0'::bigint,
    circuitid bigint DEFAULT '0'::bigint,
    name text DEFAULT ''::text,
    date date,
    "time" text,
    url text
);

CREATE TABLE public.constructorresults (
    constructorresultsid bigint NOT NULL,
    raceid bigint DEFAULT '0'::bigint,
    constructorid bigint DEFAULT '0'::bigint,
    points real,
    status text
);

CREATE TABLE public.constructorstandings (
    constructorstandingsid bigint NOT NULL,
    raceid bigint DEFAULT '0'::bigint,
    constructorid bigint DEFAULT '0'::bigint,
    points real DEFAULT '0'::real,
    "position" bigint,
    positiontext text,
    wins bigint DEFAULT '0'::bigint
);

CREATE TABLE public.driverstandings (
    driverstandingsid bigint NOT NULL,
    raceid bigint DEFAULT '0'::bigint,
    driverid bigint DEFAULT '0'::bigint,
    points real DEFAULT '0'::real,
    "position" bigint,
    positiontext text,
    wins bigint DEFAULT '0'::bigint
);

CREATE TABLE public.laptimes (
    raceid bigint NOT NULL,
    driverid bigint NOT NULL,
    lap bigint NOT NULL,
    "position" bigint,
    "time" text,
    milliseconds bigint
);

CREATE TABLE public.pitstops (
    raceid bigint NOT NULL,
    driverid bigint NOT NULL,
    stop bigint NOT NULL,
    lap bigint,
    "time" text,
    duration text,
    milliseconds bigint
);

CREATE TABLE public.qualifying (
    qualifyid bigint NOT NULL,
    raceid bigint DEFAULT '0'::bigint,
    driverid bigint DEFAULT '0'::bigint,
    constructorid bigint DEFAULT '0'::bigint,
    number bigint DEFAULT '0'::bigint,
    "position" bigint,
    q1 text,
    q2 text,
    q3 text
);

CREATE TABLE public.status (
    statusid bigint NOT NULL,
    status text DEFAULT ''::text
);

CREATE TABLE public.results (
    resultid bigint NOT NULL,
    raceid bigint DEFAULT '0'::bigint,
    driverid bigint DEFAULT '0'::bigint,
    constructorid bigint DEFAULT '0'::bigint,
    number bigint,
    grid bigint DEFAULT '0'::bigint,
    "position" bigint,
    positiontext text DEFAULT ''::text,
    positionorder bigint DEFAULT '0'::bigint,
    points real DEFAULT '0'::real,
    laps bigint DEFAULT '0'::bigint,
    "time" text,
    milliseconds bigint,
    fastestlap bigint,
    rank bigint DEFAULT '0'::bigint,
    fastestlaptime text,
    fastestlapspeed text,
    statusid bigint DEFAULT '0'::bigint
);

ALTER TABLE ONLY public.circuits
    ADD CONSTRAINT idx_17559_circuits_pkey PRIMARY KEY (circuitid);
ALTER TABLE ONLY public.constructors
    ADD CONSTRAINT idx_17569_constructors_pkey PRIMARY KEY (constructorid);
ALTER TABLE ONLY public.drivers
    ADD CONSTRAINT idx_17579_drivers_pkey PRIMARY KEY (driverid);
ALTER TABLE ONLY public.seasons
    ADD CONSTRAINT idx_17589_seasons_pkey PRIMARY KEY (year);
ALTER TABLE ONLY public.races
    ADD CONSTRAINT idx_17597_races_pkey PRIMARY KEY (raceid);
ALTER TABLE ONLY public.constructorresults
    ADD CONSTRAINT idx_17608_constructorresults_pkey PRIMARY KEY (constructorresultsid);
ALTER TABLE ONLY public.constructorstandings
    ADD CONSTRAINT idx_17617_constructorstandings_pkey PRIMARY KEY (constructorstandingsid);
ALTER TABLE ONLY public.driverstandings
    ADD CONSTRAINT idx_17628_driverstandings_pkey PRIMARY KEY (driverstandingsid);
ALTER TABLE ONLY public.laptimes
    ADD CONSTRAINT idx_17638_laptimes_pkey PRIMARY KEY (raceid, driverid, lap);
ALTER TABLE ONLY public.pitstops
    ADD CONSTRAINT idx_17643_pitstops_pkey PRIMARY KEY (raceid, driverid, stop);
ALTER TABLE ONLY public.qualifying
    ADD CONSTRAINT idx_17649_qualifying_pkey PRIMARY KEY (qualifyid);
ALTER TABLE ONLY public.status
    ADD CONSTRAINT idx_17660_status_pkey PRIMARY KEY (statusid);
ALTER TABLE ONLY public.results
    ADD CONSTRAINT idx_17668_results_pkey PRIMARY KEY (resultid);
CREATE UNIQUE INDEX idx_17559_sqlite_autoindex_circuits_1 ON public.circuits USING btree (url);
CREATE UNIQUE INDEX idx_17569_sqlite_autoindex_constructors_1 ON public.constructors USING btree (name);
CREATE UNIQUE INDEX idx_17579_sqlite_autoindex_drivers_1 ON public.drivers USING btree (url);
CREATE UNIQUE INDEX idx_17589_sqlite_autoindex_seasons_1 ON public.seasons USING btree (url);
CREATE UNIQUE INDEX idx_17597_sqlite_autoindex_races_1 ON public.races USING btree (url);
CREATE UNIQUE INDEX idx_17638_sqlite_autoindex_laptimes_1 ON public.laptimes USING btree (raceid, driverid, lap);
CREATE UNIQUE INDEX idx_17643_sqlite_autoindex_pitstops_1 ON public.pitstops USING btree (raceid, driverid, stop);
ALTER TABLE ONLY public.races
    ADD CONSTRAINT races_circuitid_fkey FOREIGN KEY (circuitid) REFERENCES public.circuits(circuitid);
ALTER TABLE ONLY public.races
    ADD CONSTRAINT races_year_fkey FOREIGN KEY (year) REFERENCES public.seasons(year);
ALTER TABLE ONLY public.constructorresults
    ADD CONSTRAINT constructorresults_constructorid_fkey FOREIGN KEY (constructorid) REFERENCES public.constructors(constructorid);
ALTER TABLE ONLY public.constructorstandings
    ADD CONSTRAINT constructorstandings_constructorid_fkey FOREIGN KEY (constructorid) REFERENCES public.constructors(constructorid);
ALTER TABLE ONLY public.driverstandings
    ADD CONSTRAINT driverstandings_driverid_fkey FOREIGN KEY (driverid) REFERENCES public.drivers(driverid);
ALTER TABLE ONLY public.laptimes
    ADD CONSTRAINT laptimes_driverid_fkey FOREIGN KEY (driverid) REFERENCES public.drivers(driverid);
ALTER TABLE ONLY public.laptimes
    ADD CONSTRAINT laptimes_raceid_fkey FOREIGN KEY (raceid) REFERENCES public.races(raceid);
ALTER TABLE ONLY public.pitstops
    ADD CONSTRAINT pitstops_driverid_fkey FOREIGN KEY (driverid) REFERENCES public.drivers(driverid);
ALTER TABLE ONLY public.pitstops
    ADD CONSTRAINT pitstops_raceid_fkey FOREIGN KEY (raceid) REFERENCES public.races(raceid);
ALTER TABLE ONLY public.qualifying
    ADD CONSTRAINT qualifying_constructorid_fkey FOREIGN KEY (constructorid) REFERENCES public.constructors(constructorid);
ALTER TABLE ONLY public.qualifying
    ADD CONSTRAINT qualifying_driverid_fkey FOREIGN KEY (driverid) REFERENCES public.drivers(driverid);
ALTER TABLE ONLY public.qualifying
    ADD CONSTRAINT qualifying_raceid_fkey FOREIGN KEY (raceid) REFERENCES public.races(raceid);
ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_constructorid_fkey FOREIGN KEY (constructorid) REFERENCES public.constructors(constructorid);
ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_driverid_fkey FOREIGN KEY (driverid) REFERENCES public.drivers(driverid);
ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_raceid_fkey FOREIGN KEY (raceid) REFERENCES public.races(raceid);
ALTER TABLE ONLY public.results
    ADD CONSTRAINT results_statusid_fkey FOREIGN KEY (statusid) REFERENCES public.status(statusid);
