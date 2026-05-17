Hey — wanted to send a fuller update after the Flagship call today and the latest MCP/tooling sprint.

Overall, the call was encouraging. The tool layer landed well conceptually: the accounting lead understood the value of having Claude query the BCP Dev process, check readiness, surface gaps, and reproduce the Parkway Fields workbook output. But the call also clarified that the next stage is less about “more chatbot features” and more about making this operational for their monthly/periodic accounting workflow.

Where we landed technically
We now have the BCP Dev v0.2 MCP layer working with 13 tools exposed through the existing MCP server.

The current system can:

explain the BCP Dev allocation/accounting process

explain allocation logic by event or cost type

check allocation readiness for a community/phase

surface crosswalk/source mapping gaps

detect accounting-event issues from ClickUp-style status changes

generate a Per-Lot Output spec

replicate the Parkway Fields satellite workbook output

preserve refusals/caveats for unsupported cases

The important distinction: PF satellite replication is not canonical allocation compute. It is a read-through/reformatting layer over the already-populated Parkway Fields satellite workbook CSV. That is useful and demoable, but we should not represent it as the final allocation engine.

What we learned on the call
A few things became clearer:

1. The land allocation rule is now directionally clear
The workbook uses projected-sales basis for land/indirect allocation, not pure lot-count weighting.

So the interpretation is:

lot count is still required for tie-out and per-lot denominator

projected sales price drives total projected sales

total projected sales drives sales-basis %

land/indirect pools are allocated by that sales-basis %

That is now represented in the rule layer as workbook-observed, with formal source-owner ratification still noted.

2. Some inputs are manual/sensitive by design
Projected sales/pricing cannot just be blindly pulled from MLS or inferred by the system. The accounting lead was clear that projected sales values are sensitive and should be controlled/reviewed.

Same idea with warranty: warranty should come from Corey’s budget / budgeted warranty line, not a default zero. The current refusal behavior is right, but we need to wire in the actual source.

3. Sign convention needs review
The PF satellite output shows land/direct costs with negative signs. The accounting lead seemed surprised by that and said costs should generally show as positive while revenue/credit balances may show negative. So we need to review whether:

the source workbook is using a particular sign convention,

our parser is preserving the workbook correctly,

or the displayed view should support a “finance-readable costs positive” mode.

I would not change this blindly yet, but it is an important hardening item before a broader demo.

4. QBD/New Star mappings are actively improving
He is cleaning up QuickBooks/New Star job naming with a structure like:

community

cost type

scope

That should help a lot with crosswalk confidence. The known messy areas are still Harmony and Lewis Estates / Pioneer Village / Dry Creek Lehi, but the important thing is those are source-cleanup items in flight, not permanent system failures.

5. The next product layer is reporting/review, not just Q&A
The strongest product feedback was that they want:

monthly/periodic reports

community → phase → lot cost by cost type

ability to toggle/group by lot type, sales tranche, cost type, etc.

preparer/reviewer workflow

signoff

feedback loop when outputs are wrong

eventually accounting-event alerts from ClickUp status changes

That is a meaningful scope expansion, but it is the right direction. The MCP layer is the query/control layer. The next layer is probably a review/reporting workflow.

Immediate roadmap I’m thinking
Here is how I would sequence the next work.

1. Host the MCP somewhere usable
Right now, it works locally. That is great for proving the architecture, but they need to actually use it.

We need to figure out the hosting/deployment path so the Flagship team can access the tool layer through Claude or some client without running it from my local machine.

Open items:

pick hosting target

figure out Claude web / Claude Desktop access path

deployment docs

smoke test hosted environment

give accounting lead / Christian / whoever access

This is probably the top priority.

2. Close the allocation input gaps
The tool layer is now honest about what is missing. The next step is to make those inputs available.

Key items:

ClickUp API access

pull current lot counts for Parkway Fields Remaining phases

get phase, lot number, lot type, status, QBD/customer/job fields if present

Manual land-team lot-count tieout

identify who owns the official land-side lot count

decide where that input lives

use it for the three-way tie: ClickUp count = workbook count = land/manual count

Projected sales/pricing input

decide where projected sales price should live

do not infer blindly

likely needs controlled manual/pricing input

Warranty source

find Corey’s budget/warranty line

decide whether warranty is a raw budget number or percentage

keep warranty refused/null until the source is known

QBD/New Star/phase mappings

let the accounting lead continue cleanup

then refresh crosswalks and rerun readiness

3. New Star connector investigation
This may be the biggest source-system win.

He mentioned DataRails already has a live connection into New Star using ODBC/File Sync Agent, and there are SQL queries visible in DataRails. We should inspect the 12/5 DataRails/New Star call/transcript and see if we can reuse or reproduce that path.

Open items:

review the DataRails/New Star integration transcript

inspect the DataRails SQL queries

identify New Star tables/fields

determine if we can use ODBC directly, export through DataRails, or request a cloud replica

identify first minimum pull target

4. Define the first report/dashboard interaction
The accounting lead specifically wants a reviewable view, not just chat output.

First report/dashboard target could be:

community

phase

lot type

lots

cost type

land

direct

indirect

water

warranty

total cost

sales

margin

margin %

With toggles/grouping by:

community

phase

lot type

sales tranche

cost type

source/caveat status

This does not necessarily need to be a full app immediately. It could start as an HTML report, CSV export, or generated table from the MCP tools. But it needs to be reviewable.

5. Define the feedback/review workflow
We should not let users directly edit the tools or rules. But we do need a feedback loop.

Potential flow:

user flags issue or requested change

feedback is stored

Bedrock/system owner reviews

source owner confirms if needed

rule/crosswalk/tool is updated intentionally

tests run

MCP redeployed

Eventually this becomes a monthly/periodic control workflow:

reports generated

preparer assigned

reviewer assigned

signoff captured

feedback/corrections tracked

That seems very aligned with what they actually need on the accounting side.

Things we may need to change or add
A few directional changes I’m thinking:

A. Add display modes for financial signs
Right now PF replication preserves workbook signs. That is safest from a “do not transform source” perspective. But it may be confusing to business users.

We may need something like:

workbook_sign

finance_readable_cost_positive

Not urgent, but worth discussing.

B. Add a reporting tool family
Current tools are good for question answering and readiness checks. The next logical family is reporting.

Something like:

generate_allocation_review_report

generate_monthly_cost_by_phase_report

generate_margin_review_table

export_report_csv

create_review_packet

This could be where the dashboard/report output starts.

C. Add feedback capture
Maybe not direct user edits, but something like:

submit_tool_feedback

list_open_feedback

summarize_feedback_for_tool_owner

Could be simple at first: write to a JSON/CSV/GitHub issue style queue.

D. Add ownership metadata
As these tools get used, we may want to know:

who owns the tool

who owns the source data

who can approve rule changes

who should review feedback

That matters because the accounting lead specifically raised the risk of a bunch of people suggesting changes that could break things.

Tool coverage we should review together
We should probably sync on the current tool map and decide whether the coverage makes sense or whether we should abstract it down before broader use.

Current BCP Dev tool family:

query_bcp_dev_process
General process Q&A over BCP Dev accounting/process rules.

explain_allocation_logic
Explains allocation method by cost type or event.

validate_crosswalk_readiness
Shows source mapping/crosswalk issues and unresolved mappings.

check_allocation_readiness
Tells whether a community/phase is actually ready to run allocation, with blockers.

detect_accounting_events
Given status changes, identifies accounting events and missing required fields.

generate_per_lot_output_spec
Shows the intended per-lot output shape and which fields are computable/refused/blocked.

replicate_pf_satellite_per_lot_output
Reads through the populated Parkway Fields satellite workbook output. Explicitly not authoritative compute.

Existing BCPD v2.1 tools still exist too:

generate_project_brief

review_margin_report_readiness

find_false_precision_risks

summarize_change_impact

prepare_finance_land_review

draft_owner_update

I think we should talk through:

which tools are internal/dev-facing vs user-facing

whether end users should see all of them

whether we should group them by use case

whether we should eventually expose fewer higher-level tools

whether feedback should attach to a specific tool

whether BCP Dev / BCP vertical / New Star should eventually be separate MCP surfaces or one server with multiple tool families

My current take
The MCP layer works. The architecture is good. The call validated the direction.

The next sprint should probably be:

hosted MCP access

ClickUp API / lot-count pull

PF sign convention review

New Star connector investigation

first report/dashboard output design

feedback/review workflow design

I do not think we should jump straight to a full app or try to replace DataRails immediately. But I do think we should start shaping the reporting/review workflow because that is where this becomes useful to the accounting team day-to-day.

Would love to sync on this and decide what you think should be next from an engineering standpoint.

