# BCPD Operating State v2.1 — Query Examples

_Generated: 2026-05-01_

10 worked queries that respect the v2.1 rules (3-tuple lot joins, range rows
at project+phase grain, commercial parcels as non-lot exception, SctLot as
its own project). All examples use the v2.1 artifacts.

Run from the repo root with `python3 -c "..."`. All queries assume `pandas`,
`pyarrow`, and `json` are importable.

---

## 1. Per-lot VF cost for Parkway Fields Phase B1 (uses 3-tuple, including the AultF B→B1 correction)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
pwf = next(p for p in d['projects'] if p['canonical_project'] == 'Parkway Fields')
b1 = next(ph for ph in pwf['phases'] if ph['canonical_phase'] == 'B1')
print(f"Phase B1 lots ({b1['lot_count_observed']}):")
for lot in sorted(b1['lots'], key=lambda x: -x.get('vf_actual_cost_3tuple_usd', 0)):
    if lot.get('vf_actual_cost_3tuple_usd', 0) > 0:
        print(f"  Lot {lot['canonical_lot_number']}: ${lot['vf_actual_cost_3tuple_usd']:,.0f} ({lot['vf_actual_cost_rows']} rows) — confidence: {lot['vf_actual_cost_confidence']}")
print(f"\nUnattributed shell dollars at Phase B1: ${b1['vf_unattributed_shell_dollars']:,.0f} ({b1['vf_unattributed_shell_rows']} rows)")
```

What you'll see: AultF B-suffix lots 0127B–0211B now correctly attached to B1
(was misrouted to B2 in v2.0). Per-lot $ are inferred (decoder-derived);
shell dollars listed separately, not summed into per-lot.

---

## 2. Total Harmony VF cost — using the 3-tuple discipline (NOT flat 2-tuple)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
harmony = next(p for p in d['projects'] if p['canonical_project'] == 'Harmony')
print(f"Harmony 2018-2025 cost partitions:")
print(f"  Lot-grain (3-tuple matched): ${harmony['actuals']['vf_lot_grain_sum_usd']:,.0f} across {harmony['actuals']['vf_lot_grain_rows']:,} rows")
print(f"  Range/shell grain (project+phase only): ${harmony['actuals']['vf_range_grain_sum_usd']:,.0f} across {harmony['actuals']['vf_range_grain_rows']:,} rows")
print(f"  Commercial parcels (non-lot): ${harmony['actuals']['vf_commercial_grain_sum_usd']:,.0f}")
print(f"  Total: ${harmony['actuals']['vf_2018_2025_sum_usd']:,.0f}")
print(f"\nNOTE: do NOT use a flat (project, lot) join — would double-count $6.75M (MF1 lot 101 vs B1 lot 101).")
```

---

## 3. List Harmony commercial parcels (non-lot inventory)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
harmony = next(p for p in d['projects'] if p['canonical_project'] == 'Harmony')
print("Harmony commercial parcels (NOT residential lots):")
for pad in harmony.get('commercial_parcels_non_lot', []):
    print(f"  Pad {pad['pad']}: ${pad['dollars']:,.0f} ({pad['rows']} rows) — {pad['treatment']}")
```

What you'll see: 11 pads A through K. Most cost concentrated on pads A and B
(active vertical construction); C-K largely placeholder.

---

## 4. Scattered Lots cost (formerly mis-attributed to Scarlet Ridge in v2.0)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
sl = next(p for p in d['projects'] if p['canonical_project'] == 'Scattered Lots')
print(f"Scattered Lots project (new in v2.1):")
print(f"  Total cost: ${sl['actuals']['vf_2018_2025_sum_usd']:,.0f}")
print(f"  Rows: {sl['actuals']['vf_2018_2025_rows']:,}")
print(f"  Note: {sl['v2_1_note']}")
print()
sr = next(p for p in d['projects'] if p['canonical_project'] == 'Scarlet Ridge')
print(f"Scarlet Ridge cost (v2.1, after SctLot removal): ${sr['actuals']['vf_2018_2025_sum_usd']:,.0f}")
print(f"  vs v2.0 (which silently included SctLot): ~$6.55M higher")
```

---

## 5. Surface unattributed shell dollars per project

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
print("Unattributed shell-allocation dollars per project (v2.1):")
total_shell = 0
for p in d['projects']:
    shell = p['actuals'].get('vf_range_grain_sum_usd', 0)
    if shell > 0:
        print(f"  {p['canonical_project']}: ${shell:,.0f} (project+phase grain only; not allocated to specific lots)")
        total_shell += shell
print(f"\nBCPD total unattributed shell: ${total_shell:,.0f}")
print("This is ~13% of BCPD VF cost basis. v2.2 candidate: expand to per-lot synthetic rows after allocation-method sign-off.")
```

What you'll see: PWFT1 (Parkway Townhomes), MCreek, HarmTo dominate.
$45.75M total surfaced as a separate line.

---

## 6. Compare v2.0 vs v2.1 for a Harmony lot that exists in both MF1 and B1

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
harmony = next(p for p in d['projects'] if p['canonical_project'] == 'Harmony')
mf1 = next(ph for ph in harmony['phases'] if ph['canonical_phase'] == 'MF1')
b1 = next(ph for ph in harmony['phases'] if ph['canonical_phase'] == 'B1')
mf1_101 = next((l for l in mf1['lots'] if l['canonical_lot_number'] == '101'), None)
b1_101 = next((l for l in b1['lots'] if l['canonical_lot_number'] == '101'), None)
print(f"Harmony Lot 101 (two physical lots, same lot number):")
if mf1_101:
    print(f"  MF1 Lot 101: ${mf1_101.get('vf_actual_cost_3tuple_usd',0):,.0f} ({mf1_101.get('vf_actual_cost_rows',0)} rows) — current_stage: {mf1_101.get('current_stage')}")
if b1_101:
    print(f"  B1  Lot 101: ${b1_101.get('vf_actual_cost_3tuple_usd',0):,.0f} ({b1_101.get('vf_actual_cost_rows',0)} rows) — current_stage: {b1_101.get('current_stage')}")
print(f"\nv2.0 would have collapsed these onto a single inventory row, losing $443K of distinguishing detail.")
```

---

## 7. AultF SR-suffix isolation (inferred-unknown)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
pwf = next(p for p in d['projects'] if p['canonical_project'] == 'Parkway Fields')
sr_dollars = pwf['actuals'].get('vf_sr_inferred_unknown_sum_usd', 0)
sr_rows = pwf['actuals'].get('vf_sr_inferred_unknown_rows', 0)
print(f"Parkway Fields AultF SR-suffix: ${sr_dollars:,.0f} ({sr_rows} rows)")
print("These are 0139SR + 0140SR — only 2 distinct lots. Meaning unknown.")
print("v2.1 isolates them as inferred-unknown; not in lot-level cost.")
print("Source-owner question open: what does 'SR' mean? (Spec Reserve? Show home?)")
```

---

## 8. Per-lot lifecycle stage + ClickUp + GL triangle for an active Salem Fields lot

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
salem = next(p for p in d['projects'] if p['canonical_project'] == 'Salem Fields')
# Find first ACTIVE lot with all three signals
for ph in salem['phases']:
    for lot in ph['lots']:
        if (lot.get('lot_status_inventory') == 'ACTIVE' and
            lot.get('in_clickup_lottagged') and
            lot.get('vf_actual_cost_3tuple_usd', 0) > 0):
            print(f"Salem Fields {ph['canonical_phase']} Lot {lot['canonical_lot_number']}:")
            print(f"  Stage: {lot.get('current_stage')} (completion {lot.get('completion_pct')})")
            print(f"  ClickUp status: {lot.get('clickup_status')}")
            print(f"  Inventory status: {lot.get('lot_status_inventory')}")
            print(f"  VF cost: ${lot.get('vf_actual_cost_3tuple_usd',0):,.0f} ({lot.get('vf_actual_cost_rows',0)} rows)")
            print(f"  Source confidence: {lot.get('source_confidence')} | VF cost confidence: {lot.get('vf_actual_cost_confidence')}")
            break
    else:
        continue
    break
```

---

## 9. Decoder rule audit (which rules are applied in v2.1?)

```python
import pandas as pd
df = pd.read_csv('data/staged/vf_lot_code_decoder_v1.csv')
print("Decoder rules in v2.1 (all confidence='inferred'):")
print(df[['vf_project_code','virtual_code','rule_quality','rows_total','rows_lot_grain_eligible','match_rate_any_pct','recommendation']].to_string(index=False))
```

---

## 10. Open source-owner questions (gates on confidence promotion)

```python
import json
d = json.load(open('output/operating_state_v2_1_bcpd.json'))
print(f"v2.1 source-owner questions still open ({len(d['source_owner_questions_open'])}):")
for i, q in enumerate(d['source_owner_questions_open'], 1):
    print(f"  {i}. {q}")
print("\nUntil each is resolved, the corresponding rule stays `inferred` in v2.1.")
```

---

## Appendix — query patterns (v2.1 specific)

- **Always** read `vf_actual_cost_3tuple_usd` for per-lot VF cost. Do not re-derive at the 2-tuple grain.
- **Always** add `vf_unattributed_shell_dollars` as a separate line item when reporting per-phase or per-project cost.
- **Never** roll `commercial_parcels_non_lot` dollars into residential lot totals.
- **Never** report SctLot dollars under Scarlet Ridge in v2.1 — they live under 'Scattered Lots'.
- **Always** disclose `vf_actual_cost_confidence` ("inferred (v1 decoder; not source-owner-validated)") when citing decoder-derived numbers.
- **Cite** the v2.1 schema version (`operating_state_v2_1_bcpd`) when answering, not v2.0.
