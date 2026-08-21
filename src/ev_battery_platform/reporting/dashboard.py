from __future__ import annotations

import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class ReportResult:
    dashboard_path: Path
    summary_path: Path
    vehicles: int
    regions: int
    high_risk_vehicles: int


def build_reports(
    gold_dir: Path = Path("data/gold"),
    silver_dir: Path = Path("data/silver"),
    output_dir: Path = Path("reports"),
) -> ReportResult:
    output_dir.mkdir(parents=True, exist_ok=True)

    health = _read_csv(gold_dir / "battery_health_summary.csv")
    charging = _read_csv(gold_dir / "charging_intelligence.csv")
    thermal = _read_csv(gold_dir / "thermal_risk_events.csv")
    warranty = _read_csv(gold_dir / "warranty_risk_scores.csv")
    rejected = _read_csv(silver_dir / "rejected_events.csv")

    dashboard_path = output_dir / "dashboard.html"
    summary_path = output_dir / "executive_summary.md"

    dashboard_path.write_text(
        _render_dashboard(health, charging, thermal, warranty, rejected),
        encoding="utf-8",
    )
    summary_path.write_text(
        _render_summary(health, charging, thermal, warranty, rejected),
        encoding="utf-8",
    )

    return ReportResult(
        dashboard_path=dashboard_path,
        summary_path=summary_path,
        vehicles=len(health),
        regions=len(charging),
        high_risk_vehicles=sum(1 for row in warranty if row.get("risk_band") == "high"),
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _render_summary(
    health: list[dict[str, str]],
    charging: list[dict[str, str]],
    thermal: list[dict[str, str]],
    warranty: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> str:
    avg_soh = _avg(health, "latest_soh_pct")
    total_energy = sum(_float(row, "total_energy_added_kwh") for row in charging)
    total_sessions = sum(_float(row, "charging_sessions") for row in charging)
    risk_counts = _risk_counts(warranty)
    top_risks = sorted(warranty, key=lambda row: _float(row, "warranty_risk_score"), reverse=True)[:5]

    lines = [
        "# EV Battery Health Executive Summary",
        "",
        f"Generated at: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        "",
        "## Fleet Snapshot",
        "",
        f"- Vehicles analyzed: {len(health)}",
        f"- German regions covered: {len(charging)}",
        f"- Average latest SOH: {avg_soh:.2f}%",
        f"- Charging sessions: {total_sessions:.0f}",
        f"- Energy added: {total_energy:,.1f} kWh",
        f"- Thermal risk events: {len(thermal)}",
        f"- Rejected bronze records: {len(rejected)}",
        "",
        "## Warranty Risk Distribution",
        "",
        f"- Low: {risk_counts['low']}",
        f"- Medium: {risk_counts['medium']}",
        f"- High: {risk_counts['high']}",
        "",
        "## Highest Priority Vehicles",
        "",
        "| Vehicle | SOH | Risk score | Risk band | Odometer |",
        "| --- | ---: | ---: | --- | ---: |",
    ]

    for row in top_risks:
        lines.append(
            "| "
            f"{row.get('vehicle_id', '')} | "
            f"{_float(row, 'latest_soh_pct'):.2f}% | "
            f"{_float(row, 'warranty_risk_score'):.2f} | "
            f"{row.get('risk_band', '')} | "
            f"{_float(row, 'latest_odometer_km'):,.0f} km |"
        )

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "The dashboard and this report are generated from the gold medallion outputs. They are intended for fleet operations, battery analytics, and portfolio demonstration workflows.",
        ]
    )
    return "\n".join(lines)


def _render_dashboard(
    health: list[dict[str, str]],
    charging: list[dict[str, str]],
    thermal: list[dict[str, str]],
    warranty: list[dict[str, str]],
    rejected: list[dict[str, str]],
) -> str:
    avg_soh = _avg(health, "latest_soh_pct")
    avg_risk = _avg(warranty, "warranty_risk_score")
    total_sessions = sum(_float(row, "charging_sessions") for row in charging)
    total_energy = sum(_float(row, "total_energy_added_kwh") for row in charging)
    risk_counts = _risk_counts(warranty)
    top_risks = sorted(warranty, key=lambda row: _float(row, "warranty_risk_score"), reverse=True)[:8]

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>EV Battery Health Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #607080;
      --line: #d8e0e8;
      --surface: #f7f9fb;
      --panel: #ffffff;
      --blue: #2563a8;
      --green: #2e7d5b;
      --amber: #b7791f;
      --red: #bd3b3b;
      --teal: #087f8c;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--surface);
      color: var(--ink);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.45;
    }}
    header {{
      background: #102033;
      color: #fff;
      padding: 28px clamp(18px, 4vw, 48px);
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: clamp(26px, 4vw, 42px);
      font-weight: 600;
      letter-spacing: 0;
    }}
    header p {{
      margin: 0;
      max-width: 980px;
      color: #dce7f2;
    }}
    main {{
      padding: 24px clamp(16px, 4vw, 48px) 40px;
      max-width: 1360px;
      margin: 0 auto;
    }}
    .metrics {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 14px;
      margin-bottom: 22px;
    }}
    .metric, section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    .metric {{
      padding: 16px;
      min-height: 104px;
    }}
    .metric .label {{
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .metric .value {{
      font-size: 26px;
      font-weight: 600;
      letter-spacing: 0;
    }}
    .metric .context {{
      color: var(--muted);
      font-size: 13px;
      margin-top: 6px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 18px;
    }}
    section {{
      padding: 18px;
      min-width: 0;
    }}
    section.wide {{
      grid-column: 1 / -1;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 18px;
      font-weight: 600;
      letter-spacing: 0;
    }}
    .bars {{
      display: grid;
      gap: 10px;
    }}
    .bar-row {{
      display: grid;
      grid-template-columns: 88px minmax(120px, 1fr) 92px;
      gap: 10px;
      align-items: center;
      font-size: 13px;
    }}
    .track {{
      height: 12px;
      background: #e9eef3;
      border-radius: 999px;
      overflow: hidden;
    }}
    .fill {{
      height: 100%;
      background: var(--blue);
    }}
    .fill.green {{ background: var(--green); }}
    .fill.amber {{ background: var(--amber); }}
    .fill.red {{ background: var(--red); }}
    .value-small {{
      color: var(--muted);
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    svg {{
      width: 100%;
      height: auto;
      display: block;
    }}
    .axis {{
      stroke: var(--line);
      stroke-width: 1;
    }}
    .dot {{
      fill: var(--teal);
      opacity: 0.72;
    }}
    .dot.medium {{
      fill: var(--amber);
    }}
    .dot.high {{
      fill: var(--red);
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 14px;
    }}
    th, td {{
      padding: 10px 8px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
    }}
    td.num, th.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .badge {{
      display: inline-block;
      min-width: 62px;
      padding: 3px 8px;
      border-radius: 999px;
      font-size: 12px;
      text-align: center;
      background: #e9eef3;
      color: var(--ink);
    }}
    .badge.medium {{
      background: #fff1cc;
      color: #704f00;
    }}
    .badge.high {{
      background: #ffe0df;
      color: #8c1f1f;
    }}
    footer {{
      margin-top: 18px;
      color: var(--muted);
      font-size: 13px;
    }}
    @media (max-width: 850px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
      .bar-row {{
        grid-template-columns: 72px minmax(90px, 1fr) 72px;
      }}
      table {{
        font-size: 13px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>EV Battery Health Dashboard</h1>
    <p>Fleet-level view of battery health, charging behavior, thermal risk, and warranty monitoring from the gold medallion datasets.</p>
  </header>
  <main>
    <div class="metrics" aria-label="Fleet metrics">
      {_metric("Vehicles", f"{len(health)}", "Battery packs analyzed")}
      {_metric("Average SOH", f"{avg_soh:.2f}%", "Latest observed state of health")}
      {_metric("Charging Sessions", f"{total_sessions:,.0f}", f"{total_energy:,.0f} kWh added")}
      {_metric("Avg Risk Score", f"{avg_risk:.2f}", f"{risk_counts['high']} high-risk vehicles")}
      {_metric("Thermal Events", f"{len(thermal):,}", "Elevated or critical battery temperature")}
      {_metric("Rejected Records", f"{len(rejected):,}", "Captured during silver validation")}
    </div>

    <div class="grid">
      <section>
        <h2>Warranty Risk Distribution</h2>
        {_risk_distribution(risk_counts, max(1, len(warranty)))}
      </section>

      <section>
        <h2>Charging Sessions by Region</h2>
        {_region_bars(charging, "charging_sessions", " sessions", "blue")}
      </section>

      <section>
        <h2>Energy Added by Region</h2>
        {_region_bars(charging, "total_energy_added_kwh", " kWh", "green")}
      </section>

      <section>
        <h2>DC Fast-Charging Share</h2>
        {_region_bars(charging, "dc_fast_session_share_pct", "%", "amber")}
      </section>

      <section class="wide">
        <h2>Battery Health vs Odometer</h2>
        {_scatter_health_vs_odometer(warranty)}
      </section>

      <section class="wide">
        <h2>Highest Priority Vehicles</h2>
        {_risk_table(top_risks)}
      </section>
    </div>

    <footer>
      Generated at {html.escape(datetime.now(timezone.utc).isoformat(timespec="seconds"))}. Source: gold and silver medallion outputs.
    </footer>
  </main>
</body>
</html>
"""


def _metric(label: str, value: str, context: str) -> str:
    return f"""
      <div class="metric">
        <div class="label">{html.escape(label)}</div>
        <div class="value">{html.escape(value)}</div>
        <div class="context">{html.escape(context)}</div>
      </div>
    """


def _risk_distribution(counts: dict[str, int], total: int) -> str:
    rows = [
        ("low", "Low", "green"),
        ("medium", "Medium", "amber"),
        ("high", "High", "red"),
    ]
    return '<div class="bars">' + "".join(
        _bar_row(label, counts[key] / total * 100, f"{counts[key]} vehicles", color)
        for key, label, color in rows
    ) + "</div>"


def _region_bars(rows: list[dict[str, str]], field: str, suffix: str, color: str) -> str:
    sorted_rows = sorted(rows, key=lambda row: _float(row, field), reverse=True)
    max_value = max((_float(row, field) for row in sorted_rows), default=1.0)
    return '<div class="bars">' + "".join(
        _bar_row(
            row.get("region", "unknown"),
            _float(row, field) / max_value * 100 if max_value else 0,
            _format_value(_float(row, field), suffix),
            color,
        )
        for row in sorted_rows
    ) + "</div>"


def _bar_row(label: str, width_pct: float, value: str, color: str) -> str:
    width = max(0.0, min(100.0, width_pct))
    return f"""
      <div class="bar-row">
        <div>{html.escape(label)}</div>
        <div class="track" aria-hidden="true"><div class="fill {html.escape(color)}" style="width: {width:.2f}%"></div></div>
        <div class="value-small">{html.escape(value)}</div>
      </div>
    """


def _scatter_health_vs_odometer(rows: list[dict[str, str]]) -> str:
    if not rows:
        return "<p>No warranty rows available.</p>"
    width = 980
    height = 360
    margin_left = 62
    margin_right = 24
    margin_top = 22
    margin_bottom = 48
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    odometers = [_float(row, "latest_odometer_km") for row in rows]
    soh_values = [_float(row, "latest_soh_pct") for row in rows]
    min_x, max_x = min(odometers), max(odometers)
    min_y, max_y = max(50.0, min(soh_values) - 2), min(100.0, max(soh_values) + 1)
    if max_x == min_x:
        max_x += 1
    if max_y == min_y:
        max_y += 1

    def x(value: float) -> float:
        return margin_left + (value - min_x) / (max_x - min_x) * plot_width

    def y(value: float) -> float:
        return margin_top + (max_y - value) / (max_y - min_y) * plot_height

    y_ticks = [min_y, (min_y + max_y) / 2, max_y]
    x_ticks = [min_x, (min_x + max_x) / 2, max_x]
    tick_markup = "".join(
        f'<line class="axis" x1="{margin_left}" y1="{y(tick):.1f}" x2="{width - margin_right}" y2="{y(tick):.1f}"></line>'
        f'<text x="{margin_left - 10}" y="{y(tick) + 4:.1f}" text-anchor="end" font-size="12" fill="#607080">{tick:.1f}%</text>'
        for tick in y_ticks
    )
    tick_markup += "".join(
        f'<line class="axis" x1="{x(tick):.1f}" y1="{margin_top}" x2="{x(tick):.1f}" y2="{height - margin_bottom}"></line>'
        f'<text x="{x(tick):.1f}" y="{height - 18}" text-anchor="middle" font-size="12" fill="#607080">{tick / 1000:.0f}k</text>'
        for tick in x_ticks
    )
    dots = "".join(
        f'<circle class="dot {html.escape(row.get("risk_band", ""))}" cx="{x(_float(row, "latest_odometer_km")):.1f}" cy="{y(_float(row, "latest_soh_pct")):.1f}" r="{4 + min(5, _float(row, "warranty_risk_score") / 20):.1f}">'
        f'<title>{html.escape(row.get("vehicle_id", ""))}: {_float(row, "latest_soh_pct"):.2f}% SOH, {_float(row, "latest_odometer_km"):,.0f} km, risk {_float(row, "warranty_risk_score"):.2f}</title>'
        '</circle>'
        for row in rows
    )
    return f"""
      <svg viewBox="0 0 {width} {height}" role="img" aria-label="Scatter chart showing battery state of health against odometer">
        <rect x="{margin_left}" y="{margin_top}" width="{plot_width}" height="{plot_height}" fill="#ffffff" stroke="#d8e0e8"></rect>
        {tick_markup}
        {dots}
        <text x="{width / 2}" y="{height - 4}" text-anchor="middle" font-size="13" fill="#17202a">Latest odometer, thousands of km</text>
        <text x="16" y="{height / 2}" text-anchor="middle" font-size="13" fill="#17202a" transform="rotate(-90 16 {height / 2})">Latest SOH, %</text>
      </svg>
    """


def _risk_table(rows: list[dict[str, str]]) -> str:
    body = "".join(
        f"""
        <tr>
          <td>{html.escape(row.get("vehicle_id", ""))}</td>
          <td>{html.escape(row.get("pack_id", ""))}</td>
          <td class="num">{_float(row, "latest_soh_pct"):.2f}%</td>
          <td class="num">{_float(row, "dc_fast_session_share_pct"):.2f}%</td>
          <td class="num">{_float(row, "hot_event_share_pct"):.2f}%</td>
          <td class="num">{_float(row, "warranty_risk_score"):.2f}</td>
          <td><span class="badge {html.escape(row.get("risk_band", ""))}">{html.escape(row.get("risk_band", ""))}</span></td>
        </tr>
        """
        for row in rows
    )
    return f"""
      <table>
        <thead>
          <tr>
            <th>Vehicle</th>
            <th>Pack</th>
            <th class="num">SOH</th>
            <th class="num">DC fast share</th>
            <th class="num">Hot event share</th>
            <th class="num">Risk score</th>
            <th>Band</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    """


def _risk_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = {"low": 0, "medium": 0, "high": 0}
    for row in rows:
        band = row.get("risk_band", "")
        if band in counts:
            counts[band] += 1
    return counts


def _avg(rows: list[dict[str, str]], field: str) -> float:
    values = [_float(row, field) for row in rows]
    return sum(values) / len(values) if values else 0.0


def _float(row: dict[str, str], field: str) -> float:
    try:
        return float(row.get(field, "0") or 0)
    except ValueError:
        return 0.0


def _format_value(value: float, suffix: str) -> str:
    if suffix == "%":
        return f"{value:.1f}%"
    if suffix.strip() == "kWh":
        return f"{value:,.0f} kWh"
    return f"{value:,.0f}{suffix}"

