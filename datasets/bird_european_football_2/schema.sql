-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database european_football_2.
-- Written by database/import_bird.py.

CREATE TABLE public.player_attributes (
    id bigint NOT NULL,
    player_fifa_api_id bigint,
    player_api_id bigint,
    date text,
    overall_rating bigint,
    potential bigint,
    preferred_foot text,
    attacking_work_rate text,
    defensive_work_rate text,
    crossing bigint,
    finishing bigint,
    heading_accuracy bigint,
    short_passing bigint,
    volleys bigint,
    dribbling bigint,
    curve bigint,
    free_kick_accuracy bigint,
    long_passing bigint,
    ball_control bigint,
    acceleration bigint,
    sprint_speed bigint,
    agility bigint,
    reactions bigint,
    balance bigint,
    shot_power bigint,
    jumping bigint,
    stamina bigint,
    strength bigint,
    long_shots bigint,
    aggression bigint,
    interceptions bigint,
    positioning bigint,
    vision bigint,
    penalties bigint,
    marking bigint,
    standing_tackle bigint,
    sliding_tackle bigint,
    gk_diving bigint,
    gk_handling bigint,
    gk_kicking bigint,
    gk_positioning bigint,
    gk_reflexes bigint
);

CREATE TABLE public.player (
    id bigint NOT NULL,
    player_api_id bigint,
    player_name text,
    player_fifa_api_id bigint,
    birthday text,
    height bigint,
    weight bigint
);

CREATE TABLE public.league (
    id bigint NOT NULL,
    country_id bigint,
    name text
);

CREATE TABLE public.country (
    id bigint NOT NULL,
    name text
);

CREATE TABLE public.team (
    id bigint NOT NULL,
    team_api_id bigint,
    team_fifa_api_id bigint,
    team_long_name text,
    team_short_name text
);

CREATE TABLE public.team_attributes (
    id bigint NOT NULL,
    team_fifa_api_id bigint,
    team_api_id bigint,
    date text,
    buildupplayspeed bigint,
    buildupplayspeedclass text,
    buildupplaydribbling bigint,
    buildupplaydribblingclass text,
    buildupplaypassing bigint,
    buildupplaypassingclass text,
    buildupplaypositioningclass text,
    chancecreationpassing bigint,
    chancecreationpassingclass text,
    chancecreationcrossing bigint,
    chancecreationcrossingclass text,
    chancecreationshooting bigint,
    chancecreationshootingclass text,
    chancecreationpositioningclass text,
    defencepressure bigint,
    defencepressureclass text,
    defenceaggression bigint,
    defenceaggressionclass text,
    defenceteamwidth bigint,
    defenceteamwidthclass text,
    defencedefenderlineclass text
);

CREATE TABLE public.match (
    id bigint NOT NULL,
    country_id bigint,
    league_id bigint,
    season text,
    stage bigint,
    date text,
    match_api_id bigint,
    home_team_api_id bigint,
    away_team_api_id bigint,
    home_team_goal bigint,
    away_team_goal bigint,
    home_player_x1 bigint,
    home_player_x2 bigint,
    home_player_x3 bigint,
    home_player_x4 bigint,
    home_player_x5 bigint,
    home_player_x6 bigint,
    home_player_x7 bigint,
    home_player_x8 bigint,
    home_player_x9 bigint,
    home_player_x10 bigint,
    home_player_x11 bigint,
    away_player_x1 bigint,
    away_player_x2 bigint,
    away_player_x3 bigint,
    away_player_x4 bigint,
    away_player_x5 bigint,
    away_player_x6 bigint,
    away_player_x7 bigint,
    away_player_x8 bigint,
    away_player_x9 bigint,
    away_player_x10 bigint,
    away_player_x11 bigint,
    home_player_y1 bigint,
    home_player_y2 bigint,
    home_player_y3 bigint,
    home_player_y4 bigint,
    home_player_y5 bigint,
    home_player_y6 bigint,
    home_player_y7 bigint,
    home_player_y8 bigint,
    home_player_y9 bigint,
    home_player_y10 bigint,
    home_player_y11 bigint,
    away_player_y1 bigint,
    away_player_y2 bigint,
    away_player_y3 bigint,
    away_player_y4 bigint,
    away_player_y5 bigint,
    away_player_y6 bigint,
    away_player_y7 bigint,
    away_player_y8 bigint,
    away_player_y9 bigint,
    away_player_y10 bigint,
    away_player_y11 bigint,
    home_player_1 bigint,
    home_player_2 bigint,
    home_player_3 bigint,
    home_player_4 bigint,
    home_player_5 bigint,
    home_player_6 bigint,
    home_player_7 bigint,
    home_player_8 bigint,
    home_player_9 bigint,
    home_player_10 bigint,
    home_player_11 bigint,
    away_player_1 bigint,
    away_player_2 bigint,
    away_player_3 bigint,
    away_player_4 bigint,
    away_player_5 bigint,
    away_player_6 bigint,
    away_player_7 bigint,
    away_player_8 bigint,
    away_player_9 bigint,
    away_player_10 bigint,
    away_player_11 bigint,
    goal text,
    shoton text,
    shotoff text,
    foulcommit text,
    card text,
    "cross" text,
    corner text,
    possession text,
    b365h real,
    b365d real,
    b365a real,
    bwh real,
    bwd real,
    bwa real,
    iwh real,
    iwd real,
    iwa real,
    lbh real,
    lbd real,
    lba real,
    psh real,
    psd real,
    psa real,
    whh real,
    whd real,
    wha real,
    sjh real,
    sjd real,
    sja real,
    vch real,
    vcd real,
    vca real,
    gbh real,
    gbd real,
    gba real,
    bsh real,
    bsd real,
    bsa real
);

ALTER TABLE ONLY public.player_attributes
    ADD CONSTRAINT idx_143121_player_attributes_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.player
    ADD CONSTRAINT idx_143128_player_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.league
    ADD CONSTRAINT idx_143135_league_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.country
    ADD CONSTRAINT idx_143142_country_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.team
    ADD CONSTRAINT idx_143149_team_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.team_attributes
    ADD CONSTRAINT idx_143156_team_attributes_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT idx_143163_match_pkey PRIMARY KEY (id);
CREATE UNIQUE INDEX idx_143128_sqlite_autoindex_player_1 ON public.player USING btree (player_api_id);
CREATE UNIQUE INDEX idx_143128_sqlite_autoindex_player_2 ON public.player USING btree (player_fifa_api_id);
CREATE UNIQUE INDEX idx_143135_sqlite_autoindex_league_1 ON public.league USING btree (name);
CREATE UNIQUE INDEX idx_143142_sqlite_autoindex_country_1 ON public.country USING btree (name);
CREATE UNIQUE INDEX idx_143149_sqlite_autoindex_team_1 ON public.team USING btree (team_api_id);
CREATE UNIQUE INDEX idx_143163_sqlite_autoindex_match_1 ON public.match USING btree (match_api_id);
ALTER TABLE ONLY public.player_attributes
    ADD CONSTRAINT player_attributes_player_api_id_fkey FOREIGN KEY (player_api_id) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.team_attributes
    ADD CONSTRAINT team_attributes_team_api_id_fkey FOREIGN KEY (team_api_id) REFERENCES public.team(team_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_10_fkey FOREIGN KEY (away_player_10) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_11_fkey FOREIGN KEY (away_player_11) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_1_fkey FOREIGN KEY (away_player_1) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_2_fkey FOREIGN KEY (away_player_2) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_3_fkey FOREIGN KEY (away_player_3) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_4_fkey FOREIGN KEY (away_player_4) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_5_fkey FOREIGN KEY (away_player_5) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_6_fkey FOREIGN KEY (away_player_6) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_7_fkey FOREIGN KEY (away_player_7) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_8_fkey FOREIGN KEY (away_player_8) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_player_9_fkey FOREIGN KEY (away_player_9) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_away_team_api_id_fkey FOREIGN KEY (away_team_api_id) REFERENCES public.team(team_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_10_fkey FOREIGN KEY (home_player_10) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_11_fkey FOREIGN KEY (home_player_11) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_1_fkey FOREIGN KEY (home_player_1) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_2_fkey FOREIGN KEY (home_player_2) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_3_fkey FOREIGN KEY (home_player_3) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_4_fkey FOREIGN KEY (home_player_4) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_5_fkey FOREIGN KEY (home_player_5) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_6_fkey FOREIGN KEY (home_player_6) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_7_fkey FOREIGN KEY (home_player_7) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_8_fkey FOREIGN KEY (home_player_8) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_player_9_fkey FOREIGN KEY (home_player_9) REFERENCES public.player(player_api_id);
ALTER TABLE ONLY public.match
    ADD CONSTRAINT match_home_team_api_id_fkey FOREIGN KEY (home_team_api_id) REFERENCES public.team(team_api_id);
