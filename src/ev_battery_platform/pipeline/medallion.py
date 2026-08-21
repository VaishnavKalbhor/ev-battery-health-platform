from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Iterable


MODEL_CAPACITY_KWH = {
    "compact_ev": 58.0,
    "premium_sedan_ev": 89.0,
    "suv_ev": 104.0,
    "delivery_van_ev": 78.0,
}

SILVER_FIELDS = [
    "event_id",
    "timestamp",
    "vehicle_id",
    "pack_id",
    "model",
    "region",
    "firmware_version",
    "odometer_km",
    "latitude",
    "longitude",
    "speed_kmh",
    "soc_pct",
    "soh_pct",
    "battery_temp_c",
    "ambient_temp_c",
    "voltage_v",
    "current_a",
    "charger_power_kw",
    "energy_delta_kwh",
    "is_charging",
    "event_date",
    "usable_battery_kwh",
    "thermal_state",
    "charging_type",
]


@dataclass(frozen=True)
class PipelineResult:
    raw_events: int
    silver_events: int
    rejected_events: int
    charging_sessions: int
    gold_outputs: tuple[Path, ...]


def run_pipeline(
    bronze_path: Path = Path("data/bronze/ev_telemetry_raw.jsonl"),
    silver_dir: Path = Path("data/silver"),
    gold_dir: Path = Path("data/gold"),
) -> PipelineResult:
    silver_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)

    raw_events = 0
    accepted: list[dict[str, object]] = []
    rejected: list[dict[str, object]] = []
    seen_event_ids: set[str] = set()

    for payload in _read_jsonl(bronze_path):
        raw_events += 1
        normalized, errors = _normalize_event(payload)
        if normalized is None:
            rejected.append(_rejection(payload, errors))
            continue
        event_id = str(normalized["event_id"])
        if event_id in seen_event_ids:
            rejected.append(_rejection(payload, ["duplicate_event_id"]))
            continue
        seen_event_ids.add(event_id)
        accepted.append(normalized)

    accepted.sort(key=lambda row: (str(row["vehicle_id"]), str(row["timestamp"])))

    silver_events_path = silver_dir / "battery_events.csv"
    rejected_path = silver_dir / "rejected_events.csv"
    sessions_path = silver_dir / "charging_sessions.csv"
    _write_csv(silver_events_path, accepted, SILVER_FIELDS)
    _write_csv(rejected_path, rejected, ["event_id", "vehicle_id", "timestamp", "errors", "raw_payload"])

    sessions = _build_charging_sessions(accepted)
    _write_csv(
        sessions_path,
        sessions,
        [
            "session_id",
            "vehicle_id",
            "pack_id",
            "region",
            "start_ts",
            "end_ts",
            "start_soc_pct",
            "end_soc_pct",
            "soc_gain_pct",
            "energy_added_kwh",
            "avg_power_kw",
            "max_power_kw",
            "charging_type",
            "duration_minutes",
        ],
    )

    gold_outputs = (
        _write_battery_health(accepted, sessions, gold_dir / "battery_health_summary.csv"),
        _write_charging_intelligence(sessions, gold_dir / "charging_intelligence.csv"),
        _write_thermal_risk(accepted, gold_dir / "thermal_risk_events.csv"),
        _write_warranty_risk(accepted, sessions, gold_dir / "warranty_risk_scores.csv"),
    )

    return PipelineResult(
        raw_events=raw_events,
        silver_events=len(accepted),
        rejected_events=len(rejected),
        charging_sessions=len(sessions),
        gold_outputs=gold_outputs,
    )


def _read_jsonl(path: Path) -> Iterable[dict[str, object]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _normalize_event(payload: dict[str, object]) -> tuple[dict[str, object] | None, list[str]]:
    errors: list[str] = []
    required = [
        "event_id",
        "timestamp",
        "vehicle_id",
        "pack_id",
        "model",
        "region",
        "odometer_km",
        "soc_pct",
        "soh_pct",
        "battery_temp_c",
        "charger_power_kw",
        "energy_delta_kwh",
        "is_charging",
    ]
    for field in required:
        if field not in payload or payload[field] in (None, ""):
            errors.append(f"missing_{field}")

    try:
        timestamp = datetime.fromisoformat(str(payload.get("timestamp")))
    except ValueError:
        errors.append("invalid_timestamp")
        timestamp = None

    model = str(payload.get("model", ""))
    if model not in MODEL_CAPACITY_KWH:
        errors.append("unknown_model")

    numeric_ranges = {
        "odometer_km": (0, 500_000),
        "latitude": (47, 55.5),
        "longitude": (5, 16),
        "speed_kmh": (0, 260),
        "soc_pct": (0, 100),
        "soh_pct": (50, 105),
        "battery_temp_c": (-40, 90),
        "ambient_temp_c": (-35, 55),
        "voltage_v": (250, 900),
        "current_a": (-900, 900),
        "charger_power_kw": (0, 350),
        "energy_delta_kwh": (-80, 80),
    }

    parsed: dict[str, object] = {}
    for field, (minimum, maximum) in numeric_ranges.items():
        try:
            value = float(payload.get(field))
        except (TypeError, ValueError):
            errors.append(f"invalid_{field}")
            continue
        if value < minimum or value > maximum:
            errors.append(f"out_of_range_{field}")
        parsed[field] = round(value, 6)

    if errors:
        return None, errors

    battery_temp_c = float(parsed["battery_temp_c"])
    charger_power_kw = float(parsed["charger_power_kw"])
    is_charging = bool(payload.get("is_charging"))

    normalized = {
        "event_id": str(payload["event_id"]),
        "timestamp": timestamp.isoformat(),
        "vehicle_id": str(payload["vehicle_id"]),
        "pack_id": str(payload["pack_id"]),
        "model": model,
        "region": str(payload.get("region", "unknown")),
        "firmware_version": str(payload.get("firmware_version", "unknown")),
        **parsed,
        "is_charging": is_charging,
        "event_date": timestamp.date().isoformat(),
        "usable_battery_kwh": MODEL_CAPACITY_KWH[model],
        "thermal_state": _thermal_state(battery_temp_c),
        "charging_type": _charging_type(charger_power_kw, is_charging),
    }
    return normalized, []


def _thermal_state(temp_c: float) -> str:
    if temp_c >= 55:
        return "critical"
    if temp_c >= 45:
        return "elevated"
    if temp_c <= -10:
        return "cold_stress"
    return "normal"


def _charging_type(charger_power_kw: float, is_charging: bool) -> str:
    if not is_charging or charger_power_kw <= 0:
        return "not_charging"
    if charger_power_kw >= 100:
        return "dc_fast"
    if charger_power_kw >= 40:
        return "dc_standard"
    return "ac"


def _rejection(payload: dict[str, object], errors: list[str]) -> dict[str, object]:
    return {
        "event_id": payload.get("event_id", ""),
        "vehicle_id": payload.get("vehicle_id", ""),
        "timestamp": payload.get("timestamp", ""),
        "errors": "|".join(errors),
        "raw_payload": json.dumps(payload, sort_keys=True),
    }


def _build_charging_sessions(events: list[dict[str, object]]) -> list[dict[str, object]]:
    sessions: list[dict[str, object]] = []
    by_vehicle: dict[str, list[dict[str, object]]] = defaultdict(list)
    for event in events:
        by_vehicle[str(event["vehicle_id"])].append(event)

    for vehicle_id, rows in by_vehicle.items():
        active: list[dict[str, object]] = []
        session_number = 1
        for event in rows:
            if bool(event["is_charging"]):
                active.append(event)
                continue
            if active:
                sessions.append(_summarize_session(vehicle_id, session_number, active))
                session_number += 1
                active = []
        if active:
            sessions.append(_summarize_session(vehicle_id, session_number, active))

    return sessions


def _summarize_session(vehicle_id: str, session_number: int, rows: list[dict[str, object]]) -> dict[str, object]:
    start = rows[0]
    end = rows[-1]
    powers = [float(row["charger_power_kw"]) for row in rows]
    energy_added = sum(max(0.0, float(row["energy_delta_kwh"])) for row in rows)
    start_ts = datetime.fromisoformat(str(start["timestamp"]))
    end_ts = datetime.fromisoformat(str(end["timestamp"]))
    duration_minutes = max(20.0, (end_ts - start_ts).total_seconds() / 60 + 20)
    return {
        "session_id": f"{vehicle_id}-CHG-{session_number:04d}",
        "vehicle_id": vehicle_id,
        "pack_id": start["pack_id"],
        "region": start["region"],
        "start_ts": start["timestamp"],
        "end_ts": end["timestamp"],
        "start_soc_pct": round(float(start["soc_pct"]), 2),
        "end_soc_pct": round(float(end["soc_pct"]), 2),
        "soc_gain_pct": round(float(end["soc_pct"]) - float(start["soc_pct"]), 2),
        "energy_added_kwh": round(energy_added, 4),
        "avg_power_kw": round(mean(powers), 2),
        "max_power_kw": round(max(powers), 2),
        "charging_type": _dominant_charging_type(rows),
        "duration_minutes": round(duration_minutes, 1),
    }


def _dominant_charging_type(rows: list[dict[str, object]]) -> str:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["charging_type"])] += 1
    return max(counts.items(), key=lambda item: item[1])[0]


def _write_battery_health(events: list[dict[str, object]], sessions: list[dict[str, object]], path: Path) -> Path:
    session_count = _count_by_vehicle(sessions)
    rows = []
    for vehicle_id, vehicle_events in _events_by_vehicle(events).items():
        first = vehicle_events[0]
        soh_values = [float(row["soh_pct"]) for row in vehicle_events]
        discharge_kwh = sum(abs(min(0.0, float(row["energy_delta_kwh"]))) for row in vehicle_events)
        capacity = float(first["usable_battery_kwh"])
        rows.append(
            {
                "vehicle_id": vehicle_id,
                "pack_id": first["pack_id"],
                "model": first["model"],
                "region": first["region"],
                "events": len(vehicle_events),
                "latest_odometer_km": round(float(vehicle_events[-1]["odometer_km"]), 2),
                "usable_battery_kwh": round(capacity, 1),
                "start_soh_pct": round(soh_values[0], 3),
                "latest_soh_pct": round(soh_values[-1], 3),
                "observed_soh_drop_pct": round(soh_values[0] - soh_values[-1], 4),
                "min_soh_pct": round(min(soh_values), 3),
                "equivalent_full_cycles": round(discharge_kwh / capacity, 3),
                "charging_sessions": session_count.get(vehicle_id, 0),
            }
        )
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    return path


def _write_charging_intelligence(sessions: list[dict[str, object]], path: Path) -> Path:
    by_region: dict[str, list[dict[str, object]]] = defaultdict(list)
    for session in sessions:
        by_region[str(session["region"])].append(session)

    rows = []
    for region, region_sessions in sorted(by_region.items()):
        fast_sessions = [row for row in region_sessions if row["charging_type"] == "dc_fast"]
        rows.append(
            {
                "region": region,
                "charging_sessions": len(region_sessions),
                "total_energy_added_kwh": round(sum(float(row["energy_added_kwh"]) for row in region_sessions), 3),
                "avg_session_energy_kwh": round(mean(float(row["energy_added_kwh"]) for row in region_sessions), 3),
                "avg_power_kw": round(mean(float(row["avg_power_kw"]) for row in region_sessions), 2),
                "dc_fast_session_share_pct": round(len(fast_sessions) / len(region_sessions) * 100, 2),
                "avg_soc_gain_pct": round(mean(float(row["soc_gain_pct"]) for row in region_sessions), 2),
            }
        )
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    return path


def _write_thermal_risk(events: list[dict[str, object]], path: Path) -> Path:
    rows = []
    for event in events:
        temp = float(event["battery_temp_c"])
        if event["thermal_state"] in {"elevated", "critical"}:
            rows.append(
                {
                    "event_id": event["event_id"],
                    "timestamp": event["timestamp"],
                    "vehicle_id": event["vehicle_id"],
                    "pack_id": event["pack_id"],
                    "region": event["region"],
                    "battery_temp_c": round(temp, 2),
                    "charger_power_kw": event["charger_power_kw"],
                    "thermal_state": event["thermal_state"],
                    "risk_reason": "high_temp_during_charge" if bool(event["is_charging"]) else "high_temp_while_driving",
                }
            )
    _write_csv(path, rows, list(rows[0].keys()) if rows else ["event_id"])
    return path


def _write_warranty_risk(events: list[dict[str, object]], sessions: list[dict[str, object]], path: Path) -> Path:
    by_vehicle = _events_by_vehicle(events)
    sessions_by_vehicle: dict[str, list[dict[str, object]]] = defaultdict(list)
    for session in sessions:
        sessions_by_vehicle[str(session["vehicle_id"])].append(session)

    rows = []
    for vehicle_id, vehicle_events in by_vehicle.items():
        vehicle_sessions = sessions_by_vehicle.get(vehicle_id, [])
        fast_share = (
            sum(1 for session in vehicle_sessions if session["charging_type"] == "dc_fast") / len(vehicle_sessions)
            if vehicle_sessions
            else 0.0
        )
        soh_drop = float(vehicle_events[0]["soh_pct"]) - float(vehicle_events[-1]["soh_pct"])
        hot_event_share = sum(1 for event in vehicle_events if event["thermal_state"] in {"elevated", "critical"}) / len(vehicle_events)
        odometer = float(vehicle_events[-1]["odometer_km"])
        score = min(100.0, soh_drop * 80 + fast_share * 25 + hot_event_share * 35 + max(0, odometer - 80_000) / 2_000)
        rows.append(
            {
                "vehicle_id": vehicle_id,
                "pack_id": vehicle_events[-1]["pack_id"],
                "latest_soh_pct": round(float(vehicle_events[-1]["soh_pct"]), 3),
                "observed_soh_drop_pct": round(soh_drop, 4),
                "dc_fast_session_share_pct": round(fast_share * 100, 2),
                "hot_event_share_pct": round(hot_event_share * 100, 2),
                "latest_odometer_km": round(odometer, 2),
                "warranty_risk_score": round(score, 2),
                "risk_band": _risk_band(score),
            }
        )
    _write_csv(path, rows, list(rows[0].keys()) if rows else [])
    return path


def _risk_band(score: float) -> str:
    if score >= 70:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


def _events_by_vehicle(events: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for event in events:
        grouped[str(event["vehicle_id"])].append(event)
    return grouped


def _count_by_vehicle(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["vehicle_id"])] += 1
    return counts


def _write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

