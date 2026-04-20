"""Post-patch forensic audit."""
import pandas as pd

def pm(v):
    if pd.isna(v): return 0.0
    s = str(v).strip().replace('$','').replace(',','').replace('(','-').replace(')','').strip()
    if s in ('','-','—','#DIV/0!','#ERROR!'): return 0.0
    try: return float(s)
    except: return 0.0

def strip_s(v):
    return '' if pd.isna(v) else str(v).strip()

ls = pd.read_csv('output/lot_state.csv', low_memory=False)
ps = pd.read_csv('output/phase_state.csv')
status_raw = pd.read_csv('Collateral Dec2025 01 Claude.xlsx - 2025Status.csv', skiprows=2, dtype=str)

print("="*90)
print("1) EXPECTED COST — arithmetic + fallback")
print("="*90)

def reconstruct(path, project):
    raw = pd.read_csv(path, header=None, dtype=str)
    stop = len(raw)
    for i in range(len(raw)):
        for c in range(5):
            v = raw.iloc[i,c]
            if pd.notna(v) and str(v).strip() == 'Budgeting':
                stop = i; break
        if stop < len(raw): break
    rows=[]
    for i in range(stop):
        r = raw.iloc[i]
        ph = strip_s(r.get(5)); lc = strip_s(r.get(7))
        if not ph or not lc: continue
        try: lcn = int(float(lc))
        except: continue
        if lcn <= 0: continue
        land = abs(pm(r.get(13))); direct = abs(pm(r.get(14)))
        water = abs(pm(r.get(15))); indirect = abs(pm(r.get(16)))
        total = abs(pm(r.get(17)))
        # Same fallback the pipeline uses
        if total == 0:
            total = land + direct + water + indirect
        rows.append(dict(project=project, phase=ph, lots=lcn,
            land=land, direct=direct, water=water, indirect=indirect, total=total))
    return pd.DataFrame(rows)

pf = reconstruct('Parkway Allocation 2025.10.xlsx - PF.csv', 'Parkway Fields')
lh = reconstruct('LH Allocation 2025.10.xlsx - LH.csv', 'Lomond Heights')

def phase_agg(df):
    out = df.assign(
        direct_t=df['direct']*df['lots'],
        indirect_t=df['indirect']*df['lots'],
        total_t=df['total']*df['lots'],
    ).groupby(['project','phase']).agg(
        alloc_lots=('lots','sum'),
        alloc_direct=('direct_t','sum'),
        alloc_indirect=('indirect_t','sum'),
        alloc_total=('total_t','sum'),
    ).reset_index()
    return out

alloc = pd.concat([phase_agg(pf), phase_agg(lh)], ignore_index=True)

# Compare to phase_state
mrg = ps.merge(alloc, left_on=['project_name','phase_name'], right_on=['project','phase'], how='inner')
mrg['d_direct'] = mrg['expected_direct_cost_total'].fillna(0) - mrg['alloc_direct']
mrg['d_indirect'] = mrg['expected_indirect_cost_total'].fillna(0) - mrg['alloc_indirect']
mrg['d_total'] = mrg['expected_total_cost'].fillna(0) - mrg['alloc_total']
mrg['d_lots'] = mrg['lot_count_total'] - mrg['alloc_lots']
print("\nExpected cost vs reconstruction (allocation-sheet phases):")
print(mrg[['canonical_phase_id','alloc_lots','lot_count_total','d_lots',
           'alloc_total','expected_total_cost','d_total']].to_string(index=False))

arith_bad = mrg[mrg['d_total'].abs() > 1]
print(f"\nArithmetic mismatches (>$1): {len(arith_bad)} of {len(mrg)}")

# Denominator/lot-count mismatch
denom_bad = mrg[mrg['d_lots'] != 0]
print(f"Lot-count mismatch (allocation vs phase_state): {len(denom_bad)}")
if len(denom_bad):
    print(denom_bad[['canonical_phase_id','alloc_lots','lot_count_total','d_lots']].to_string(index=False))

print("\nCoverage:")
print(f"  Total phases: {len(ps)}")
print(f"  Phases with expected_total_cost: {ps['expected_total_cost'].notna().sum()}")
print(f"  cost_data_completeness distribution:")
print(ps['cost_data_completeness'].fillna('NONE').value_counts().to_string())

print()
print("="*90)
print("2) ACTUAL COST — horizontal-only semantics")
print("="*90)

main = ['Project','Phase','Lot','Permits and Fees','Direct Construction - Lot',
        'Direct Construction','Vertical Costs','Shared Cost Alloc.','Lot Cost']
status = status_raw[[c for c in main if c in status_raw.columns]].dropna(subset=['Project','Phase','Lot']).copy()
for c in ['Project','Phase','Lot']: status[c] = status[c].map(strip_s)
for c in ['Permits and Fees','Direct Construction - Lot','Direct Construction','Vertical Costs','Shared Cost Alloc.','Lot Cost']:
    status[c] = status[c].map(pm)
status = status.drop_duplicates(subset=['Project','Phase','Lot'], keep='first')

status['horiz_only'] = status['Permits and Fees'] + status['Direct Construction - Lot'] + status['Shared Cost Alloc.']
status['with_direct_constr'] = status['horiz_only'] + status['Direct Construction']
status['with_vertical'] = status['with_direct_constr'] + status['Vertical Costs']

sph = status.groupby(['Project','Phase']).agg(
    n=('Lot','count'),
    horiz_only=('horiz_only','sum'),
    direct_constr=('Direct Construction','sum'),
    vertical=('Vertical Costs','sum'),
    lot_cost=('Lot Cost','sum'),
).reset_index()

cmp = ps.merge(sph, left_on=['project_name','phase_name'], right_on=['Project','Phase'], how='left')
cmp['d_actual'] = cmp['actual_cost_total'] - cmp['horiz_only'].fillna(0)
bad_act = cmp[cmp['d_actual'].abs() > 1]
print(f"\nactual_cost_total vs independent horizontal-only recompute: {len(bad_act)} mismatches")
if len(bad_act):
    print(bad_act[['canonical_phase_id','actual_cost_total','horiz_only','d_actual']].head(10).to_string(index=False))

# Confirm Direct Construction and Vertical fully excluded
print(f"\n'Direct Construction' still in actuals? total column-sum = ${cmp['direct_constr'].sum():,.0f} (now EXCLUDED from actual_cost_total)")
print(f"'Vertical Costs' still in actuals?  total column-sum = ${cmp['vertical'].sum():,.0f} (now EXCLUDED from actual_cost_total)")

# Verify lot-level too
ls_sum = ls['cost_to_date'].sum()
ps_sum = ps['actual_cost_total'].sum()
print(f"\nΣ lot_state.cost_to_date = ${ls_sum:,.0f}")
print(f"Σ phase_state.actual_cost_total = ${ps_sum:,.0f}")
print(f"Δ = ${ls_sum - ps_sum:,.2f}  (should be 0)")

print()
print("="*90)
print("3) VARIANCE — meaningfulness + arithmetic")
print("="*90)

vm = ps[ps['variance_meaningful']==True]
nvm = ps[ps['variance_meaningful']==False]
print(f"\nvariance_meaningful=True: {len(vm)}  |  False: {len(nvm)}")

# Gating: meaningful rule must be actual>0 AND expected not null
rule_pass = ((ps['actual_cost_total']>0) & ps['expected_total_cost'].notna())
gate_bad = ps[rule_pass != ps['variance_meaningful']]
print(f"Rows where variance_meaningful != (actual>0 & expected notnull): {len(gate_bad)} (should be 0)")

# Variance null where not meaningful
leak = nvm[nvm[['variance_total','variance_per_lot','variance_pct']].notna().any(axis=1)]
print(f"Variance leakage (variance populated but meaningful=False): {len(leak)} (should be 0)")

# Arithmetic for meaningful rows
vm2 = vm.copy()
vm2['var_t_rec'] = vm2['actual_cost_total'] - vm2['expected_total_cost']
vm2['var_pl_rec'] = vm2['actual_cost_per_lot'] - vm2['expected_total_cost_per_lot']
vm2['var_pct_rec'] = vm2['var_t_rec'] / vm2['expected_total_cost']
arith_problems = vm2[
    ((vm2['var_t_rec'] - vm2['variance_total']).abs() > 0.01) |
    ((vm2['var_pl_rec'] - vm2['variance_per_lot']).abs() > 0.01) |
    ((vm2['var_pct_rec'] - vm2['variance_pct']).abs() > 1e-6)
]
print(f"Arithmetic mismatches in meaningful variance: {len(arith_problems)} (should be 0)")

# Extreme artifacts
print("\nAll meaningful phases (sorted by |variance_pct|):")
print(vm[['canonical_phase_id','lot_count_total','expected_total_cost','actual_cost_total',
         'variance_total','variance_pct','cost_data_completeness']]
      .sort_values('variance_pct', key=abs, ascending=False).to_string(index=False))

print()
print("="*90)
print("4) COMPOSITION — lot counts")
print("="*90)

c = ls.groupby(['project_name','phase_name']).size().reset_index(name='n')
m = ps.merge(c, on=['project_name','phase_name'], how='left')
m['d'] = m['lot_count_total'] - m['n']
bad = m[m['d'] != 0]
print(f"\nphase_state lot_count_total vs lot_state row count mismatches: {len(bad)} (should be 0)")

# product mix sanity — sum to 1.0
import json
bad_mix = 0
for i, r in ps.iterrows():
    try:
        mix = json.loads(r['product_mix_pct'])
        if abs(sum(mix.values()) - 1.0) > 0.02: bad_mix += 1
    except: bad_mix += 1
print(f"product_mix_pct rows not summing to 1.0 (±2%): {bad_mix}")

print()
print("="*90)
print("5) LIFECYCLE SPOT CHECK")
print("="*90)

asof = pd.Timestamp('2025-12-31')
waterfall = [
    ('vert_close_date','CLOSED'),('vert_sale_date','SOLD_NOT_CLOSED'),
    ('vert_co_date','VERTICAL_COMPLETE'),('vert_start_date','VERTICAL_IN_PROGRESS'),
    ('vert_purchase_date','VERTICAL_PURCHASED'),('horiz_record_date','FINISHED_LOT'),
    ('horiz_start_date','HORIZONTAL_IN_PROGRESS'),('horiz_purchase_date','LAND_OWNED'),
]
ls2 = ls.copy()
for c,_ in waterfall: ls2[c] = pd.to_datetime(ls2[c], errors='coerce')
def rec(r):
    for f,s in waterfall:
        d = r.get(f)
        if pd.notna(d) and d <= asof: return s
    return 'PROSPECT'
ls2['rec'] = ls2.apply(rec, axis=1)
mm = ls2[ls2['rec'] != ls2['lot_state']]
print(f"\nLot waterfall mismatches: {len(mm)} of {len(ls2)} (should be 0)")

# Phase waterfall spot check — pick a few phases with diverse lots
print("\nPhase waterfall sanity for 3 phases:")
for pid in ['Harmony::A10','Parkway Fields::G1','Arrowhead Springs::123']:
    sub = ls[ls['phase_id']==pid]
    states = set(sub['lot_state'])
    expected = None
    if states == {'CLOSED'}: expected='CLOSED_OUT'
    elif states & {'SOLD_NOT_CLOSED','CLOSED'}: expected='SELLING'
    elif states & {'VERTICAL_PURCHASED','VERTICAL_IN_PROGRESS','VERTICAL_COMPLETE'}: expected='VERTICAL_ACTIVE'
    elif states & {'HORIZONTAL_IN_PROGRESS','FINISHED_LOT'}: expected='HORIZONTAL_ACTIVE'
    elif 'LAND_OWNED' in states: expected='LAND_ACQUIRED'
    else: expected='PLANNED'
    actual = ps.loc[ps['canonical_phase_id']==pid,'phase_state'].iloc[0] if (ps['canonical_phase_id']==pid).any() else None
    print(f"  {pid:<35s} states={sorted(states)}  expected={expected}  actual={actual}  {'OK' if expected==actual else 'MISMATCH'}")

print()
print("="*90)
print("6) REMAINING ISSUES")
print("="*90)

# Phases with meaningful variance >3x (over or under 200%)
big = vm[vm['variance_pct'].abs() > 2][['canonical_phase_id','lot_count_total','expected_total_cost','actual_cost_total','variance_pct','cost_data_completeness']]
print(f"\nPhases with |variance_pct|>200% (still suspect): {len(big)}")
if len(big):
    print(big.to_string(index=False))

# LH denominator problem
print("\nAllocation lot-count vs phase_state lot_count (denominator check):")
mrg_show = mrg[mrg['d_lots']!=0][['canonical_phase_id','alloc_lots','lot_count_total','d_lots','expected_total_cost','expected_total_cost_per_lot']]
print(mrg_show.to_string(index=False))

# Collateral report phases that might be missing
print("\nProjects by phase count where expected_total_cost is still NULL:")
miss = ps[ps['expected_total_cost'].isna()].groupby('project_name').size()
print(miss.to_string())

print()
print("="*90)
print("7) COVERAGE SUMMARY")
print("="*90)
n = len(ps)
print(f"Total phases: {n}")
print(f"  with expected_total_cost: {ps['expected_total_cost'].notna().sum()} ({ps['expected_total_cost'].notna().mean()*100:.1f}%)")
print(f"  with variance_meaningful=True: {(ps['variance_meaningful']==True).sum()} ({(ps['variance_meaningful']==True).mean()*100:.1f}%)")
print(f"  cost_data_completeness=FULL: {(ps['cost_data_completeness']=='FULL').sum()} ({(ps['cost_data_completeness']=='FULL').mean()*100:.1f}%)")
print(f"  cost_data_completeness=PARTIAL: {(ps['cost_data_completeness']=='PARTIAL').sum()}")
print(f"  cost_data_completeness=NONE: {ps['cost_data_completeness'].isna().sum()}")
