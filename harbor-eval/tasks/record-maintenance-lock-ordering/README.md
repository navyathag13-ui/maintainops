# maintainops/record-maintenance-lock-ordering

record_maintenance locks Part rows in client-supplied order instead of a canonical order, risking Postgres deadlocks under concurrency.
