-- ============================================================
-- READ-ONLY ROLE FOR LLM-GENERATED SQL
-- ============================================================
-- The application connects with this role, never as postgres.
-- The SQL validators are the first line of defence; this role
-- is the one that actually guarantees generated SQL cannot
-- modify data, read server files or run forever.
--
-- One role for the whole server, granted per dataset database.
-- Run as superuser against the dataset database, after its schema
-- (setup_dataset.py does this):
--   psql -U postgres -d <db> -v db_name=<db> -f readonly_role.sql
-- Local development password; override in production setups.

DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'text2sql_reader') THEN
        CREATE ROLE text2sql_reader LOGIN PASSWORD 'text2sql_reader';
    END IF;
END
$$;

-- Only read access to the data tables.
REVOKE ALL ON DATABASE :"db_name" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"db_name" TO text2sql_reader;

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO text2sql_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO text2sql_reader;

-- Server-side large object import/export (lo_import('/etc/passwd')).
REVOKE EXECUTE ON FUNCTION lo_import(text) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lo_import(text, oid) FROM PUBLIC;
REVOKE EXECUTE ON FUNCTION lo_export(oid, text) FROM PUBLIC;

-- Session defaults. The client can still SET these, so the
-- application additionally rolls back every query transaction.
ALTER ROLE text2sql_reader SET default_transaction_read_only = on;
ALTER ROLE text2sql_reader SET statement_timeout = '10s';
