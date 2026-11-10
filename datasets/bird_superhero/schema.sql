-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database superhero.
-- Written by database/import_bird.py.

CREATE TABLE public.alignment (
    id bigint NOT NULL,
    alignment text
);

CREATE TABLE public.attribute (
    id bigint NOT NULL,
    attribute_name text
);

CREATE TABLE public.colour (
    id bigint NOT NULL,
    colour text
);

CREATE TABLE public.gender (
    id bigint NOT NULL,
    gender text
);

CREATE TABLE public.publisher (
    id bigint NOT NULL,
    publisher_name text
);

CREATE TABLE public.race (
    id bigint NOT NULL,
    race text
);

CREATE TABLE public.superhero (
    id bigint NOT NULL,
    superhero_name text,
    full_name text,
    gender_id bigint,
    eye_colour_id bigint,
    hair_colour_id bigint,
    skin_colour_id bigint,
    race_id bigint,
    publisher_id bigint,
    alignment_id bigint,
    height_cm bigint,
    weight_kg bigint
);

CREATE TABLE public.hero_attribute (
    hero_id bigint,
    attribute_id bigint,
    attribute_value bigint
);

CREATE TABLE public.superpower (
    id bigint NOT NULL,
    power_name text
);

CREATE TABLE public.hero_power (
    hero_id bigint,
    power_id bigint
);

ALTER TABLE ONLY public.alignment
    ADD CONSTRAINT idx_16745_alignment_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.attribute
    ADD CONSTRAINT idx_16750_attribute_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.colour
    ADD CONSTRAINT idx_16755_colour_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.gender
    ADD CONSTRAINT idx_16760_gender_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.publisher
    ADD CONSTRAINT idx_16765_publisher_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.race
    ADD CONSTRAINT idx_16770_race_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT idx_16775_superhero_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.superpower
    ADD CONSTRAINT idx_16783_superpower_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_alignment_id_fkey FOREIGN KEY (alignment_id) REFERENCES public.alignment(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_eye_colour_id_fkey FOREIGN KEY (eye_colour_id) REFERENCES public.colour(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_gender_id_fkey FOREIGN KEY (gender_id) REFERENCES public.gender(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_hair_colour_id_fkey FOREIGN KEY (hair_colour_id) REFERENCES public.colour(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_publisher_id_fkey FOREIGN KEY (publisher_id) REFERENCES public.publisher(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_race_id_fkey FOREIGN KEY (race_id) REFERENCES public.race(id);
ALTER TABLE ONLY public.superhero
    ADD CONSTRAINT superhero_skin_colour_id_fkey FOREIGN KEY (skin_colour_id) REFERENCES public.colour(id);
ALTER TABLE ONLY public.hero_attribute
    ADD CONSTRAINT hero_attribute_attribute_id_fkey FOREIGN KEY (attribute_id) REFERENCES public.attribute(id);
ALTER TABLE ONLY public.hero_attribute
    ADD CONSTRAINT hero_attribute_hero_id_fkey FOREIGN KEY (hero_id) REFERENCES public.superhero(id);
ALTER TABLE ONLY public.hero_power
    ADD CONSTRAINT hero_power_hero_id_fkey FOREIGN KEY (hero_id) REFERENCES public.superhero(id);
ALTER TABLE ONLY public.hero_power
    ADD CONSTRAINT hero_power_power_id_fkey FOREIGN KEY (power_id) REFERENCES public.superpower(id);
