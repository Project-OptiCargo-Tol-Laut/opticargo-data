# PRD traceability — opticargo-data v3.0.0

This repository extension implements only the missing data-runtime layer while preserving the existing curated JSON/PDF datasets.

| PRD expectation | Implementation |
|---|---|
| `opticargo-data` = dataset + importers/validators/seed scripts/synthetic training data | Python package `opticargo_data`, validator, Docker one-off image, deterministic operational datasets |
| Data job is local/CI/one-off, not permanent public service | Docker image has no HTTP server; infra executes `python -m opticargo_data.seed` |
| Seed must be reproducible and idempotent | UUID5 IDs, fixed competition timestamps, `--idempotent` PK upserts, duplicate-ID tests |
| Competition demo data | Existing 70 ports/445 routes/19 commodities/15 ships/50 suppliers retained; added role users, 30 voyages/capacities, 80 listings, 500 synthetic bookings |
| Synthetic/real segregation | Synthetic rows expose `is_synthetic=true` and provenance where schema supports those columns; curated ports/routes remain marked non-synthetic |
| Regulations | Existing 9 PDFs + metadata validated; optional `--upload-regulations` stages PDFs in MinIO. Indexing itself remains RAG worker responsibility. |
| PostgreSQL source of truth / Gateway owns business transactions | Seeder populates deterministic baseline/history only. It does **not** fake refresh sessions, idempotency records, outbox, audit logs, payment webhooks, notifications, reports, or recommendations. Those are produced by Gateway/workers during E2E flows. |
| Strong password hashing | Demo-user hashes generated at seed time using Argon2 by default; bcrypt is selectable with `OPTICARGO_PASSWORD_SCHEME=bcrypt`. No password hash is committed in dataset files. |
| Shared validation dependency | Intrinsic contract/FK validation is included. Exact `opticargo-shared` model validation cannot be guaranteed without the shared wheel/source; integrate it in CI when that package is available. |
| Gateway schema authority | Seeder reflects live PostgreSQL columns and fails with `SCHEMA_MISMATCH` for uncovered required columns rather than silently inventing data. Use `--schema-only` to inspect compatibility. |

## Intentionally not seeded

The following tables are lifecycle/runtime artifacts and should be created by application flows: `refresh_sessions`, `idempotency_records`, `outbox_events`, `audit_logs`, `payment_webhook_events`, `notifications`, `report_jobs`, and AI recommendation state. This keeps the demo path aligned with the PRD requirement that critical E2E flows work without manual DB edits or hardcoded final responses.

## v3.1.0 shared-contract alignment

- Pins `opticargo-shared==1.0.0` using the official wheel in `vendor/`.
- Validates all seeded public domain records with shared Create models before DB writes.
- Validates synthetic provenance through `RecordProvenance` and dataset-level metadata
  through `DatasetManifest`.
- Keeps Gateway persistence-only fields separate from the public shared contracts.
