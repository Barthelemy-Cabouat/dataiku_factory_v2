# Clients and membership

## number of clients
aliases: client count, how many clients, total clients, number of farmers, farmer count, client base
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(CLIENT_ID)
filter: CLIENTSTATUS = 'Active'
grain: one row per client
verified: 2026-08-04
Client roster from Fineract. As of 2026-08-04 this is 634,481 active clients out
of 634,503 rows.

Use `CLIENT_ID`, not `OAFID`. `OAFID` looks like the obvious One Acre Fund
identifier but is **empty in every one of the 634,503 rows** — counting distinct
`OAFID` returns 0 and will read as "no clients". `CLIENT_ID` is unique per row,
so `COUNT(*)` and `COUNT_DISTINCT(CLIENT_ID)` agree.

Beware the lookalikes. BURUNDI_BIZOPS holds 32 datasets whose names start
`VFINERACT_CLIENTS`. Only `VFINERACT_CLIENTS_BI` is the answer here. Do not use
`VFINERACT_CLIENTS_BI_QC_Final`, `..._Duplicates`, `..._prepared`, `..._joined`
or `VFINERACT_CLIENTS_with_emptyGroupNames` — these are quality-control and
intermediate stages of the flow, and each returns a plausible but wrong number.
`VFINERACT_CLIENTS_BU*` are separate country-level tables, not the BI view.

Note the suffix trap: the DSS dataset is `..._BI` but the Snowflake table behind
it is `PRODUCTION.CLIENT.VFINERACT_CLIENTS_BU`. Never write SQL from the dataset
name.

## active client
aliases: active clients, currently active, active membership
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(CLIENT_ID)
filter: CLIENTSTATUS = 'Active'
verified: 2026-08-04
`CLIENTSTATUS` takes only two values in the data today: `Active` (634,481 rows)
and `303` (22 rows). `303` is a numeric code that has leaked into a text status
field — a data quality artifact, not a real status. Exclude it, and mention it
if a total is being reconciled against another source, since it explains a
22-row discrepancy.

`CLIENTSUBSTATUS` exists for finer breakdowns but has not been profiled here;
check its values before relying on it.

## clients by district
aliases: clients per district, client distribution, where are our clients, clients by region
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(CLIENT_ID)
filter: CLIENTSTATUS = 'Active'
grain: one row per client
verified: 2026-08-04
Group by `DISTRICTNAME` for One Acre Fund's own operational districts, or by
`GOVTDISTRICTNAME` for government administrative districts. These are different
hierarchies and will not match — ask which one is meant if the question just
says "district".

The full OAF hierarchy runs `REGIONNAME` > `DISTRICTNAME` > `SECTOR` > `CELL` >
`SITE` > `VILLAGE` > `GROUP_NAME`. The government hierarchy is
`GOVTREGIONNAME` > `GOVTDISTRICTNAME`.

## client group
aliases: groups, farmer groups, number of groups, group count
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(GROUPID)
filter: CLIENTSTATUS = 'Active'
verified: 2026-08-04
Clients are organised into groups. `GROUPID` is the identifier; `GROUP_NAME` and
`GROUPCODE` are labels and are not guaranteed unique — count `GROUPID`.

`VFINERACT_CLIENTS_with_emptyGroupNames` exists precisely because some group
names are blank, so do not count `GROUP_NAME` distinct values.

## field officer
aliases: field officers, FO, staff, how many field officers
project: BURUNDI_BIZOPS
dataset: VFINERACT_CLIENTS_BI
measure: COUNT_DISTINCT(FIELDOFFICER)
filter: CLIENTSTATUS = 'Active'
verified: 2026-08-04
`FIELDOFFICER` is a free-text name on the client record, not a staff ID, so the
count is approximate — spelling variants inflate it. Treat it as "field officers
with at least one active client", and say so when reporting. For a headcount,
ask for an HR source instead.
