from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REQUIRED_SILVER_COLUMNS = {
    "event_id",
    "timestamp",
    "vehicle_id",
    "pack_id",
    "model",
    "region",
    "soc_pct",
    "soh_pct",
    "battery_temp_c",
    "charger_power_kw",
    "energy_delta_kwh",
    "is_charging",
    "event_date",
    "thermal_state",
    "charging_type",
}

VALID_RISK_BANDS = {"low", "medium", "high"}


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    details: str


@dataclass(frozen=True)
class QualityReport:
    checks: tuple[QualityCheck, ...]

    @property
    def passed(self) -> bool:
        return all(check.passed for check in self.checks)

    def to_markdown(self) -> str:
        lines = ["# Data Quality Report", ""]
        for check in self.checks:
            status = "PASS" if check.passed else "FAIL"
            lines.append(f"- **{status}** `{check.name}`: {check.details}")
        lines.append("")
        lines.append(f"Overall status: {'PASS' if self.passed else 'FAIL'}")
        return "\n".join(lines)


def run_quality_checks(
    silver_dir: Path = Path("data/silver"),
    gold_dir: Path = Path("data/gold"),
    report_path: Path | None = Path("reports/data_quality.md"),
) -> QualityReport:
    battery_events_path = silver_dir / "battery_events.csv"
    charging_sessions_path = silver_dir / "charging_sessions.csv"
    health_path = gold_dir / "battery_health_summary.csv"
    charging_path = gold_dir / "charging_intelligence.csv"
    warranty_path = gold_dir / "warranty_risk_scores.csv"

    silver_events = _read_csv(battery_events_path)
    charging_sessions = _read_csv(charging_sessions_path)
    health_rows = _read_csv(health_path)
    charging_rows = _read_csv(charging_path)
    warranty_rows = _read_csv(warranty_path)

    checks = [
        _check_non_empty("silver_battery_events_not_empty", silver_events),
        _check_non_empty("silver_charging_sessions_not_empty", charging_sessions),
        _check_non_empty("gold_battery_health_not_empty", health_rows),
        _check_non_empty("gold_charging_intelligence_not_empty", charging_rows),
        _check_non_empty("gold_warranty_risk_not_empty", warranty_rows),
        _check_silver_columns(silver_events),
        _check_unique_event_ids(silver_events),
        _check_range("soc_pct_range", silver_events, "soc_pct", 0.0, 100.0),
        _check_range("soh_pct_range", silver_events, "soh_pct", 50.0, 105.0),
        _check_range("battery_temp_c_range", silver_events, "battery_temp_c", -40.0, 90.0),
        _check_gold_vehicle_coverage(silver_events, health_rows, warranty_rows),
        _check_warranty_risk_bands(warranty_rows),
    ]
    report = QualityReport(tuple(checks))

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report.to_markdown(), encoding="utf-8")

    return report


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _check_non_empty(name: str, rows: list[dict[str, str]]) -> QualityCheck:
    return QualityCheck(name, bool(rows), f"{len(rows)} rows found")


def _check_silver_columns(rows: list[dict[str, str]]) -> QualityCheck:
    if not rows:
        return QualityCheck("silver_required_columns", False, "silver table is empty")
    columns = set(rows[0].keys())
    missing = sorted(REQUIRED_SILVER_COLUMNS - columns)
    return QualityCheck(
        "silver_required_columns",
        not missing,
        "all required columns present" if not missing else f"missing columns: {', '.join(missing)}",
    )


def _check_unique_event_ids(rows: list[dict[str, str]]) -> QualityCheck:
    event_ids = [row.get("event_id", "") for row in rows]
    duplicates = len(event_ids) - len(set(event_ids))
    return QualityCheck(
        "silver_unique_event_ids",
        duplicates == 0,
        "no duplicate event IDs" if duplicates == 0 else f"{duplicates} duplicate event IDs",
    )


def _check_range(name: str, rows: list[dict[str, str]], field: str, minimum: float, maximum: float) -> QualityCheck:
    failures = 0
    for row in rows:
        try:
            value = float(row[field])
        except (KeyError, TypeError, ValueError):
            failures += 1
            continue
        if value < minimum or value > maximum:
            failures += 1
    return QualityCheck(
        name,
        failures == 0,
        f"all {field} values within [{minimum}, {maximum}]" if failures == 0 else f"{failures} invalid values",
    )


def _check_gold_vehicle_coverage(
    silver_events: list[dict[str, str]],
    health_rows: list[dict[str, str]],
    warranty_rows: list[dict[str, str]],
) -> QualityCheck:
    silver_vehicles = {row["vehicle_id"] for row in silver_events}
    health_vehicles = {row["vehicle_id"] for row in health_rows}
    warranty_vehicles = {row["vehicle_id"] for row in warranty_rows}
    missing_health = silver_vehicles - health_vehicles
    missing_warranty = silver_vehicles - warranty_vehicles
    passed = not missing_health and not missing_warranty
    detail = "all silver vehicles covered by health and warranty gold outputs"
    if not passed:
        detail = f"missing health={len(missing_health)}, missing warranty={len(missing_warranty)}"
    return QualityCheck("gold_vehicle_coverage", passed, detail)


def _check_warranty_risk_bands(rows: list[dict[str, str]]) -> QualityCheck:
    invalid = [row.get("risk_band", "") for row in rows if row.get("risk_band", "") not in VALID_RISK_BANDS]
    return QualityCheck(
        "warranty_risk_bands",
        not invalid,
        "risk bands are valid" if not invalid else f"{len(invalid)} invalid risk bands",
    )

