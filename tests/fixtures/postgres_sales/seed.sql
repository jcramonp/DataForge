-- Test fixture (#24): a small PostgreSQL *source* for config/examples/postgres_sales.yaml.
-- Not DataForge metadata and not demo business data: it only proves that the
-- generic orchestration runs a postgresql-type source end to end.
-- Expected Quality Gate outcome: 5 rows -> 4 validated, 1 quarantined (S4: negative amount).
DROP TABLE IF EXISTS public.sales;

CREATE TABLE public.sales (
    sale_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    tax NUMERIC(12, 2) NOT NULL,
    created_at TIMESTAMP NOT NULL
);

INSERT INTO public.sales (sale_id, customer_id, amount, tax, created_at) VALUES
    ('S1', 'C1', 100.00, 19.00, '2026-10-01 10:00:00'),
    ('S2', 'C2', 250.50, 47.60, '2026-10-02 11:30:00'),
    ('S3', 'C1', 80.00, 15.20, '2026-10-03 09:15:00'),
    ('S4', 'C3', -20.00, 0.00, '2026-10-04 16:45:00'),
    (' S5 ', 'C4', 60.00, 11.40, '2026-10-05 08:05:00');
