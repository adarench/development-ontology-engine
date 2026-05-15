# BCPDev Operating State — Claude.ai web setup

**For Flagship users (finance / land dev / ops).** No installs. No
config files. No command line.

This is a read-only Q&A surface over the current BCPDev operating state
(projects, phases, cost coverage, allocation readiness, crosswalks,
exception rules). You ask questions in Claude on the web; Claude calls
the BCPDev tools behind the scenes and answers using only grounded
operational data.

## Setup (one time, ~2 minutes)

1. Open **https://claude.ai/** in a browser and sign in.
2. Click your profile icon in the bottom-left → **Settings**.
3. Click **Connectors** in the sidebar.
4. Scroll to the bottom of the page; click **+ Add custom connector**.
5. Fill in:
   - **Name:** `BCPDev Operating State`
   - **Remote MCP server URL:** `https://bcpd-mcp.fly.dev/mcp`
   - Leave Advanced settings empty (no OAuth Client ID / Secret).
6. Click **Add**. Claude should connect and list 13 tools.
7. Start a new chat. In the tools panel, ensure the
   **BCPDev Operating State** connector is toggled on.

That's it. The same 13 tools work in every chat from then on.

> If your plan is Free, Claude allows **one** custom connector at a time
> — you'll have to remove any other custom connector first. Pro / Max /
> Team / Enterprise have no such cap.

## Try these prompts

Copy/paste any of these into a new Claude chat. Watch the response —
Claude will show a small "calling tool…" indicator when it invokes one
of the BCPDev tools (you should see this for every prompt below; if you
don't, the connector isn't toggled on for that chat).

1. **Project brief.** "Give me a project brief for Parkway Fields."
   *Expect:* AultF B-suffix correction story, $4.0M routed B2 → B1, the
   per-row cost-basis table with the total, and the v2.1 correction
   narrative. The word "inferred" should appear — that's the system
   honestly marking per-lot decoder cost as not source-owner-ratified.

2. **Allocation logic.** "Explain the allocation logic for land."
   *Expect:* The current workbook-observed method
   (`land_at_mda` = community land pool × sales-basis % per phase), the
   lot-count control interpretation, and the Q23 caveat ("source-owner
   ratification pending"). Method ID `ALLOC-001`.

3. **Allocation readiness.** "Check allocation readiness for Parkway
   Fields E1." *Expect:* `method_status: compute_ready` paired with
   `run_readiness: not_ready`, top-line "❌ No — not cleanly today", a
   per-input checklist, and the MDA Day three-way tie status.

4. **Crosswalk readiness.** "Validate crosswalk readiness across all
   tables." *Expect:* 13 crosswalk tables enumerated, resolved counts,
   unresolved (UNRES-*) entries, stale source files. `CW-01` and
   `UNRES-01` will appear.

5. **False-precision risk audit.** "What risks or false precision issues
   should finance care about for BCPD?" *Expect:* six numbered risks —
   range/shell rows ($45.75M / 4,020 rows), inferred decoder,
   Harmony 3-tuple, SctLot vs Scarlet Ridge, HarmCo commercial,
   AultF B-suffix.

## What it WILL refuse

These refusals are by design. If you see them, the system is working
correctly — not malfunctioning.

- **Anything org-wide** — Hillcrest Road at Saratoga and Flagship
  Belmont GL coverage ends 2017-02. The system will say "out of scope"
  rather than fabricate org-wide numbers.
- **Promoting `inferred` per-lot cost to validated** — until a finance
  source-owner ratifies (Q23), per-lot decoder-derived cost stays
  `inferred`. The system will not pretend otherwise.
- **Allocating range/shell rows to specific lots** — the allocation
  method isn't ratified. The system will cite `EXC-007` (unratified
  method refusal) and keep those rows at project+phase grain.
- **Numeric values for unbuilt phases / phases with no master
  pricing** — `generate_per_lot_output_spec` returns the schema only,
  never invented dollar values.
- **Treating missing cost as $0** — projects without GL coverage are
  reported as `unknown`, never zero.

## A few rough edges to know about

- This is **read-only**. The system cannot write to ClickUp, QuickBooks,
  DataRails, or anywhere else. It only reads the bundled BCPD operating
  state plus the Parkway Fields satellite workbook snapshot.
- The Parkway Fields satellite read-through is a **workbook
  replication**, not authoritative compute. Every response from that
  tool leads with "NOT authoritative compute."
- Claude on the web may paraphrase tool output. If a refusal looks soft
  to you ("seems like the system maybe could do that") double-check by
  re-reading the actual tool response — Claude shows it in a foldable
  block. The raw tool text is the source of truth.
- Your chat content passes through Anthropic's cloud. This is the same
  posture as any other Claude conversation on the web. The BCPD server
  itself logs only tool names, durations, and outcomes — never your
  question text and never tool arguments.

## When something looks wrong

Ping Adam. Useful screenshots:

- The exact prompt you sent.
- The full Claude response, including any expanded tool-use blocks.
- The tool that was called (visible in the response).

The system is gated by source-owner validation (~8 open questions),
not engineering. If the tool answers "I don't know — that's pending
source-owner ratification," that's the honest answer, not a bug.
