-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database card_games.
-- Written by database/import_bird.py.

CREATE TABLE public.cards (
    id bigint NOT NULL,
    artist text,
    asciiname text,
    availability text,
    bordercolor text,
    cardkingdomfoilid text,
    cardkingdomid text,
    coloridentity text,
    colorindicator text,
    colors text,
    convertedmanacost real,
    dueldeck text,
    edhrecrank bigint,
    faceconvertedmanacost real,
    facename text,
    flavorname text,
    flavortext text,
    frameeffects text,
    frameversion text,
    hand text,
    hasalternativedecklimit bigint DEFAULT '0'::bigint,
    hascontentwarning bigint DEFAULT '0'::bigint,
    hasfoil bigint DEFAULT '0'::bigint,
    hasnonfoil bigint DEFAULT '0'::bigint,
    isalternative bigint DEFAULT '0'::bigint,
    isfullart bigint DEFAULT '0'::bigint,
    isonlineonly bigint DEFAULT '0'::bigint,
    isoversized bigint DEFAULT '0'::bigint,
    ispromo bigint DEFAULT '0'::bigint,
    isreprint bigint DEFAULT '0'::bigint,
    isreserved bigint DEFAULT '0'::bigint,
    isstarter bigint DEFAULT '0'::bigint,
    isstoryspotlight bigint DEFAULT '0'::bigint,
    istextless bigint DEFAULT '0'::bigint,
    istimeshifted bigint DEFAULT '0'::bigint,
    keywords text,
    layout text,
    leadershipskills text,
    life text,
    loyalty text,
    manacost text,
    mcmid text,
    mcmmetaid text,
    mtgarenaid text,
    mtgjsonv4id text,
    mtgofoilid text,
    mtgoid text,
    multiverseid text,
    name text,
    number text,
    originalreleasedate text,
    originaltext text,
    originaltype text,
    otherfaceids text,
    power text,
    printings text,
    promotypes text,
    purchaseurls text,
    rarity text,
    scryfallid text,
    scryfallillustrationid text,
    scryfalloracleid text,
    setcode text,
    side text,
    subtypes text,
    supertypes text,
    tcgplayerproductid text,
    text text,
    toughness text,
    type text,
    types text,
    uuid text,
    variations text,
    watermark text
);

CREATE TABLE public.foreign_data (
    id bigint NOT NULL,
    flavortext text,
    language text,
    multiverseid bigint,
    name text,
    text text,
    type text,
    uuid text
);

CREATE TABLE public.legalities (
    id bigint NOT NULL,
    format text,
    status text,
    uuid text
);

CREATE TABLE public.sets (
    id bigint NOT NULL,
    basesetsize bigint,
    block text,
    booster text,
    code text,
    isfoilonly bigint DEFAULT '0'::bigint,
    isforeignonly bigint DEFAULT '0'::bigint,
    isnonfoilonly bigint DEFAULT '0'::bigint,
    isonlineonly bigint DEFAULT '0'::bigint,
    ispartialpreview bigint DEFAULT '0'::bigint,
    keyrunecode text,
    mcmid bigint,
    mcmidextras bigint,
    mcmname text,
    mtgocode text,
    name text,
    parentcode text,
    releasedate date,
    tcgplayergroupid bigint,
    totalsetsize bigint,
    type text
);

CREATE TABLE public.set_translations (
    id bigint NOT NULL,
    language text,
    setcode text,
    translation text
);

CREATE TABLE public.rulings (
    id bigint NOT NULL,
    date date,
    text text,
    uuid text
);

ALTER TABLE ONLY public.cards
    ADD CONSTRAINT idx_48549_cards_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.foreign_data
    ADD CONSTRAINT idx_48571_foreign_data_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.legalities
    ADD CONSTRAINT idx_48578_legalities_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.sets
    ADD CONSTRAINT idx_48585_sets_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.set_translations
    ADD CONSTRAINT idx_48597_set_translations_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.rulings
    ADD CONSTRAINT idx_48604_rulings_pkey PRIMARY KEY (id);
CREATE UNIQUE INDEX idx_48549_sqlite_autoindex_cards_1 ON public.cards USING btree (uuid);
CREATE UNIQUE INDEX idx_48585_sqlite_autoindex_sets_1 ON public.sets USING btree (code);
ALTER TABLE ONLY public.set_translations
    ADD CONSTRAINT set_translations_setcode_fkey FOREIGN KEY (setcode) REFERENCES public.sets(code) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.rulings
    ADD CONSTRAINT rulings_uuid_fkey FOREIGN KEY (uuid) REFERENCES public.cards(uuid) ON UPDATE CASCADE ON DELETE CASCADE;
