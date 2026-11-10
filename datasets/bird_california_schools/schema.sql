-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database california_schools.
-- Written by database/import_bird.py.

CREATE TABLE public.frpm (
    cdscode text,
    "Academic Year" text,
    "County Code" text,
    "District Code" bigint,
    "School Code" text,
    "County Name" text,
    "District Name" text,
    "School Name" text,
    "District Type" text,
    "School Type" text,
    "Educational Option Type" text,
    "NSLP Provision Status" text,
    "Charter School (Y/N)" bigint,
    "Charter School Number" text,
    "Charter Funding Type" text,
    irc bigint,
    "Low Grade" text,
    "High Grade" text,
    "Enrollment (K-12)" real,
    "Free Meal Count (K-12)" real,
    "Percent (%) Eligible Free (K-12)" real,
    "FRPM Count (K-12)" real,
    "Percent (%) Eligible FRPM (K-12)" real,
    "Enrollment (Ages 5-17)" real,
    "Free Meal Count (Ages 5-17)" real,
    "Percent (%) Eligible Free (Ages 5-17)" real,
    "FRPM Count (Ages 5-17)" real,
    "Percent (%) Eligible FRPM (Ages 5-17)" real,
    "2013-14 CALPADS Fall 1 Certification Status" bigint
);

CREATE TABLE public.satscores (
    cds text NOT NULL,
    rtype text,
    sname text,
    dname text,
    cname text,
    enroll12 bigint,
    numtsttakr bigint,
    avgscrread bigint,
    avgscrmath bigint,
    avgscrwrite bigint,
    numge1500 bigint
);

CREATE TABLE public.schools (
    cdscode text,
    ncesdist text,
    ncesschool text,
    statustype text,
    county text,
    district text,
    school text,
    street text,
    streetabr text,
    city text,
    zip text,
    state text,
    mailstreet text,
    mailstrabr text,
    mailcity text,
    mailzip text,
    mailstate text,
    phone text,
    ext text,
    website text,
    opendate date,
    closeddate date,
    charter bigint,
    charternum text,
    fundingtype text,
    doc text,
    doctype text,
    soc text,
    soctype text,
    edopscode text,
    edopsname text,
    eilcode text,
    eilname text,
    gsoffered text,
    gsserved text,
    virtual text,
    magnet bigint,
    latitude real,
    longitude real,
    admfname1 text,
    admlname1 text,
    admemail1 text,
    admfname2 text,
    admlname2 text,
    admemail2 text,
    admfname3 text,
    admlname3 text,
    admemail3 text,
    lastupdate date
);

ALTER TABLE ONLY public.satscores
    ADD CONSTRAINT idx_48501_sqlite_autoindex_satscores_1 PRIMARY KEY (cds);
CREATE UNIQUE INDEX idx_48496_sqlite_autoindex_frpm_1 ON public.frpm USING btree (cdscode);
CREATE UNIQUE INDEX idx_48506_sqlite_autoindex_schools_1 ON public.schools USING btree (cdscode);
ALTER TABLE ONLY public.frpm
    ADD CONSTRAINT frpm_cdscode_fkey FOREIGN KEY (cdscode) REFERENCES public.schools(cdscode);
ALTER TABLE ONLY public.satscores
    ADD CONSTRAINT satscores_cds_fkey FOREIGN KEY (cds) REFERENCES public.schools(cdscode);
