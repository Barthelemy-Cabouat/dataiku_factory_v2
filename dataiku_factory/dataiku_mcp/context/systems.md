# Source systems

Vocabulary entries. These carry no dataset — they exist so the agent can read
a question correctly before it goes looking for one. See `_conventions.md`.

## Fineract
kind: vocabulary
aliases: Fineract, VFINERACT, loan system, core banking, account number, OU
verified: 2026-08-06
The core lending system. Holds clients, groups, loan accounts, repayments and
savings. Everything prefixed `VFINERACT_` or `V_FINERACT_` originates here,
and the client roster (clients.md) is a Fineract view.

**OU — Organisational Unit.** The Fineract structure that mirrors districts,
sites and groups. OUs must be created and aligned before a season's enrolment
can be loaded, which is why "OU creation" and "OU alignment" appear as
blocking tasks each season. OU errors are a known cause of farmers ending up
in placeholder or misaligned groups.

## CLIF
kind: vocabulary
aliases: CLIF, CLIF migration, CLIF credit, new system
verified: 2026-08-06
The platform One Acre Fund is migrating onto, of which CLIF Credit is the
Fineract-based lending component. Alongside it sit Payment Hub, BOP, the Odoo
utilities modules and SAP.

Two consequences for figures. Underpayments and overpayments from 24A/24B/25A/
25B are being moved into CLIF and seasons recreated there, so historical
balances may exist in two places during migration. And on 2026-06-15 a key
CLIF repayments table was changed to exclude reversed repayments
(`WHERE NOT is_reversed`) — repayment figures computed before and after that
date are not comparable. Date any repayment figure you quote.

`CLIF_site` and `Site_as_CLIF` columns carry the CLIF site identifier and are
what reconciliation joins on.

## Roster
kind: vocabulary
aliases: Roster, roster data, ROSTER_REPAYMENTS, season closure system
verified: 2026-08-06
The legacy operational system of record for members, deliveries, returns and
season closure. Write-offs and season closure happen in Roster. CDM uploads
corrections into Roster and then QCs that they landed.

Roster is also the fallback when Fineract group assignment is wrong — group
identity is resolved against Roster before transfers complete. Where a figure
must reconcile, Logistics verification that deliveries and returns are updated
in Roster is a precondition, not a detail.

## AppSheet
kind: vocabulary
aliases: AppSheet, app, FO app, FM app, mobile app
verified: 2026-08-06
The mobile app FOs and FMs use in the field for distribution and, increasingly,
claim status. Its backing store is PostgreSQL on connection
`Burundi_AppSheet_DB_Prod` — both `26B_Distribution_AppSheet_View` and
`burundi_claims_repository` resolve there, under table names that do not match
their DSS dataset names. Always resolve the physical location rather than
building SQL from a dataset name.

Field complaints about "AppSheet not working" in the SFD minutes are usually
about FMs not seeing per-member detail, which is a permissions/sync issue
rather than missing data.

## Kobo
kind: vocabulary
aliases: Kobo, kobo forms, kobo data, data collection, enquête, form
verified: 2026-08-06
The form platform used for enrolment, distribution, claims collection and
stock takes, with paper backup. Kobo data arrives as one dataset per district
(`KOBO_Claims_<District>`, `27A_Enrollment_<District>`) which are then stacked
and flattened.

Flattened Kobo exports are wide and entirely string-typed — one prefixed
column block per form branch. `KOBO_Claims_Flattened` has 120 such columns. Use
them to read what was submitted, not to aggregate; the normalised repository
(`burundi_claims_repository`) is the counting surface.

## DPIB
kind: vocabulary
aliases: DPIB, input reconciliation, réconciliation des intrants, variance, site variance, stock reconciliation
verified: 2026-08-06
The input reconciliation analysis: what was ordered and credited against what
was physically distributed, compared at site level to surface variances. Run
per season and used to prioritise sites for investigation and to decide which
products to re-examine. The 2025 OKR target was to hold absolute-value
variances to 1.5% of farmer credit.

DPIB output drives CI's audit queue and feeds deceased-farmer write-off
decisions (only products actually distributed in the current season may be
written off). The acronym's expansion is not stated in the source documents —
use it as a proper noun and do not guess at what it stands for.

## cash and mobile money collection
kind: vocabulary
aliases: cash vs MM, cash collection, how do farmers pay, payment channel, digital collection, RvR, revenue vs repayments
verified: 2026-08-06
For the transaction dataset, see "mobile money repayment" in repayment.md —
this entry explains the channels, not the number.

Repayment arrives either as mobile money or as cash collected at site. Mobile
money collection was expanded to 400 sites through 2025. For 26A the reported
split was MM 18Bn against cash 32Bn — the ratio shifts every season and is not
stable enough to assume.

**RvR — Revenue versus Repayments.** The Collections team's reconciliation of
what was billed against what was received. A distinct exercise from the
repayment rate in repayment.md, and its own tooling; do not treat an RvR figure
and a repayment-rate figure as the same quantity.
