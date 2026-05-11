"""Forensic audit — independently reconstruct expected, actual, variance, composition."""
import pandas as pd
import numpy as np
import json
import re
from pathlib import Path

pd.options.display.float_format = lambda x: f'{x:,.2f}'

# Load outputs
ls = pd.read_csv('output/lot_state.csv', low_memory=False)
ps = pd.read_csv('output/phase_state.csv')

# Load raw sources
lot_data = pd.read_csv('Collateral Dec2025 01 Claude.xlsx - Lot Data.csv', dtype=str)
status_raw = pd.read_csv('Collateral Dec2025 01 Claude.xlsx - 2025Status.csv',
                         skiprows=2, dtype=str)
coll_raw = pd.read_csv('Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv',
                       header=8, dtype=str)

# Money parser
def pm(v):
    if pd.isna(v): return 0.0
    s = str(v).strip().replace('$','').replace(',','').replace('(','-').replace(')','').strip()
    if s in ('','-','—','#DIV/0!','#ERROR!'): return 0.0
    try: return float(s)
    except: return 0.0

def strip_s(v):
    return '' if pd.isna(v) else str(v).strip()

print("=" * 90)
print("SECTION 1 — EXPECTED COSTS (allocation sheet reconstruction)")
print("=" * 90)

def reconstruct_allocation(path, project_name):
    """Recompute expected totals per phase from the Summary-per-lot section."""
    raw = pd.read_csv(path, header=None, dtype=str)
    # Find "Budgeting" stop row
    stop = len(raw)
    for i in range(len(raw)):
        for c in range(5):
            v = raw.iloc[i,c]
            if pd.notna(v) and str(v).strip() == 'Budgeting':
                stop = i; break
        if stop < len(raw): break
    rows = []
    for i in range(stop):
        r = raw.iloc[i]
        ph = strip_s(r.get(5)); pt = strip_s(r.get(6)); lc = strip_s(r.get(7))
        if not ph or not lc: continue
        try: lc_n = int(float(lc))
        except: continue
        if lc_n <= 0: continue
        rows.append(dict(
            project_name=project_name, phase=ph, prod=pt, lots=lc_n,
            direct=abs(pm(r.get(14))), indirect=abs(pm(r.get(16))),
            total=abs(pm(r.get(17))),
        ))
    return pd.DataFrame(rows)

pf_alloc = reconstruct_allocation('Parkway Allocation 2025.10.xlsx - PF.csv', 'Parkway Fields')
lh_alloc = reconstruct_allocation('LH Allocation 2025.10.xlsx - LH.csv', 'Lomond Heights')

print(f"\nPF allocation rows parsed: {len(pf_alloc)}  (sum lots: {pf_alloc['lots'].sum()})")
print(pf_alloc.groupby('phase').agg(lots=('lots','sum'),
    direct=('direct', lambda s: (s * pf_alloc.loc[s.index,'lots']).sum()),
    indirect=('indirect', lambda s: (s * pf_alloc.loc[s.index,'lots']).sum()),
    total=('total', lambda s: (s * pf_alloc.loc[s.index,'lots']).sum())))

print(f"\nLH allocation rows parsed: {len(lh_alloc)}  (sum lots: {lh_alloc['lots'].sum()})")
lh_summary = lh_alloc.assign(
    direct_t=lh_alloc['direct']*lh_alloc['lots'],
    indirect_t=lh_alloc['indirect']*lh_alloc['lots'],
    total_t=lh_alloc['total']*lh_alloc['lots'],
).groupby('phase').agg(lots=('lots','sum'),
    direct=('direct_t','sum'), indirect=('indirect_t','sum'), total=('total_t','sum'))
print(lh_summary.to_string())
print()
print("→ LH allocation sheet has ZERO indirects and ZERO totals — unusable for FULL fidelity")
print()

# Compare pipeline expected vs reconstructed for Parkway phases
print("\n--- Parkway expected costs: pipeline vs reconstruction ---")
pf_recon = pf_alloc.assign(
    direct_t=pf_alloc['direct']*pf_alloc['lots'],
    indirect_t=pf_alloc['indirect']*pf_alloc['lots'],
    total_t=pf_alloc['total']*pf_alloc['lots'],
).groupby('phase').agg(lots=('lots','sum'),
    direct=('direct_t','sum'), indirect=('indirect_t','sum'), total=('total_t','sum')).reset_index()

for _, r in pf_recon.iterrows():
    match = ps[(ps['project_name']=='Parkway Fields') & (ps['phase_name'].str.strip()==r['phase'])]
    if match.empty:
        print(f"  {r['phase']}: NO MATCH IN phase_state")
        continue
    m = match.iloc[0]
    d_pipe = m['expected_direct_cost_total'] or 0
    i_pipe = m['expected_indirect_cost_total'] or 0
    t_pipe = m['expected_total_cost'] or 0
    dd = (d_pipe - r['direct']); di = (i_pipe - r['indirect']); dt = (t_pipe - r['total'])
    flag = "OK" if abs(dt) < 1 else "MISMATCH"
    print(f"  PF::{r['phase']:<4s}  lots={r['lots']:>3d} pipe_lots={m['lot_count_total']:>3d}  "
          f"direct Δ={dd:>+12,.0f}  indirect Δ={di:>+10,.0f}  total Δ={dt:>+12,.0f}  [{flag}]")

print()
print("=" * 90)
print("SECTION 2 — ACTUAL COSTS (lot_state roll-up vs 2025Status direct read)")
print("=" * 90)

# Rebuild status cost data
main = ['Project','Phase','Lot','Product Type','Status','Vert Sold','Collateral Bucket',
        'Permits and Fees','Direct Construction - Lot','Direct Construction',
        'Vertical Costs','Shared Cost Alloc.','Lot Cost']
status = status_raw[[c for c in main if c in status_raw.columns]].copy()
status = status.dropna(subset=['Project','Phase','Lot'])
for c in ['Project','Phase','Lot']: status[c] = status[c].map(strip_s)
for c in ['Permits and Fees','Direct Construction - Lot','Direct Construction',
          'Vertical Costs','Shared Cost Alloc.','Lot Cost']:
    status[c] = status[c].map(pm)

status['cost_pipeline_def'] = (status['Permits and Fees'] + status['Direct Construction - Lot']
                                + status['Direct Construction'] + status['Shared Cost Alloc.'])
status['cost_incl_vertical'] = status['cost_pipeline_def'] + status['Vertical Costs']
status['cost_incl_all'] = status['cost_incl_vertical'] + status['Lot Cost']

# Dedupe same as pipeline
status = status.drop_duplicates(subset=['Project','Phase','Lot'], keep='first')

# Phase totals (pipeline definition vs including Vertical Costs vs including Lot Cost)
status_phase = status.groupby(['Project','Phase']).agg(
    n=('Lot','count'),
    cost_pipeline=('cost_pipeline_def','sum'),
    cost_incl_vert=('cost_incl_vertical','sum'),
    cost_incl_all=('cost_incl_all','sum'),
    vert_costs=('Vertical Costs','sum'),
    lot_cost=('Lot Cost','sum'),
).reset_index()

# Compare to phase_state actual_cost_total
print("\n--- Phase actuals: pipeline vs raw sum (includes vertical/lot cost?) ---")
print("A phase with Vertical Costs > 0 may be under-reported if those costs are excluded.\n")
ps_cmp = ps.merge(status_phase, left_on=['project_name','phase_name'],
                  right_on=['Project','Phase'], how='left')
ps_cmp['delta_pipeline'] = ps_cmp['actual_cost_total'] - ps_cmp['cost_pipeline']
ps_cmp['excluded_vert'] = ps_cmp['vert_costs']
ps_cmp['excluded_lot'] = ps_cmp['lot_cost']

mis = ps_cmp[ps_cmp['delta_pipeline'].abs() > 1]
print(f"Phases where actual_cost_total != sum of 4-component cost from 2025Status: {len(mis)}")
if len(mis):
    print(mis[['canonical_phase_id','actual_cost_total','cost_pipeline','delta_pipeline']].head(10).to_string(index=False))

vert_excluded = ps_cmp[ps_cmp['excluded_vert'] > 0][['canonical_phase_id','actual_cost_total','excluded_vert','excluded_lot']]
print(f"\nPhases with Vertical Costs in 2025Status NOT counted in actual_cost_total: {len(vert_excluded)}")
if len(vert_excluded):
    print(vert_excluded.sort_values('excluded_vert', ascending=False).head(15).to_string(index=False))
print(f"\nTotal 'Vertical Costs' across all phases EXCLUDED from actuals: ${ps_cmp['excluded_vert'].sum():,.0f}")
print(f"Total 'Lot Cost' across all phases EXCLUDED from actuals: ${ps_cmp['excluded_lot'].sum():,.0f}")

print()
print("=" * 90)
print("SECTION 3 — VARIANCE RECOMPUTE")
print("=" * 90)

comp = ps.dropna(subset=['expected_total_cost']).copy()
comp['var_recon'] = comp['actual_cost_total'] - comp['expected_total_cost']
comp['delta_var'] = comp['var_recon'] - comp['variance_total']
bad = comp[comp['delta_var'].abs() > 0.01]
print(f"\nVariance_total recompute mismatches: {len(bad)} of {len(comp)}")
if len(bad):
    print(bad[['canonical_phase_id','actual_cost_total','expected_total_cost','variance_total','var_recon','delta_var']].to_string(index=False))
print()

# Variance pct
comp['varpct_recon'] = comp['var_recon'] / comp['expected_total_cost']
bad2 = comp[(comp['expected_total_cost'] > 0) & ((comp['varpct_recon'] - comp['variance_pct']).abs() > 1e-6)]
print(f"Variance_pct recompute mismatches: {len(bad2)}")

print()
print("=" * 90)
print("SECTION 4 — COMPOSITION (lot counts)")
print("=" * 90)

# Independently count lots per phase from lot_state
lot_phase = ls.groupby(['project_name','phase_name']).size().reset_index(name='n_lots')
ps_cmp2 = ps.merge(lot_phase, on=['project_name','phase_name'], how='left')
ps_cmp2['delta_lots'] = ps_cmp2['lot_count_total'] - ps_cmp2['n_lots']
miscount = ps_cmp2[ps_cmp2['delta_lots'] != 0]
print(f"\nLot count mismatches phase_state vs lot_state roll-up: {len(miscount)}")
if len(miscount):
    print(miscount[['canonical_phase_id','lot_count_total','n_lots','delta_lots']].to_string(index=False))

# Compare phase_state allocation lot_count vs PhaseState lot_count
print("\n--- FULL-fidelity expected lot_count vs PhaseState lot_count_total ---")
for _, r in pf_recon.iterrows():
    match = ps[(ps['project_name']=='Parkway Fields') & (ps['phase_name'].str.strip()==r['phase'])]
    if match.empty: continue
    m = match.iloc[0]
    flag = "OK" if r['lots']==m['lot_count_total'] else "DENOM MISMATCH"
    print(f"  PF::{r['phase']:<4s}  allocation_lot_count={r['lots']:>3d}  phase_state_lot_count={m['lot_count_total']:>3d}  [{flag}]")

print()
print("=" * 90)
print("SECTION 5 — LIFECYCLE WATERFALL SPOT CHECK")
print("=" * 90)

# Sample some lots across states
ls_sample = ls.groupby('lot_state').head(2)[['canonical_lot_id','lot_state','horiz_purchase_date','horiz_start_date','horiz_record_date','vert_purchase_date','vert_start_date','vert_co_date','vert_sale_date','vert_close_date']]
print(ls_sample.to_string(index=False))

# Verify waterfall holds
asof = pd.Timestamp('2025-12-31')
waterfall = [
    ('vert_close_date','CLOSED'),
    ('vert_sale_date','SOLD_NOT_CLOSED'),
    ('vert_co_date','VERTICAL_COMPLETE'),
    ('vert_start_date','VERTICAL_IN_PROGRESS'),
    ('vert_purchase_date','VERTICAL_PURCHASED'),
    ('horiz_record_date','FINISHED_LOT'),
    ('horiz_start_date','HORIZONTAL_IN_PROGRESS'),
    ('horiz_purchase_date','LAND_OWNED'),
]
def recompute_state(r):
    for f,s in waterfall:
        d = r.get(f)
        if pd.notna(d) and pd.Timestamp(d) <= asof: return s
    return 'PROSPECT'
ls2 = ls.copy()
for c,_ in waterfall: ls2[c] = pd.to_datetime(ls2[c], errors='coerce')
ls2['state_recon'] = ls2.apply(recompute_state, axis=1)
mism = ls2[ls2['state_recon'] != ls2['lot_state']]
print(f"\nLot state waterfall mismatches: {len(mism)} of {len(ls2)}")
if len(mism):
    print(mism[['canonical_lot_id','lot_state','state_recon']].head(10).to_string(index=False))

print()
print("=" * 90)
print("SECTION 6 — ID HYGIENE / LEADING-TRAILING SPACES")
print("=" * 90)

bad_phase = ps[ps['canonical_phase_id'].str.strip() != ps['canonical_phase_id']]
print(f"\nPhase IDs with leading/trailing whitespace: {len(bad_phase)}")
if len(bad_phase):
    print(bad_phase[['canonical_phase_id','project_name','phase_name','lot_count_total']].to_string(index=False))

bad_lot = ls[ls['canonical_lot_id'].str.strip() != ls['canonical_lot_id']]
print(f"\nLot IDs with leading/trailing whitespace: {len(bad_lot)}")
if len(bad_lot):
    print(bad_lot[['canonical_lot_id','project_name','phase_name','lot_number']].head(10).to_string(index=False))
