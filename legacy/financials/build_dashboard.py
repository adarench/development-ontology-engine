"""
Build a single-file executive-readable HTML dashboard from Operating State v1
outputs. No external deps; opens straight in a browser.
"""
from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR   = REPO_ROOT / "output"

OPERATING_VIEW = OUT_DIR / "operating_view_v1.csv"
LOT_STATE      = OUT_DIR / "lot_state_real.csv"
PROJECT_STATE  = OUT_DIR / "project_state_real.csv"
PHASE_STATE    = OUT_DIR / "phase_state_real.csv"
STATE_JSON     = OUT_DIR / "operating_state_v1.json"
DASH_OUT       = OUT_DIR / "operating_dashboard_v1.html"


def _safe(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return html.escape(str(v))


def status_class(status: str) -> str:
    return {
        "complete":      "st-complete",
        "near_complete": "st-near",
        "in_progress":   "st-progress",
        "not_started":   "st-idle",
    }.get(status, "st-idle")


def progress_bar(pct: float) -> str:
    pct = 0.0 if pd.isna(pct) else max(0.0, min(1.0, float(pct)))
    width = f"{pct * 100:.1f}%"
    return f"""<div class="bar"><div class="bar-fill" style="width:{width}"></div><span class="bar-text">{pct*100:.1f}%</span></div>"""


def derive_insights(state: dict) -> list[dict]:
    out = []
    for p in state["projects"]:
        for ph in p.get("phases", []):
            if ph["lots_in_phase"] >= 5 and ph["avg_completion_pct"] < 0.6:
                out.append({
                    "tone": "warning",
                    "text": f"<strong>{html.escape(p['project_code'])}</strong> has "
                            f"<strong>{ph['lots_in_phase']} lots</strong> clustered at "
                            f"<strong>{html.escape(ph.get('dominant_stage') or '—')}</strong> in estimated phase "
                            f"<code>{html.escape(ph['phase_id_estimated'])}</code> "
                            f"({ph['avg_completion_pct']*100:.1f}% avg complete) — "
                            f"likely a single-stage handoff bottleneck."
                })
    for p in state["projects"]:
        f = p.get("financials", {})
        if f.get("project_total_cost", 0) == 0:
            ent = f.get("gl_entity") or "no entity mapping"
            out.append({
                "tone": "info",
                "text": f"<strong>{html.escape(p['project_code'])}</strong> financials are missing "
                        f"because <em>{html.escape(ent)}</em> has no Activity rows in the GL sample. "
                        f"Cost is <strong>unknown, not zero</strong>."
            })
    n_phases = state["data_quality"]["phases_estimated"]
    out.append({
        "tone": "info",
        "text": f"All <strong>{n_phases}</strong> phases shown are <strong>estimated</strong> "
                f"(gap-based clustering on lot_number). They will be replaced when a real "
                f"plat→lot reference table is wired in."
    })
    low = state["data_quality"]["lots_low_confidence"]
    if low:
        out.append({
            "tone": "warning",
            "text": f"<strong>{low}</strong> low-confidence lot(s) — bare parent rows in ClickUp with no "
                    f"associated tasks. Stage detail unknown."
        })
    return out


def financial_label(total_cost: float, confidence: str) -> tuple[str, str]:
    """(class, label)"""
    if total_cost > 0 and confidence == "high":
        return "fin-ok", "cost available"
    if total_cost == 0:
        return "fin-missing", "cost missing"
    return "fin-partial", "partial"


CSS = """
:root {
  --bg: #ffffff;
  --fg: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --soft: #f9fafb;
  --soft-2: #f3f4f6;
  --accent: #0f766e;
  --accent-soft: #ccfbf1;
  --warn: #b45309;
  --warn-soft: #fef3c7;
  --green: #15803d;
  --amber: #b45309;
  --gray: #4b5563;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  color: var(--fg);
  background: var(--bg);
  line-height: 1.45;
  -webkit-font-smoothing: antialiased;
}
.container { max-width: 1200px; margin: 0 auto; padding: 32px 28px 64px; }
header { padding-bottom: 20px; border-bottom: 1px solid var(--line); margin-bottom: 28px; }
h1 { font-size: 24px; font-weight: 600; margin: 0 0 4px; letter-spacing: -0.01em; }
.subtitle { color: var(--muted); font-size: 14px; margin: 0; }
.meta { color: var(--muted); font-size: 12px; margin-top: 8px; }
section { margin-bottom: 36px; }
h2 { font-size: 14px; text-transform: uppercase; letter-spacing: 0.06em; font-weight: 600;
     color: var(--muted); margin: 0 0 14px; }

/* KPI cards */
.kpi-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; }
.kpi {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 14px 16px;
  background: var(--bg);
}
.kpi .label { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em;
              color: var(--muted); margin-bottom: 6px; }
.kpi .value { font-size: 22px; font-weight: 600; }
.kpi .sub { font-size: 11px; color: var(--muted); margin-top: 4px; }

/* Tables */
table { width: 100%; border-collapse: collapse; font-size: 13px; }
th { text-align: left; font-weight: 600; padding: 8px 10px; border-bottom: 1px solid var(--line);
     color: var(--muted); text-transform: uppercase; font-size: 11px; letter-spacing: 0.04em; }
td { padding: 8px 10px; border-bottom: 1px solid var(--soft-2); vertical-align: middle; }
tr:hover td { background: var(--soft); }
.table-wrap { border: 1px solid var(--line); border-radius: 6px; overflow: hidden; }

/* Status pills */
.pill { display: inline-block; padding: 2px 8px; font-size: 11px; border-radius: 999px;
        font-weight: 500; border: 1px solid transparent; }
.st-complete { background: #dcfce7; color: #166534; border-color: #bbf7d0; }
.st-near     { background: var(--accent-soft); color: var(--accent); border-color: #99f6e4; }
.st-progress { background: var(--warn-soft); color: var(--warn); border-color: #fde68a; }
.st-idle     { background: var(--soft-2); color: var(--gray); border-color: var(--line); }
.fin-ok      { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.fin-missing { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.fin-partial { background: var(--warn-soft); color: var(--warn); border: 1px solid #fde68a; }

/* Progress bar */
.bar { position: relative; width: 110px; height: 16px; background: var(--soft-2);
       border-radius: 3px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--gray); }
.bar-text { position: absolute; top: 0; left: 0; right: 0; bottom: 0;
            font-size: 10px; line-height: 16px; text-align: center;
            font-weight: 500; color: var(--fg); mix-blend-mode: luminosity; }

/* Insight cards */
.insight { padding: 12px 14px; border: 1px solid var(--line); border-radius: 6px;
           background: var(--soft); margin-bottom: 8px; font-size: 13px; }
.insight.warning { border-left: 3px solid var(--warn); }
.insight.info    { border-left: 3px solid var(--accent); }

/* Trust grid */
.trust-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px; }
.trust { padding: 12px 14px; border: 1px solid var(--line); border-radius: 6px; }
.trust .name { font-size: 13px; font-weight: 600; margin-bottom: 4px; }
.trust .tier { display: inline-block; padding: 2px 8px; font-size: 11px;
               border-radius: 999px; margin-right: 6px; font-weight: 500; }
.tier.high { background: #dcfce7; color: #166534; border: 1px solid #bbf7d0; }
.tier.estimated { background: var(--warn-soft); color: var(--warn); border: 1px solid #fde68a; }
.tier.partial { background: var(--warn-soft); color: var(--warn); border: 1px solid #fde68a; }
.tier.unavailable { background: #fee2e2; color: #991b1b; border: 1px solid #fecaca; }
.trust .why { font-size: 12px; color: var(--muted); margin-top: 4px; }

/* Asks list */
.asks { padding-left: 18px; margin: 0; font-size: 13px; }
.asks li { margin-bottom: 6px; }
.asks li strong { color: var(--fg); }

code { font-family: "SF Mono", Menlo, Consolas, monospace; font-size: 12px;
       background: var(--soft-2); padding: 1px 5px; border-radius: 3px; }
small.note { color: var(--muted); font-size: 12px; }
"""


def render_kpis(state: dict) -> str:
    q = state["data_quality"]
    proj_with_cost = sum(1 for p in state["projects"]
                         if p["financials"]["project_total_cost"] > 0)
    n_in_progress  = sum(1 for p in state["projects"] for ph in p["phases"]
                         for l in ph["lots"] if l["status"] == "in_progress")
    n_near_or_done = sum(1 for p in state["projects"] for ph in p["phases"]
                         for l in ph["lots"] if l["status"] in {"near_complete", "complete"})
    cards = [
        ("Projects", q["projects_total"], "detected"),
        ("Lots", q["lots_total"], f"{q['lots_high_confidence']} high-confidence"),
        ("Estimated phases", q["phases_estimated"], "heuristic"),
        ("Lots in progress", n_in_progress, ""),
        ("Near complete / complete", n_near_or_done, ""),
        ("Projects with cost data", f"{proj_with_cost}/{q['projects_total']}", "GL Activity rows present"),
    ]
    items = "\n".join(
        f'<div class="kpi"><div class="label">{html.escape(label)}</div>'
        f'<div class="value">{html.escape(str(value))}</div>'
        f'<div class="sub">{html.escape(sub)}</div></div>'
        for label, value, sub in cards
    )
    return f'<section><h2>Executive Summary</h2><div class="kpi-grid">{items}</div></section>'


def render_operating_table(operating_view: pd.DataFrame, state: dict) -> str:
    # Build a lookup: project_code → financial coverage label
    fin_label_for = {}
    for p in state["projects"]:
        f = p["financials"]
        cls, label = financial_label(f["project_total_cost"], f["financial_confidence"])
        fin_label_for[p["project_code"]] = (cls, label, f.get("financial_notes", ""))

    rows_html = []
    for _, r in operating_view.iterrows():
        proj = _safe(r["project_code"])
        fin_cls, fin_label, _ = fin_label_for.get(r["project_code"], ("fin-missing", "—", ""))
        status_val = _safe(r["status"])
        rows_html.append(f"""
        <tr>
          <td>{proj}</td>
          <td><code>{_safe(r["phase_id_estimated"])}</code></td>
          <td>{_safe(r["lot_number"])}</td>
          <td>{_safe(r["stage"])}</td>
          <td>{progress_bar(r["completion_pct"])}</td>
          <td><span class="pill {status_class(r['status'])}">{status_val.replace("_", " ")}</span></td>
          <td><span class="pill {fin_cls}">{html.escape(fin_label)}</span></td>
        </tr>""")
    body = "\n".join(rows_html)
    return f"""
    <section>
      <h2>Operating View</h2>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Project</th>
              <th>Estimated Phase</th>
              <th>Lot #</th>
              <th>Current Stage</th>
              <th>Completion</th>
              <th>Status</th>
              <th>Financial Coverage</th>
            </tr>
          </thead>
          <tbody>{body}</tbody>
        </table>
      </div>
      <small class="note">"Estimated phase" is a heuristic grouping by lot_number proximity, not a plat reference. "Financial coverage" reflects whether GL Activity rows exist for the mapped entity.</small>
    </section>"""


def render_project_rollup(project_state: pd.DataFrame, state: dict) -> str:
    fin_for = {p["project_code"]: p["financials"] for p in state["projects"]}
    rows = []
    for _, r in project_state.iterrows():
        f = fin_for.get(r["project_code"], {})
        cls, label = financial_label(f.get("project_total_cost", 0), f.get("financial_confidence", "low"))
        # Pick dominant stage as the most-frequent in stage_distribution.
        dom = "—"
        if isinstance(r["stage_distribution"], str) and r["stage_distribution"]:
            parts = [p.split(":") for p in r["stage_distribution"].split("|") if ":" in p]
            parts = [(k, int(v)) for k, v in parts]
            parts.sort(key=lambda kv: -kv[1])
            if parts:
                dom = parts[0][0]
        rows.append(f"""
        <tr>
          <td><strong>{_safe(r["project_code"])}</strong></td>
          <td>{_safe(int(r["total_lots"]))}</td>
          <td>{progress_bar(r["avg_completion_pct"])}</td>
          <td>{_safe(dom)}</td>
          <td><code style="font-size:11px">{_safe(r["stage_distribution"])}</code></td>
          <td><span class="pill {cls}">{html.escape(label)}</span></td>
        </tr>""")
    return f"""
    <section>
      <h2>Project Rollup</h2>
      <div class="table-wrap">
        <table>
          <thead><tr>
            <th>Project</th><th>Total Lots</th><th>Avg Completion</th>
            <th>Dominant Stage</th><th>Stage Distribution</th><th>Financial Status</th>
          </tr></thead>
          <tbody>{"".join(rows)}</tbody>
        </table>
      </div>
    </section>"""


def render_insights(state: dict) -> str:
    cards = derive_insights(state)
    items = "\n".join(
        f'<div class="insight {c["tone"]}">{c["text"]}</div>' for c in cards
    )
    return f'<section><h2>Bottlenecks &amp; Insights</h2>{items}</section>'


def render_trust() -> str:
    rows = [
        ("LotState",       "high",        "Parsed from real ClickUp tasks. 100% project_code+lot_number, 86% with valid stage progression."),
        ("PhaseState",     "estimated",   "Heuristic only — gap-based clustering on lot_number (gap ≥ 10). Not a plat reference."),
        ("Financials",     "partial",     "Project-level totals available where GL Activity rows exist. LE shows $0 because Anderson Geneva has no Activity rows in this sample."),
        ("Lot-level cost", "unavailable", "GL has no lot-level signal. Not computed and not displayed."),
    ]
    cards = "\n".join(
        f'<div class="trust"><div class="name">{html.escape(name)}</div>'
        f'<span class="tier {tier}">{html.escape(tier)}</span>'
        f'<div class="why">{html.escape(why)}</div></div>'
        for name, tier, why in rows
    )
    return f'<section><h2>Data Quality &amp; Trust</h2><div class="trust-grid">{cards}</div></section>'


def render_asks() -> str:
    asks = [
        ("Full ClickUp export", "currently a 100-row preview; same parser handles full volume"),
        ("Real plat / phase / lot reference table", "replaces the heuristic phase model with named plat phases"),
        ("GL re-export with <code>Class</code>, <code>Customer:Job</code>, <code>Transaction ID</code>, <code>Vendor</code>, <code>Memo</code>", "single highest-leverage change — moves cost visibility from project-level to phase- or lot-level"),
        ("Anderson Geneva activity rows", "currently only Beginning Balance rows; LE cost reads as $0"),
        ("ClickUp <code>start_date</code> and <code>date_done</code> populated per task", "unlocks stage-duration analytics"),
    ]
    items = "\n".join(f"<li><strong>{label}</strong> — {detail}</li>" for label, detail in asks)
    return f'<section><h2>Missing Inputs / Next Asks</h2><ol class="asks">{items}</ol></section>'


def render_dashboard(state: dict, operating_view: pd.DataFrame, project_state: pd.DataFrame) -> str:
    generated_at = state.get("generated_at", datetime.utcnow().isoformat())
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Operating View v1</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<div class="container">
  <header>
    <h1>Operating View v1</h1>
    <p class="subtitle">Prototype built from ClickUp + GL extracts</p>
    <p class="meta">Generated {html.escape(generated_at)}</p>
  </header>

  {render_kpis(state)}
  {render_operating_table(operating_view, state)}
  {render_project_rollup(project_state, state)}
  {render_insights(state)}
  {render_trust()}
  {render_asks()}
</div>
</body>
</html>
"""


def main() -> None:
    operating_view = pd.read_csv(OPERATING_VIEW)
    project_state  = pd.read_csv(PROJECT_STATE)
    state          = json.loads(STATE_JSON.read_text())

    # Stable display order: project_code, then estimated phase, then lot_number.
    operating_view = operating_view.sort_values(
        ["project_code", "phase_id_estimated", "lot_number"], na_position="last"
    ).reset_index(drop=True)

    html_out = render_dashboard(state, operating_view, project_state)
    DASH_OUT.write_text(html_out)

    print(f"Wrote: {DASH_OUT}  ({DASH_OUT.stat().st_size:,} bytes)")
    print()
    print("Data files used:")
    for p in [OPERATING_VIEW, PROJECT_STATE, STATE_JSON]:
        print(f"  - {p.relative_to(REPO_ROOT)}")
    print()
    print("Assumptions:")
    print("  - 'Estimated Phase' values come from gap-based clustering (heuristic).")
    print("  - 'Financial coverage' = 'cost available' iff GL entity matched AND total_cost > 0;")
    print("    'cost missing' iff total_cost == 0; 'partial' otherwise.")
    print("  - Bottleneck flag fires when a phase has ≥5 lots AND avg completion < 0.6.")
    print("  - cost_per_lot is intentionally NOT displayed (GL has no lot-level signal).")
    print(f"  - 'Generated' timestamp is taken from operating_state_v1.json, not regenerated.")


if __name__ == "__main__":
    main()
