# Enrolment

## members enrolled
aliases: enrolment, enrollment, members enrolled, enrolled farmers, inscription, enregistrement, 27A enrolment, how many farmers signed up
project: BURUNDI_27A_ENROLMENT
dataset: 27A_Enrol_AllMembers_Ready
measure: COUNT(*)
grain: one row per enrolled member for season 27A
verified: 2026-08-06
Enrolment is the start of the season: Field Officers register members on Kobo,
groups are formed, and orders are taken. 563,649 rows as of 2026-08-06 across
36 districts and 3,614 groups.

**Count rows, not `OAFID`.** `OAFID` is null for every new farmer — all 89,409
of them — because a new member has no One Acre Fund identifier until an
account is created in Fineract. `COUNT_DISTINCT(OAFID)` returns 472,998 and
silently drops every new enrolment, which is exactly the number a question
about enrolment is usually asking for. This is the same trap as `OAFID` in
VFINERACT_CLIENTS_BI (clients.md), where the column is empty in every row.

The DSS dataset is `27A_Enrol_AllMembers_Ready`; the Snowflake table behind it
is `BURUNDI_27A_ENROLMENT.27A_Enrol_kobo_ready`. Never build SQL from the
dataset name.

Note the season is in the project key, not just the dataset name. This project
holds only 27A. There is also a `27Q_Enrollment_*` family in the same project —
those are a separate collection, not a typo for 27A, and their meaning has not
been documented here.

## new farmers
aliases: new farmers, new members, nouveaux membres, true new, first season farmers, growth
project: BURUNDI_27A_ENROLMENT
dataset: 27A_Enrol_AllMembers_Ready
measure: COUNT(*)
filter: Member_Type = 'New'
grain: one row per enrolled member for season 27A
verified: 2026-08-06
Two columns describe this and they do not mean the same thing. `Member_Type`
splits `New` (89,409) from `Old` (474,240). `New_Farmer_Type` splits that
`New` population further into `True_New` (87,810) and `Returning_Unconfirmed`
(1,599) — the latter are members who look new to the form but are believed to
have farmed with OAF before and are awaiting confirmation.

If someone asks "how many new farmers", they usually mean `True_New` = 87,810.
If they are sizing next season's roster, `Member_Type = 'New'` = 89,409 is the
right figure. The two differ by 1,599; say which you used.

`Returning_Unconfirmed` and `True_New` both have `OAFID` null, so neither can
be counted by identifier.

## enrolment account status
aliases: account status, enrolment QC, account matching, needs manual validation, enrolment data quality
project: BURUNDI_27A_ENROLMENT
dataset: 27A_Enrol_AllMembers_Ready
measure: COUNT(*)
grain: one row per enrolled member for season 27A
verified: 2026-08-06
`account_status` records how the enrolment record matched to an existing
Fineract account. On 2026-08-06:

| account_status | rows |
| --- | --- |
| NA | 557,971 |
| VALID | 3,570 |
| NO_ACCOUNT | 1,069 |
| AUTOFIX | 509 |
| AUTOFIX_COLLISION | 296 |
| WRONG_PERSON | 192 |
| NOT_FOUND | 42 |

**`NA` is 99% of the table and is not a status** — it is the absence of one.
Those rows were never put through account matching, and `AccountID_FO` is null
in all 557,971 of them. Do not report "3,570 valid accounts out of 563,649" as
if 99% had failed validation; the matching exercise only covered about 5,700
records. `needs_manual_validation` and `OAFID_suggested` support the same
workflow.

`WRONG_PERSON`, `AUTOFIX_COLLISION` and `NOT_FOUND` are the genuinely
problematic buckets and are what a data-quality question is after — 530 rows
in total.

## enrolment by district
aliases: enrolment by district, enrolment by site, members per district, where did we enrol
project: BURUNDI_27A_ENROLMENT
dataset: 27A_Enrol_AllMembers_Ready
measure: COUNT(*)
grain: one row per enrolled member for season 27A
verified: 2026-08-06
Group by `District`, `Sites` or `GroupName`. 36 districts appear, but 35 of
them contain new farmers and only 32 contain old ones — the districts opened
for 27A (Isare, Cankuzo, Gisagara, Musongati, Rutana and others named in the
SFD meetings) have new members only. A district-level comparison of 27A
against a prior season will show those as infinite growth; call them new
districts instead.

These are the enrolment form's own district labels and are not guaranteed to
match `DISTRICTNAME` on VFINERACT_CLIENTS_BI or `District` on the distribution
view. Do not join the hierarchies without checking that the values line up.

## enrolment orders
aliases: orders, order taking, commandes, enrolment orders, what did farmers order
project: BURUNDI_27A_ENROLMENT
dataset: 27A_Enrol_AllMembers_Ready
measure: COUNT(*)
verified: 2026-08-06
Ordered quantities sit as one column per product on the enrolment row — `uree`,
`bagara`, `engrais_fomi`, `fomi_totahaza`, `chaux`, the `SC_*` and `PAN_*`
maize seeds, `Haraka_101`, `Ihema`, `Isuka`, `PICs`, `Isafuriya`, `Ipaswari`,
the `ITEL_*` phones, `Biolite_625`, `SKP_400`, plus 27A additions
`Aubergine_Amaranth`, `Avocado`, `Prune_Japon`, `Cabbage_Oxylus`,
`Carrot_Onion` and `SC_608`.

**Every one of these is typed string.** `SUM` will fail or coerce
unpredictably; cast explicitly or count non-empty values instead. This differs
from `26A_Credit_DistrRepaymentMultiS`, where the same products are doubles,
so a query that works on one will not work on the other.

The product list is not the same across seasons — `SC_608`, the fruit trees
and the vegetable packs are 27A-only. Do not carry a season's column list
forward.

Order reconciliation has its own datasets in this project:
`27A_enrolment_orders_merged`, `..._duplicates`, `..._missing`,
`..._exists_flags`. These are working stages of a reconciliation, not
alternative order totals.
