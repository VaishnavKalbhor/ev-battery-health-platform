# Architecture

The platform follows a medallion architecture:

1. **Bronze** stores immutable raw telemetry events exactly as they arrived.
2. **Silver** applies schema normalization, deduplication, type conversion, and domain validation.
3. **Gold** produces business-facing datasets for battery health, charging performance, thermal behavior, and warranty risk.

The current local implementation writes JSONL and CSV files so the project can be run on any laptop. The same boundaries map naturally to Kafka, object storage, Spark, Delta Lake or Iceberg, dbt, and BI tooling in a production setup.

