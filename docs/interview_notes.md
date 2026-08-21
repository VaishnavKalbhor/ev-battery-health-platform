# Interview Notes

## Project Pitch

AutoLake is a medallion-style EV battery telemetry platform. It starts with raw connected-vehicle events, cleans and normalizes them into trusted silver datasets, then publishes gold data products for battery health, charging intelligence, thermal risk, and warranty analytics.

## Why It Matters for Automotive

EV fleets generate high-volume telemetry that is noisy, late, duplicated, and difficult to trust without strong contracts. Automotive data teams need pipelines that support operational decisions, engineering analytics, warranty monitoring, and compliance-aware reporting.

## Engineering Decisions

- Used a deterministic simulator so reviewers can reproduce the same fleet.
- Kept bronze immutable and preserved rejected records instead of silently dropping bad data.
- Added silver-level derived fields such as charging type and thermal state.
- Separated gold products by business use case rather than building one wide table.
- Added automated quality checks for required columns, duplicates, value ranges, vehicle coverage, and risk-band validity.

## How to Explain Tradeoffs

- The local project uses JSONL and CSV to stay easy to run, but the architecture maps to Kafka, Spark, Delta Lake or Iceberg, and object storage.
- The simulator is not intended to be a physics-perfect battery model. It is designed to generate realistic-enough data engineering patterns: charging sessions, sensor ranges, duplicates, outliers, degradation, and regional aggregation.
- Gold outputs are dashboard-ready and can be served through BI tools or loaded into a low-latency serving database such as ClickHouse or PostgreSQL.

## Resume Bullet

Built an EV battery health and charging intelligence platform using medallion architecture, synthetic fleet telemetry, data quality gates, and analytics-ready gold datasets for SOH monitoring, charging behavior, thermal risk, and warranty scoring.

