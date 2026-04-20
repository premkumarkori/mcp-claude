-- V1: core schema + PII-masked views for the Analytics MCP.
-- The Analytics MCP should only be granted SELECT on the v_*_safe views,
-- never the raw tables. See V2__readonly_role.sql.

CREATE TABLE employees (
    id         BIGSERIAL PRIMARY KEY,
    name       TEXT        NOT NULL,
    email      TEXT        NOT NULL UNIQUE,
    joined_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_employees_joined_at ON employees (joined_at);

CREATE TABLE orders (
    id             BIGSERIAL PRIMARY KEY,
    customer_name  TEXT           NOT NULL,
    amount         NUMERIC(12, 2) NOT NULL CHECK (amount >= 0),
    status         TEXT           NOT NULL CHECK (status IN ('PENDING', 'SHIPPED', 'CANCELLED')),
    created_at     TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_status     ON orders (status);
CREATE INDEX idx_orders_created_at ON orders (created_at);

-- PII-masked view: email is partially masked so downstream consumers
-- (Analytics MCP) cannot reconstruct it.
CREATE OR REPLACE VIEW v_employees_safe AS
SELECT
    id,
    name,
    SUBSTRING(email FROM 1 FOR 2) || '***@' || SPLIT_PART(email, '@', 2) AS email_masked,
    joined_at
FROM employees;

-- Orders view: no PII today; kept as a view for consistency so the allowlist
-- is always "views only", never raw tables.
CREATE OR REPLACE VIEW v_orders_safe AS
SELECT
    id,
    customer_name,
    amount,
    status,
    created_at
FROM orders;
