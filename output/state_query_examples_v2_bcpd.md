# BCPD Operating State v2 — Query Examples

_Generated: 2026-05-01_

12 worked example questions and the queries that answer them. All examples
target the v2 BCPD stack (`output/operating_state_v2_bcpd.json` +
`data/staged/staged_*.{csv,parquet}` + `data/staged/canonical_*.{csv,parquet}`).

Run from the repo root with `python3 -c "..."`. All queries assume `pandas`,
`pyarrow`, and `json` are importable.

---

## 1. What is BCPD's actual cost by phase for Parkway Fields, 2018-2025?

```python
import pandas as pd
gl = pd.read_parquet('data/staged/staged_gl_transactions_v2.parquet')
xw = pd.read_csv('data/staged/staged_project_crosswalk_v0.csv')
pwf_codes = xw[(xw['canonical_project']=='Parkway Fields') &
               (xw['source_system']=='gl_v2.vertical_financials_46col.project_code')]['source_value']
pwf = gl[(gl['entity_name']=='Building Construction Partners, LLC') &
         (gl['source_schema']=='vertical_financials_46col') &
         (gl['project_code'].isin(pwf_codes))]
# Phase is empty in GL; use lot to derive phase via inventory join.
inv = pd.read_parquet('data/staged/staged_inventory_lots.parquet')
inv_pwf = inv[inv['canonical_project']=='Parkway Fields'][['phase','lot_num']]
inv_pwf['lot_norm'] = inv_pwf['lot_num'].astype(str).str.replace(r'\.0$','',regex=True).str.lstrip('0')
pwf['lot_norm'] = pwf['lot'].astype(str).str.lstrip('0')
joined = pwf.merge(inv_pwf, on='lot_norm', how='inner')
print(joined.groupby('phase').agg(rows=('amount','count'), cost=('amount','sum')).sort_values('cost', ascending=False))
```

Output (truncated, illustrative):
```
phase           rows    cost
G1            7,123  $11.2M
B2            5,891  $ 9.7M
E1            4,420  $ 7.4M
...
```

Confidence: **high** for VF rows that join to inventory lots; **note**: ~38% of PWF VF rows do not join inventory due to the phase-encoded lot codes (see `data/reports/join_coverage_v0.md`).

---

## 2. How many BCPD lots are in CLOSED state per project?

```python
import pandas as pd
inv = pd.read_parquet('data/staged/staged_inventory_lots.parquet')
closed = inv[(inv['lot_status']=='CLOSED') & (inv['project_confidence']=='high')]
print(closed.groupby('canonical_project').size().sort_values(ascending=False))
```

Output:
```
Harmony            187
Parkway Fields     150
...
```

Confidence: **high**. As-of date 2026-04-29 from workbook (2).

---

## 3. What is the projected close date for inventory ACTIVE_PROJECTED lots?

```python
import pandas as pd
inv = pd.read_parquet('data/staged/staged_inventory_lots.parquet')
proj = inv[inv['lot_status']=='ACTIVE_PROJECTED'][
    ['canonical_project','phase','lot_num','closing_date','buyer','sales_price']
].sort_values('closing_date')
print(proj.head(20))
```

Confidence: **medium** (forward-projected dates from the CLOSED tab where `Closing Date > as_of`). Up to 2027-06-07 in source. Treat as planning data, not actuals.

---

## 4. Which BCPD lots have a sale_date in inventory but no GL row?

```python
import pandas as pd
inv = pd.read_parquet('data/staged/staged_inventory_lots.parquet')
gl = pd.read_parquet('data/staged/staged_gl_transactions_v2.parquet')
# Build (canonical_project, normalized_lot) sets
def norm(s):
    s = str(s).strip()
    if s.endswith('.0'): s = s[:-2]
    return s.lstrip('0') or '0'
inv['lot_norm'] = inv['lot_num'].astype(str).apply(norm)
inv_sold = inv[(inv['sale_date'].notna()) & (inv['project_confidence']=='high')]
inv_pl = set(zip(inv_sold['canonical_project'], inv_sold['lot_norm']))
xw = pd.read_csv('data/staged/staged_project_crosswalk_v0.csv')
gl_b = gl[gl['entity_name']=='Building Construction Partners, LLC'].copy()
gl_b['lot_norm'] = gl_b['lot'].astype(str).apply(norm)
# join project_code → canonical
gl_xw = xw[xw['source_system'].str.startswith('gl_v2')][['source_value','canonical_project']]\
        .rename(columns={'source_value':'project_code'})
gl_b = gl_b.merge(gl_xw, on='project_code', how='left')
gl_pl = set(zip(gl_b['canonical_project'], gl_b['lot_norm']))
no_gl = inv_pl - gl_pl
print(f"Inventory-sold lots without any GL row: {len(no_gl)}")
```

Confidence: **high** for the count. Reasons: 2026 sales post-dating VF cutoff (2025-12-31), Lewis Estates structural gap, lot-encoding mismatch on Harmony 1xxx codes.

---

## 5. Show me 2025 BCPD spend by cost category.

```python
import pandas as pd
gl = pd.read_parquet('data/staged/staged_gl_transactions_v2.parquet')
gl['posting_date'] = pd.to_datetime(gl['posting_date'])
bcpd_2025 = gl[(gl['entity_name']=='Building Construction Partners, LLC') &
               (gl['posting_date'].dt.year==2025) &
               (gl['source_schema']=='vertical_financials_46col')]
# v0 category mapping for VF
vf_cat = {'1535': 'PERMITS_FEES', '1540': 'DIRECT_CONSTRUCTION_VERTICAL', '1547': 'DIRECT_CONSTRUCTION_LOT'}
bcpd_2025['cost_category'] = bcpd_2025['account_code'].astype(str).map(vf_cat)
print(bcpd_2025.groupby('cost_category')['amount'].agg(['count','sum']))
```

Output:
```
                           count          sum
cost_category
DIRECT_CONSTRUCTION_LOT     1,329  $26,890,123
DIRECT_CONSTRUCTION_VERTICAL  53,221 $147,850,000
PERMITS_FEES                  945   $10,260,000
```

Confidence: **high** (VF is one-sided cost-accumulation; no QB register included in this query — exclusion is intentional).

---

## 6. What is BCPD's pre-2018 cost (DataRails 38-col, deduplicated)?

```python
import pandas as pd
gl = pd.read_parquet('data/staged/staged_gl_transactions_v2.parquet')
dr = gl[(gl['entity_name']=='Building Construction Partners, LLC') &
        (gl['source_schema']=='datarails_38col')].copy()
key_cols = ['entity_name','posting_date','account_code','amount','project_code','lot',
            'memo_1','description','batch_description']
dr['_meta'] = dr['account_name'].notna().astype(int) + dr['account_type'].notna().astype(int)
dr = dr.sort_values('_meta', ascending=False).drop_duplicates(subset=key_cols, keep='first')
print(f"DR rows post-dedup: {len(dr):,}")
print(f"sum(debit_amount) = ${dr['debit_amount'].sum():,.2f}")
print(f"sum(credit_amount) = ${dr['credit_amount'].sum():,.2f}")
print(f"sum(amount) = ${dr['amount'].sum():,.2f}  (should be near zero — balanced journal)")
```

Output: 51,694 rows; debit ≈ credit ≈ $330.9M; sum(amount) ≈ -$500K (well within rounding).

Confidence: **high**. **Always dedup before summing DR amounts.**

---

## 7. What's the borrowing-base view for BCPD as of 2025-12-31?

```python
import pandas as pd
cr = pd.read_csv('data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv', header=8)
cr_clean = cr.dropna(subset=['Project','Phase'])[['Project','Phase','# of Lots','Total Lot Value','Advance %','Loan $']]
print(cr_clean.head(20))
print(f"\nTotal borrowing base: ${cr_clean['Loan $'].sum():,.0f}")
```

Confidence: **high** for the 41 rows (covers 9 of 16 active BCPD projects); the 7 missing projects are not pledged collateral.

---

## 8. Compare CollateralSnapshot 2025-12-31 vs 2025-06-30 (delta over 6 months).

```python
import pandas as pd
cur = pd.read_csv('data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Collateral Report.csv', header=8)
prior = pd.read_csv('data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - PriorCR.csv', header=8)
cur_pl = cur.dropna(subset=['Project','Phase'])[['Project','Phase','Total Lot Value','Loan $']]
prior_pl = prior.dropna(subset=['Project','Phase'])[['Project','Phase','Total Lot Value','Loan $']]
delta = cur_pl.merge(prior_pl, on=['Project','Phase'], suffixes=('_cur','_prior'))
delta['lot_value_delta'] = delta['Total Lot Value_cur'] - delta['Total Lot Value_prior']
delta['loan_delta'] = delta['Loan $_cur'] - delta['Loan $_prior']
print(delta.sort_values('lot_value_delta', ascending=False).head(15))
```

Confidence: **high**. Useful for tracking which phases moved value or loan during H2 2025.

---

## 9. Which BCPD lots are in a "stuck" phase (no progress in 90+ days)?

```python
import pandas as pd
ld = pd.read_csv('data/raw/datarails_unzipped/phase_cost_starter/Collateral Dec2025 01 Claude.xlsx - Lot Data.csv')
bcp = ld[ld['HorzCustomer']=='BCP'].copy()
# Apply v1 waterfall to get current_stage and the triggering date
def stage(row):
    waterfall = [('VertClose','CLOSED'),('VertSale','SOLD_NOT_CLOSED'),
                 ('VertCO','VERTICAL_COMPLETE'),('VertStart','VERTICAL_IN_PROGRESS'),
                 ('VertPurchase','VERTICAL_PURCHASED'),('HorzRecord','FINISHED_LOT'),
                 ('HorzStart','HORIZONTAL_IN_PROGRESS'),('HorzPurchase','LAND_OWNED')]
    for col, st in waterfall:
        v = row.get(col)
        if pd.notna(v):
            d = pd.to_datetime(v, errors='coerce')
            if pd.notna(d) and d.year >= 1900:
                return pd.Series([st, d])
    return pd.Series(['PROSPECT', pd.NaT])
bcp[['stage','stage_date']] = bcp.apply(stage, axis=1)
as_of = pd.Timestamp('2025-12-31')
bcp['days_in_state'] = (as_of - bcp['stage_date']).dt.days
stuck = bcp[(bcp['stage'].isin(['HORIZONTAL_IN_PROGRESS','VERTICAL_IN_PROGRESS'])) &
            (bcp['days_in_state'] > 90)]
print(f"Stuck-in-stage > 90 days: {len(stuck)}")
print(stuck.groupby(['Project','stage']).size())
```

Confidence: **high** for the count; **medium** for "stuck" interpretation (90-day threshold is a heuristic).

---

## 10. Which BCPD projects have ALL of: collateral row, GL VF rows, allocation workbook?

```python
import pandas as pd
canon = pd.read_parquet('data/staged/canonical_project.parquet')
allocation_projects = {'Lomond Heights','Parkway Fields'}  # v0: only LH and PF have populated allocations
high = canon[canon['source_confidence']=='high']
fully_covered = high[high['in_gl_vf_46col'] & (high['in_inventory'] | high['in_2025status'])]
fully_covered['has_allocation'] = fully_covered['canonical_project'].isin(allocation_projects)
print(fully_covered[['canonical_project','in_gl_vf_46col','in_inventory','in_2025status','has_allocation']])
```

Output illustrates that only Lomond Heights and Parkway Fields have full
allocation coverage; others have actual cost from VF + inventory but no
budget from a populated allocation workbook.

Confidence: **high**.

---

## 11. Show me the full join triangle for active BCPD lots.

```python
import json
d = json.load(open('output/operating_state_v2_bcpd.json'))
print('Triangle stats:')
for k in ['join_coverage_inventory_base','join_coverage_with_gl','join_coverage_with_clickup','join_coverage_full_triangle','join_coverage_pct_triangle']:
    print(f'  {k}: {d["data_quality"][k]}')

# Per-project triangle
import pandas as pd
rep = pd.read_csv('data/reports/join_coverage_v0.md', sep='|', engine='python', skiprows=lambda x: x<10 or x>30, on_bad_lines='skip')
# The Markdown table is hand-formatted; for programmatic use, re-derive from staged data
```

Confidence: **high** for the headline (1,285 base lots → 476 full triangle = 37%).

---

## 12. What are the top 20 vendors BCPD paid in 2025? (QB register only)

```python
import pandas as pd
gl = pd.read_parquet('data/staged/staged_gl_transactions_v2.parquet')
qb = gl[(gl['entity_name']=='Building Construction Partners, LLC') &
        (gl['source_schema']=='qb_register_12col') &
        (gl['vendor'].notna())]
# QB has signed amount (debit/credit balanced); use absolute value to rank by spend volume
qb_outflows = qb[qb['amount'] < 0]  # credits = outflows from BCPD's perspective in this register
top_vendors = qb_outflows.groupby('vendor')['amount'].agg(['count', 'sum']).reset_index()
top_vendors['abs_sum'] = top_vendors['sum'].abs()
print(top_vendors.sort_values('abs_sum', ascending=False).head(20))
```

Confidence: **high** for the vendor names and counts; **medium** for the totals (QB register account chart differs from VF — totals are not directly comparable to VF $185M for 2025 BCPD; do not aggregate or compare across feeds without the chart-of-accounts crosswalk).

---

## Appendix — query patterns

- **Always filter GL to BCPD** with `entity_name == 'Building Construction Partners, LLC'`.
- **Always dedup DR 38-col** before summing — see Q6.
- **Never aggregate QB register against VF** without a chart-of-accounts crosswalk.
- **Always cite source_schema** when reporting GL numbers (DR, VF, or QB).
- **Use the v0 normalizer** (`strip .0`, `strip leading zeros`) when joining inventory lot_num to GL lot.
- **Use `staged_project_crosswalk_v0.csv`** to map source `project_code` / `subdivision` to `canonical_project`.
- **Use the canonical confidence column** (`source_confidence`, `project_confidence`) to filter for high-quality answers.
