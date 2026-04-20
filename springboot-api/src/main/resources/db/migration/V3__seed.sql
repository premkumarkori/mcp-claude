-- V3: realistic seed data so the Analytics MCP has something meaningful to query.
-- 60 employees spread across the last 90 days.
-- 240 orders across all three statuses over the last 60 days.

INSERT INTO employees (name, email, joined_at)
SELECT
    'Employee ' || i,
    'employee' || i || '@example.com',
    NOW() - (random() * INTERVAL '90 days')
FROM generate_series(1, 60) AS s(i);

INSERT INTO orders (customer_name, amount, status, created_at)
SELECT
    'Customer ' || (1 + (i % 40)),
    ROUND((10 + random() * 990)::numeric, 2),
    (ARRAY['PENDING', 'SHIPPED', 'SHIPPED', 'SHIPPED', 'CANCELLED'])[1 + (i % 5)],
    NOW() - (random() * INTERVAL '60 days')
FROM generate_series(1, 240) AS s(i);
