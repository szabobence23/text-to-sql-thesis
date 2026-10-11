-- Runs the PostgreSQL port's install.sql (pinned commit, see SOURCES.md)
-- unchanged. Its \copy commands read './<Table>.csv' relative to psql's
-- working directory, so psql first moves to the CSVs that
-- prepare_data.py converted.
--
-- Prerequisite: python datasets/adventureworks/prepare_data.py

\cd /datasets/adventureworks/data/converted
\i /datasets/adventureworks/data/postgres-port/install.sql
