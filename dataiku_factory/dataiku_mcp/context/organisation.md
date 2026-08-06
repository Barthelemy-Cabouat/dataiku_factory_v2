# People, teams and geography

Vocabulary entries. These carry no dataset — they exist so the agent can read
a question correctly before it goes looking for one. See `_conventions.md`.

## field hierarchy
kind: vocabulary
aliases: FM, FD, SFD, AFD, GL, field manager, field director, group leader, what is an FO, who is the FO, field team, équipe terrain
verified: 2026-08-06
The field chain, smallest unit upward:

- **GL — Group Leader.** A farmer who leads a group of members. Around 20,000
  of them. Attends a weekly GL meeting; attendance is a tracked KPI. Receives a
  bonus, which is itself a claim type (`Bonus GL`).
- **FO — Field Officer.** Runs one or more collines. Registers members,
  distributes inputs, collects repayment, files claims. The `FIELDOFFICER`
  column on the client roster is a free-text name, not a staff ID — see
  clients.md.
- **FM — Field Manager.** Supervises FOs. Verifies KPIs and nursery
  checklists, receives per-member reports.
- **FD — Field Director.** Runs a district. Reviews enrolment figures, chases
  synchronisation, confirms site closure.
- **AFD — Assistant Field Director.** Deputises for the FD at district level.
  The expansion is inferred from usage, not stated in the source documents —
  confirm before putting it in writing.
- **SFD — Senior Field Director.** Regional, above several FDs. The weekly
  *Réunion des SFDs* is where field observations, KPIs and district-level
  repayment problems are aired.

FOps (Field Operations) is the department these roles sit in. It is distinct
from BizOps, which owns the data.

## BizOps teams
kind: vocabulary
aliases: BizOps, CDM, CE, CI, CC, hotline, call center, collections, case investigations, client data management, which team, who owns this
verified: 2026-08-06
BizOps (Business Operations) is the data and operations department. Its four
sub-teams are named by acronym everywhere in the source documents:

- **CDM — Client Data Management.** Owns the client roster, enrolment data,
  Fineract cleanup, corrections uploads.
- **CE — Collections.** Owns repayment collection, cash and mobile money
  reconciliation, revenue-vs-repayment (RvR).
- **CI — Case Investigations.** Owns fraud cases, input reconciliation audits,
  stock takes, site variance follow-up.
- **CC — Call Center**, also called the **Hotline**. Farmer-facing phone
  support.

Each has its own SLA and KPI set. "The CDM number" and "the CE number" for the
same season can differ legitimately because the teams measure different stages.

Above them: Systems Lead, BizOps Lead, and specialist roles (Tech, CX & CI).
Below: Senior Coordinators, Senior Supervisors, District Supervisors, and
agents — CI Agents, CDM Agents, Hotline Agents, Bookkeepers.

## Bookkeeper
kind: vocabulary
aliases: bookkeeper, BK, BKs, RBM, RBMs, regional business manager, who does QC
verified: 2026-08-06
**BK — Bookkeeper.** District-level staff who do data entry and the first pass
of claims correction and QC. Roughly 27 district supervisors/bookkeepers.

**RBM — Regional Business Manager.** Regional, above the Bookkeepers. RBMs
train BKs on claims correction, quality-check their work, and are responsible
for uploading validated repayments into the system. The source documents also
use **RBC** (Regional Business Manager/Coordinator) for what appears to be the
same or an adjacent role; treat the expansion as probable rather than
confirmed.

The QC chain matters when reading a figure: claims are submitted by FOs,
corrected by BKs, QC'd by RBMs, then uploaded. A number quoted before upload
and one quoted after will differ.

## geography hierarchy
kind: vocabulary
aliases: colline, collines, district, site, region, sector, cell, village, where, geography, hierarchy, umutumba
verified: 2026-08-06
Two hierarchies exist and they do not match.

**OAF operational:** `REGIONNAME` > `DISTRICTNAME` > `SECTOR` > `CELL` >
`SITE` > `VILLAGE` > `GROUP_NAME`, on the client roster.
**Government administrative:** `GOVTREGIONNAME` > `GOVTDISTRICTNAME`.

A question that just says "district" is ambiguous between them — ask.

**Colline** (Kirundi *umutumba*) is the hill, the basic settlement unit and the
FO's patch. About 1,000 collines in 26B. It appears as `Colline` on the
distribution view and is roughly but not exactly interchangeable with "site" —
`CLIF_site` and `Site_as_CLIF` are the site-level identifiers used for
reconciliation and stock delivery.

Each dataset carries its own geography columns, spelled differently, and they
have not been reconciled: `DISTRICTNAME` on the client roster, `District` on
the distribution view, `DISTRICT_NAME` and `districtPP` on the 26A credit
view, `district` on the claims repository. The 26A credit view alone shows 62
distinct district values against roughly 35 operational districts, so spelling
variants are present. Do not join or compare hierarchies across datasets
without first checking that the values line up.

District names appearing in the weekly SFD KPI table include Bugendana,
Buhinyuza, Bukirasazi, Butaganzwa, Bweru, Gahombo, Gasorwe, Gihogazi, Gishubi,
Gitaramuka, Gitega, Giteranyi, Kabarore, Karusi, Kayokwe, Kiremba, Kirundo,
Makebuko, Marangara, Matongo, Mbuye, Muramvya, Muyinga, Mwumba, Ngozi,
Nyabihanga, Nyabikere, Nyarusange, Rango, Ruyigi, Tangara — plus the districts
opened for 27A: Isare, Cankuzo, Gisagara, Musongati, Rutana.

## field KPIs
kind: vocabulary
aliases: KPI, KPIs, weekly KPIs, GL attendance, member visits, 100% repayment, hyper KPIs, field performance
verified: 2026-08-06
The weekly SFD meeting tracks four field KPIs by district, all as percentages:
GL meeting attendance, members visited this week, groups that have repaid
100%, and members who have repaid 100%.

Two things to know before quoting them. They come from field-reported Kobo
collection, not from the transaction system, so they are a management signal
rather than an audited figure — the meeting minutes themselves flag districts
whose reported percentages "do not correspond to reality on the ground".
And the 100%-repayment percentages can exceed 100 (Muramvya printed 100.64%)
because overpayments are included.

BizOps treats anything below 98% on repayment as a red flag warranting a fraud
check, and low GL attendance or visit rates as the leading indicator behind it.
