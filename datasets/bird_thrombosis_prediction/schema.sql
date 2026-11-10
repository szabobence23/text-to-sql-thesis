-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database thrombosis_prediction.
-- Written by database/import_bird.py.

CREATE TABLE public.examination (
    id bigint,
    "Examination Date" date,
    "aCL IgG" real,
    "aCL IgM" real,
    ana bigint,
    "ANA Pattern" text,
    "aCL IgA" bigint,
    diagnosis text,
    kct text,
    rvvt text,
    lac text,
    symptoms text,
    thrombosis bigint
);

CREATE TABLE public.patient (
    id bigint DEFAULT '0'::bigint NOT NULL,
    sex text,
    birthday date,
    description date,
    "First Date" date,
    admission text,
    diagnosis text
);

CREATE TABLE public.laboratory (
    id bigint DEFAULT '0'::bigint,
    date date,
    got bigint,
    gpt bigint,
    ldh bigint,
    alp bigint,
    tp real,
    alb real,
    ua real,
    un bigint,
    cre real,
    "T-BIL" real,
    "T-CHO" bigint,
    tg bigint,
    cpk bigint,
    glu bigint,
    wbc real,
    rbc real,
    hgb real,
    hct real,
    plt bigint,
    pt real,
    aptt bigint,
    fg real,
    pic bigint,
    tat bigint,
    tat2 bigint,
    "U-PRO" text,
    igg bigint,
    iga bigint,
    igm bigint,
    crp text,
    ra text,
    rf text,
    c3 bigint,
    c4 bigint,
    rnp text,
    sm text,
    sc170 text,
    ssa text,
    ssb text,
    centromea text,
    dna text,
    "DNA-II" bigint
);

ALTER TABLE ONLY public.patient
    ADD CONSTRAINT idx_16904_patient_pkey PRIMARY KEY (id);
CREATE UNIQUE INDEX idx_16910_sqlite_autoindex_laboratory_1 ON public.laboratory USING btree (id, date);
ALTER TABLE ONLY public.examination
    ADD CONSTRAINT examination_id_fkey FOREIGN KEY (id) REFERENCES public.patient(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.laboratory
    ADD CONSTRAINT laboratory_id_fkey FOREIGN KEY (id) REFERENCES public.patient(id) ON UPDATE CASCADE ON DELETE CASCADE;
