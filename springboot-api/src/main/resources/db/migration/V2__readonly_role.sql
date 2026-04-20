-- V2: dedicated read-only Postgres role for the Analytics MCP.
-- Password comes from the MCP_READONLY_PASSWORD env var via Flyway placeholders
-- (see application.yml -> spring.flyway.placeholders.mcp_readonly_password).
--
-- Guardrail intent: even if the MCP application code has a bug, the DB itself
-- rejects writes / DDL for this role. See PRD §7.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'mcp_readonly') THEN
        EXECUTE format(
            'CREATE ROLE mcp_readonly LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
            '${mcp_readonly_password}'
        );
    ELSE
        EXECUTE format(
            'ALTER ROLE mcp_readonly WITH LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT',
            '${mcp_readonly_password}'
        );
    END IF;
END
$$;

-- Session-level safety: force read-only transactions + short timeouts for this role.
ALTER ROLE mcp_readonly SET default_transaction_read_only = on;
ALTER ROLE mcp_readonly SET statement_timeout = '5s';
ALTER ROLE mcp_readonly SET idle_in_transaction_session_timeout = '10s';

-- Connect to the database and see the public schema.
GRANT CONNECT ON DATABASE appdb   TO mcp_readonly;
GRANT USAGE    ON SCHEMA   public TO mcp_readonly;

-- SELECT only on allowlisted views. Do NOT grant on raw tables.
GRANT SELECT ON v_employees_safe TO mcp_readonly;
GRANT SELECT ON v_orders_safe    TO mcp_readonly;

-- Explicit revoke on raw tables (belt-and-suspenders: if a future grant ever
-- adds them to PUBLIC, we still don't want mcp_readonly reading them).
REVOKE ALL ON employees FROM mcp_readonly;
REVOKE ALL ON orders    FROM mcp_readonly;
