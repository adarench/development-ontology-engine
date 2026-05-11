"""
Operating State Console v1 — single-file HTML interrogation console.

Renders the state as queryable Q&A with evidence and confidence labels.
Deliberately NOT a dashboard.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR   = REPO_ROOT / "output"

JSON_FILE       = OUT_DIR / "operating_state_v1.json"
OP_VIEW         = OUT_DIR / "operating_view_v1.csv"
LOT_STATE_FILE  = OUT_DIR / "lot_state_real.csv"
CONSOLE_OUT     = OUT_DIR / "operating_state_console_v1.html"


def esc(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return "—"
    return html.escape(str(v))


CSS = r"""
:root {
  --bg: #ffffff;
  --paper: #fbfaf7;
  --fg: #0b0b0d;
  --muted: #5b5b62;
  --line: #e2e2dc;
  --line-strong: #1a1a1d;
  --accent: #b45309;
  --green: #15803d;
  --amber: #b45309;
  --red: #b91c1c;
  --ink: #1f2937;
  --soft: #f5f4f0;
}
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); }
body {
  font-family: ui-sans-serif, -apple-system, BlinkMacSystemFont, "Inter", "Helvetica Neue", sans-serif;
  color: var(--fg);
  line-height: 1.55;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
}
.mono, code, pre { font-family: ui-monospace, "SF Mono", Menlo, "JetBrains Mono", monospace; }
.container { max-width: 980px; margin: 0 auto; padding: 40px 28px 80px; }

/* HEADER */
.console-header { padding-bottom: 22px; border-bottom: 2px solid var(--line-strong); }
.eyebrow { font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 11px;
           letter-spacing: 0.18em; text-transform: uppercase; color: var(--muted); }
h1 { font-size: 28px; font-weight: 600; margin: 6px 0 4px; letter-spacing: -0.015em; }
.subtitle { color: var(--muted); font-size: 14px; margin: 0 0 12px; }
.positioning { font-style: italic; color: var(--ink); font-size: 14px;
               border-left: 2px solid var(--accent); padding: 0 0 0 12px;
               margin: 14px 0 0; }

/* SNAPSHOT */
.snapshot { font-family: ui-monospace, "SF Mono", Menlo, monospace;
            font-size: 12.5px; letter-spacing: 0.01em;
            padding: 14px 0 18px; border-bottom: 1px solid var(--line);
            color: var(--ink); }
.snapshot .sep { color: var(--muted); margin: 0 12px; }
.snapshot .label { color: var(--muted); }
.snapshot .num { color: var(--fg); font-weight: 600; }

/* QUERY BLOCKS */
.queries { margin: 28px 0 0; }
.query { padding: 22px 0 24px; border-bottom: 1px solid var(--line); }
.query:last-of-type { border-bottom: none; }

.query-prompt {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 13px; letter-spacing: 0.01em;
  color: var(--ink);
  margin: 0 0 6px;
}
.query-prompt .caret { color: var(--accent); margin-right: 8px; font-weight: 600; }
.query-prompt .qid   { color: var(--muted); margin-right: 10px; }
.query-prompt .qtext { color: var(--fg); }

.query-block {
  margin: 14px 0 0;
}
.query-block-label {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 10.5px; letter-spacing: 0.16em; text-transform: uppercase;
  color: var(--muted);
  margin: 12px 0 6px;
}
.query-answer {
  font-size: 15px; line-height: 1.55; color: var(--fg);
  margin: 0;
}
.query-answer strong { font-weight: 600; }

/* EVIDENCE — terminal-style mono block */
.evidence {
  background: var(--soft);
  border: 1px solid var(--line);
  padding: 10px 12px;
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 12px;
  color: var(--ink);
  white-space: pre;
  overflow-x: auto;
  line-height: 1.55;
}
.evidence .ev-head { color: var(--muted); border-bottom: 1px solid var(--line);
                     padding-bottom: 4px; margin-bottom: 4px; display: block; }
.evidence .ev-row  { display: block; }
.evidence .ev-key  { color: var(--muted); }

/* CONFIDENCE / MISSING badges */
.meta-row { display: flex; flex-wrap: wrap; gap: 18px; margin: 10px 0 0; }
.meta-item { font-size: 13px; color: var(--ink); }
.meta-item .k { font-family: ui-monospace, "SF Mono", Menlo, monospace;
                font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase;
                color: var(--muted); margin-right: 8px; }

.cf { display: inline-block; padding: 1px 8px; font-size: 11px; border-radius: 2px;
      font-family: ui-monospace, "SF Mono", Menlo, monospace; letter-spacing: 0.04em;
      border: 1px solid; vertical-align: 1px; }
.cf-green  { background: #f0fdf4; color: var(--green); border-color: #bbf7d0; }
.cf-amber  { background: #fffbeb; color: var(--amber); border-color: #fde68a; }
.cf-red    { background: #fef2f2; color: var(--red);   border-color: #fecaca; }
.cf-multi  { padding: 0; border: none; background: transparent; }

/* LEGEND */
.legend { margin: 28px 0 0; padding: 14px 16px; border: 1px solid var(--line);
          background: var(--paper); border-radius: 2px; }
.legend-title { font-family: ui-monospace, "SF Mono", Menlo, monospace;
                font-size: 10.5px; letter-spacing: 0.16em; text-transform: uppercase;
                color: var(--muted); margin: 0 0 8px; }
.legend-row { display: flex; flex-wrap: wrap; gap: 28px; font-size: 13px; }
.legend-row span.cf { margin-right: 8px; }

/* DATA ASKS */
.asks {
  margin: 36px 0 0;
  padding: 22px 22px 18px;
  border: 1.5px solid var(--line-strong);
  border-radius: 2px;
  background: var(--paper);
}
.asks .eyebrow { font-size: 10.5px; }
.asks h2 { font-size: 18px; margin: 4px 0 14px; font-weight: 600; letter-spacing: -0.01em; }
.asks ol { padding-left: 20px; margin: 0; }
.asks li { margin-bottom: 8px; font-size: 14px; }
.asks li strong { color: var(--fg); }
.asks li code { background: var(--soft); padding: 1px 5px; border-radius: 2px;
                font-size: 12px; }

/* FOOTER */
.console-footer { margin-top: 36px; font-size: 12px; color: var(--muted);
                  border-top: 1px solid var(--line); padding-top: 14px; }
.console-footer .mono { font-size: 11.5px; }
"""


def conf_badge(level: str) -> str:
    cls = {"high": "cf-green", "estimated": "cf-amber",
           "partial": "cf-amber", "low": "cf-amber",
           "missing": "cf-red", "unavailable": "cf-red"}.get(level, "cf-amber")
    return f'<span class="cf {cls}">{html.escape(level)}</span>'


def evidence_table(headers: list[str], rows: list[list[str]]) -> str:
    """Renders a fixed-width ASCII-style monospace evidence block."""
    widths = [max(len(str(h)), max((len(str(r[i])) for r in rows), default=0)) for i, h in enumerate(headers)]
    head_line = "  ".join(str(h).ljust(widths[i]) for i, h in enumerate(headers))
    out = [f'<span class="ev-head">{html.escape(head_line)}</span>']
    for r in rows:
        line = "  ".join(str(c).ljust(widths[i]) for i, c in enumerate(r))
        out.append(f'<span class="ev-row">{html.escape(line)}</span>')
    return f'<div class="evidence">{"".join(out)}</div>'


# --- Query builders ---------------------------------------------------------

def q1_stuck(state: dict, op_view: pd.DataFrame) -> dict:
    le = op_view[op_view["project_code"] == "LE"].sort_values("lot_number")
    rows = [[str(int(float(r["lot_number"]))), str(r["stage"]),
             f"{float(r['completion_pct'])*100:.1f}%", str(r["status"])]
            for _, r in le.iterrows()]
    evidence = evidence_table(
        ["lot", "current_stage", "completion", "status"], rows
    )
    return {
        "id": "Q1",
        "question": "Where are lots currently stuck?",
        "answer": "<strong>LE</strong> has <strong>18 lots</strong> clustered at "
                  "<strong>Backfill</strong> — every active lot in the project sits at the same "
                  "Backfill→Spec handoff. This pattern strongly suggests a single bottleneck, "
                  "not 18 independent stalls.",
        "evidence": evidence,
        "confidence": [
            ("lot identity + current_stage", "high"),
            ("phase grouping (LE P1)",       "estimated"),
        ],
        "missing": "<code>start_date</code> / <code>date_done</code> per ClickUp task — "
                   "needed to measure how long the cohort has been at Backfill and confirm "
                   "this is a true bottleneck rather than synchronized progress.",
    }


def q2_missing_financials(state: dict) -> dict:
    rows = []
    for p in state["projects"]:
        f = p["financials"]
        rows.append([
            p["project_code"],
            f.get("gl_entity") or "(unmapped)",
            f"${f['project_total_cost']:,.0f}",
            f["financial_confidence"],
        ])
    evidence = evidence_table(
        ["project", "gl_entity", "total_cost", "confidence"], rows
    )
    return {
        "id": "Q2",
        "question": "Which projects have missing financials?",
        "answer": "<strong>LE</strong> maps to <em>Anderson Geneva LLC</em> in the GL, but the "
                  "GL sample contains <strong>no Activity rows</strong> for that entity — "
                  "only Beginning Balance entries. Cost is therefore <strong>unknown, not zero</strong>.",
        "evidence": evidence,
        "confidence": [
            ("financials are missing from sample (not zero spend)", "high"),
        ],
        "missing": "Anderson Geneva LLC Activity rows in the GL export.",
    }


def q3_low_confidence(state: dict) -> dict:
    low_lots = []
    for p in state["projects"]:
        for ph in p["phases"]:
            for l in ph["lots"]:
                if l.get("source_confidence") == "low":
                    low_lots.append([
                        p["project_code"],
                        ph["phase_id_estimated"],
                        str(l["lot_number"]),
                        l.get("stage") or "—",
                        l.get("status") or "—",
                    ])
    if low_lots:
        evidence = evidence_table(
            ["project", "phase_estimated", "lot", "stage", "status"], low_lots
        )
        rationale = (
            "These are <strong>bare parent rows</strong> in ClickUp (e.g. <code>H MF 77</code>) "
            "with no associated child tasks in the export. We know the lot exists; we cannot "
            "see its construction history."
        )
    else:
        evidence = '<div class="evidence">(no low-confidence lots in current sample)</div>'
        rationale = "All lots in this snapshot meet the high/medium confidence bar."

    return {
        "id": "Q3",
        "question": "Which lots are low confidence?",
        "answer": rationale,
        "evidence": evidence,
        "confidence": [("classification is deterministic", "high")],
        "missing": "Child task rows for these lots — once they exist in ClickUp, "
                   "they auto-promote to high-confidence on the next pipeline run.",
    }


def q4_trust(state: dict) -> dict:
    q = state["data_quality"]
    rows = [
        ["lot identity (project_code + lot_number)", "high",      "parsed from real ClickUp task names; 100% on 100 rows"],
        ["current stage of each lot",                 "high",      f"observed directly; 81% of rows mapped to a canonical stage"],
        ["completion %",                              "high",      "computed from observed stage rank / total stages"],
        ["stage distribution per project",            "high",      "aggregated from above"],
        ["phase identifiers",                         "estimated", "heuristic (gap-based clustering on lot_number)"],
        ["per-lot cost",                              "missing",   "GL has no lot-level signal; not computed"],
        ["stage durations",                           "missing",   "ClickUp start_date / date_done populated 0–1% in sample"],
    ]
    evidence = evidence_table(["claim", "tier", "source"], rows)
    return {
        "id": "Q4",
        "question": "What can we trust right now?",
        "answer": "Trustworthy: <strong>lot identity</strong>, <strong>project code</strong>, "
                  "<strong>current stage</strong>, <strong>completion %</strong>, and "
                  "<strong>stage distribution</strong>. Not trustworthy as ground truth: "
                  "real phase IDs and lot-level costs — these are flagged as estimated or unavailable.",
        "evidence": evidence,
        "confidence": [
            ("trustworthy facts above", "high"),
            ("phase IDs",               "estimated"),
            ("lot-level cost",          "unavailable"),
        ],
        "missing": "(see Q5)",
    }


def q5_v2(state: dict) -> dict:
    rows = [
        ["full ClickUp export",                 "currently 100-row preview"],
        ["plat → phase → lot reference",        "removes the heuristic phase model"],
        ["GL with Class / Customer:Job / TxID", "single highest-leverage change"],
        ["GL Vendor / Memo populated",          "97% placeholder today"],
        ["Anderson Geneva activity rows",       "LE financials currently $0"],
        ["start_date / date_done in ClickUp",   "unlocks stage durations"],
    ]
    evidence = evidence_table(["data needed", "why"], rows)
    return {
        "id": "Q5",
        "question": "What data unlocks v2?",
        "answer": "Three structural feeds are required: <strong>full ClickUp export</strong>, "
                  "a <strong>plat → phase → lot reference</strong>, and a <strong>GL re-export</strong> "
                  "with <code>Class</code>, <code>Customer:Job</code>, <code>Transaction ID</code>, "
                  "<code>Vendor</code>, and <code>Memo</code> restored. With these, v1 → v2 needs no "
                  "architectural changes — just better input.",
        "evidence": evidence,
        "confidence": [("scope of asks", "high")],
        "missing": "—",
    }


# --- Render ----------------------------------------------------------------

def render_query(q: dict) -> str:
    conf_html = " &nbsp; ".join(
        f"{html.escape(label)} {conf_badge(level)}"
        for label, level in q["confidence"]
    )
    return f"""
    <article class="query">
      <p class="query-prompt">
        <span class="caret">❯</span><span class="qid">{q['id']}</span><span class="qtext">{html.escape(q['question'])}</span>
      </p>

      <div class="query-block">
        <div class="query-block-label">Answer</div>
        <p class="query-answer">{q['answer']}</p>
      </div>

      <div class="query-block">
        <div class="query-block-label">Evidence</div>
        {q['evidence']}
      </div>

      <div class="meta-row">
        <div class="meta-item"><span class="k">Confidence</span> <span class="cf cf-multi">{conf_html}</span></div>
        <div class="meta-item"><span class="k">Missing</span> {q['missing']}</div>
      </div>
    </article>
    """


def render_console(state: dict, op_view: pd.DataFrame) -> str:
    q = state["data_quality"]
    proj_with_cost = sum(1 for p in state["projects"] if p["financials"]["project_total_cost"] > 0)
    coverage = "partial" if proj_with_cost < q["projects_total"] else "full"

    snapshot = (
        f'<span class="num">{q["projects_total"]}</span> <span class="label">projects</span>'
        f'<span class="sep">·</span>'
        f'<span class="num">{q["lots_total"]}</span> <span class="label">lots</span>'
        f'<span class="sep">·</span>'
        f'<span class="num">{q["phases_estimated"]}</span> <span class="label">estimated phases</span>'
        f'<span class="sep">·</span>'
        f'<span class="num">{q["lots_high_confidence"]}</span> <span class="label">high-confidence lots</span>'
        f'<span class="sep">·</span>'
        f'<span class="label">GL coverage:</span> <span class="num">{coverage}</span>'
    )

    queries_html = "".join(render_query(qq) for qq in [
        q1_stuck(state, op_view),
        q2_missing_financials(state),
        q3_low_confidence(state),
        q4_trust(state),
        q5_v2(state),
    ])

    legend = f"""
    <div class="legend">
      <div class="legend-title">Confidence Legend</div>
      <div class="legend-row">
        <div>{conf_badge("high")} real parsed state</div>
        <div>{conf_badge("estimated")} heuristic / inferred</div>
        <div>{conf_badge("missing")} input not available in current export</div>
      </div>
    </div>
    """

    asks = """
    <section class="asks">
      <p class="eyebrow">DATA ASKS</p>
      <h2>Exact asks to move from v1 → v2</h2>
      <ol>
        <li><strong>Full ClickUp export</strong> — currently a 100-row preview. Same parser handles full volume.</li>
        <li><strong>Plat / phase / lot reference table</strong> — replaces the heuristic phase model with named plat phases.</li>
        <li><strong>GL re-export</strong> with <code>Class</code>, <code>Customer:Job</code>, <code>Transaction ID</code> / <code>JE ID</code>, <code>Vendor</code>, <code>Memo</code> — single highest-leverage change. Moves cost visibility from project-level to phase- or lot-level.</li>
        <li><strong>Anderson Geneva LLC activity rows</strong> — currently only Beginning Balance rows; LE cost reads as $0.</li>
        <li><strong>ClickUp <code>start_date</code> and <code>date_done</code> per task</strong> — unlocks stage-duration analytics.</li>
      </ol>
    </section>
    """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Operating State Console v1</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
<div class="container">

  <header class="console-header">
    <div class="eyebrow">OPERATING STATE — CONSOLE</div>
    <h1>Operating State Console v1</h1>
    <p class="subtitle">Reconstructed from ClickUp + GL extracts</p>
    <p class="positioning">Not a dashboard — a structured state layer that agents can query.</p>
  </header>

  <div class="snapshot">{snapshot}</div>

  <section class="queries">{queries_html}</section>

  {legend}

  {asks}

  <footer class="console-footer">
    <div>Generated <span class="mono">{html.escape(state.get("generated_at", ""))}</span></div>
    <div class="mono">source: operating_state_v1.json · operating_view_v1.csv · lot_state_real.csv · project_state_real.csv</div>
  </footer>

</div>
</body>
</html>
"""


def main() -> None:
    state = json.loads(JSON_FILE.read_text())
    op_view = pd.read_csv(OP_VIEW)

    out_html = render_console(state, op_view)
    CONSOLE_OUT.write_text(out_html)

    print(f"Wrote: {CONSOLE_OUT}  ({CONSOLE_OUT.stat().st_size:,} bytes)")
    print()
    print("Difference from operating_dashboard_v1.html:")
    print("  - Removed: KPI tile grid, sortable lot table, project rollup table,")
    print("    progress bars, status pills.")
    print("  - Added: 5 prebuilt queries, each with answer + evidence + confidence")
    print("    + missing-input — rendered like a REPL/analyst console, not a dashboard.")
    print("  - Layout: query-driven (Q1..Q5), monospace prompts, terminal-style")
    print("    evidence blocks. The asks panel is now visually load-bearing,")
    print("    not a footnote.")
    print("  - Tone: 'ask the state, get a grounded answer with provenance' — not")
    print("    'glance at metrics'. The dashboard answers 'what's the state?';")
    print("    the console answers 'what can we say with confidence, and why?'.")


if __name__ == "__main__":
    main()
