-- BIRD Mini-Dev (bird-bench.github.io, CC BY-SA 4.0), PostgreSQL version (minidev.zip, MINIDEV_postgresql/BIRD_dev.sql), database codebase_community.
-- Written by database/import_bird.py.

CREATE TABLE public.badges (
    id bigint NOT NULL,
    userid bigint,
    name text,
    date timestamp with time zone
);

CREATE TABLE public.comments (
    id bigint NOT NULL,
    postid bigint,
    score bigint,
    text text,
    creationdate timestamp with time zone,
    userid bigint,
    userdisplayname text
);

CREATE TABLE public.posthistory (
    id bigint NOT NULL,
    posthistorytypeid bigint,
    postid bigint,
    revisionguid text,
    creationdate timestamp with time zone,
    userid bigint,
    text text,
    comment text,
    userdisplayname text
);

CREATE TABLE public.postlinks (
    id bigint NOT NULL,
    creationdate timestamp with time zone,
    postid bigint,
    relatedpostid bigint,
    linktypeid bigint
);

CREATE TABLE public.posts (
    id bigint NOT NULL,
    posttypeid bigint,
    acceptedanswerid bigint,
    creaiondate timestamp with time zone,
    score bigint,
    viewcount bigint,
    body text,
    owneruserid bigint,
    lasactivitydate timestamp with time zone,
    title text,
    tags text,
    answercount bigint,
    commentcount bigint,
    favoritecount bigint,
    lasteditoruserid bigint,
    lasteditdate timestamp with time zone,
    communityowneddate timestamp with time zone,
    parentid bigint,
    closeddate timestamp with time zone,
    ownerdisplayname text,
    lasteditordisplayname text
);

CREATE TABLE public.tags (
    id bigint NOT NULL,
    tagname text,
    count bigint,
    excerptpostid bigint,
    wikipostid bigint
);

CREATE TABLE public.users (
    id bigint NOT NULL,
    reputation bigint,
    creationdate timestamp with time zone,
    displayname text,
    lastaccessdate timestamp with time zone,
    websiteurl text,
    location text,
    aboutme text,
    views bigint,
    upvotes bigint,
    downvotes bigint,
    accountid bigint,
    age bigint,
    profileimageurl text
);

CREATE TABLE public.votes (
    id bigint NOT NULL,
    postid bigint,
    votetypeid bigint,
    creationdate date,
    userid bigint,
    bountyamount bigint
);

ALTER TABLE ONLY public.badges
    ADD CONSTRAINT idx_86323_badges_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.comments
    ADD CONSTRAINT idx_86328_comments_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.posthistory
    ADD CONSTRAINT idx_86333_posthistory_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.postlinks
    ADD CONSTRAINT idx_86338_postlinks_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.posts
    ADD CONSTRAINT idx_86341_posts_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.tags
    ADD CONSTRAINT idx_86346_tags_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.users
    ADD CONSTRAINT idx_86351_users_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.votes
    ADD CONSTRAINT idx_86356_votes_pkey PRIMARY KEY (id);
CREATE UNIQUE INDEX idx_86333_sqlite_autoindex_posthistory_1 ON public.posthistory USING btree (id);
CREATE UNIQUE INDEX idx_86341_sqlite_autoindex_posts_1 ON public.posts USING btree (id);
CREATE UNIQUE INDEX idx_86351_sqlite_autoindex_users_1 ON public.users USING btree (id);
ALTER TABLE ONLY public.badges
    ADD CONSTRAINT badges_userid_fkey FOREIGN KEY (userid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.comments
    ADD CONSTRAINT comments_userid_fkey FOREIGN KEY (userid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.posthistory
    ADD CONSTRAINT posthistory_userid_fkey FOREIGN KEY (userid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_lasteditoruserid_fkey FOREIGN KEY (lasteditoruserid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.posts
    ADD CONSTRAINT posts_owneruserid_fkey FOREIGN KEY (owneruserid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_postid_fkey FOREIGN KEY (postid) REFERENCES public.posts(id) ON UPDATE CASCADE ON DELETE CASCADE;
ALTER TABLE ONLY public.votes
    ADD CONSTRAINT votes_userid_fkey FOREIGN KEY (userid) REFERENCES public.users(id) ON UPDATE CASCADE ON DELETE CASCADE;
