# Golden dataset selection — methodology and validation

How the `golden_datasets` list in `semantic_model.yaml` was chosen, and how to
validate or challenge an entry. Written 2026-08-06 from a full read of the BI
Systems notes (May–Aug 2026), CDM & CE sync notes (Jul 2025–Jun 2026), the
SFD meeting notes, the 2026 org structure and the 2025 OKRs.

## The problem this solves

The org runs the same number on up to five bases (Log / KPI / Synch / FO /
System) and the meetings spend real time reconciling them. Three "single
source of truth" demands appear verbatim in the notes: for repayment
reporting (Ulrich, 15 Jul), for 26B claims (follow-up table, 5 Aug), and for
Dataiku project structure (Elvis's collaboration framework, 29 Jul). A golden
dataset registry is the answer to those demands — but only if the selection is
evidence-based rather than whoever-wrote-the-YAML's opinion.

## Selection criteria (in priority order)

1. **Citation as authority.** The artifact is what leadership meetings read
   numbers FROM, repeatedly. Operationalised: reference frequency across the
   meeting corpus (the repayment workbook: 93 citations; synchronisation
   report: 61; SFD KPI sheet: 60). Frequency alone is not enough — the
   citation must be *load-bearing* (a decision or reported figure rests on it).

2. **A named governance step.** Someone accountable reviews it: "611k members
   confirmed in the KPI **after FD review**"; claims consolidated "into a
   single dashboard claims table"; RBM QC before upload. An artifact with a
   review ritual outranks a technically better dataset without one.

3. **Explicit stakeholder ruling.** Where sources conflict, prefer the one a
   stakeholder ruled for on the record — e.g. FOps on 26B credit: "KPI and
   Synched data are the ones to be considered for now". Record the ruling AND
   its provisionality.

4. **Survivorship.** The artifact survived a consolidation event: duplicate
   27A enrolment projects merged (loser archived), Kobo+AppSheet claims merged
   into one table, per-district shards stacked. The survivor is golden; the
   inputs are lineage.

5. **Verified against the data.** Where the agent has DSS access, the entry
   was profiled (row counts, grain, null traps) — the measure glossary in
   `../` holds those verifications with dates.

## Status vocabulary

- **golden** — meets ≥2 criteria, no unresolved challenge. Agents may answer
  from it, naming it.
- **candidate** — technically sound and/or profiled, but lacks the governance
  citation. Agents may use it with a caveat.
- **disputed** — actively contested in meetings (credit basis, repayment
  totals, 26B claims). Agents must present the competing bases, never pick
  silently.
- **deprecated** — explicitly retired in the record (27AENROLLMENT project,
  AppSheet platform). Agents must not answer from it and should say so if
  pointed at it.

## Validation protocol for a new/challenged entry

1. **Trace the citation.** Find ≥2 independent meeting references where a
   decision or reported figure rests on the artifact. One mention in one
   meeting is not authority.
2. **Name the owner.** The registry entry must carry the accountable person
   or team (FOps repayments → Emmanuella; claims correction → CDM/Ulrich;
   LOG data → Christian/Shevalyne). If no one owns it, it cannot be golden.
3. **Profile the physical data.** Row count vs entity count (grain), null
   traps on keys, type traps (string-typed numerics), season scope. Use
   `aggregate_dataset`/SQL; record numbers and date in the entry.
4. **Reconcile against one adjacent basis.** Golden ≠ correct; golden =
   *known relationship to the alternatives*. A repayment source must state its
   expected gap vs bank and vs KPI at validation date.
5. **Write the dispute down if reconciliation fails** and set status
   `disputed` with both figures. The registry's value is honest disagreement,
   not forced convergence.
6. **Re-verify on season closure** and on any system change (the Jun 15
   `is_reversed` filter change is the canonical example of a silent
   basis-break).

## Known open disputes the registry must not paper over

| Dispute | Positions | Owner of resolution |
|---|---|---|
| 26B credit basis | Log vs KPI vs Synch (0.2% spread); FOps provisionally rules KPI+Synch | FOps + BizOps joint |
| 26B total repaid | ~400M BIF gap between analyst calculations; season-allocation of 26A money | Emmanuella + Ulrich |
| Repayment SSOT | No validated dataset exists; reversed/TREF semantics documented but unbuilt | BizOps (Ulrich rec., 15 Jul) |
| 26B claims SSOT | "Urgent need to lock in a single source of truth" — dataset recommendation pending | BizOps official rec. |
| Claims cut-off | FOps reopened forms unilaterally; BizOps declared post-deadline claims non-processable | FOPS+BizOps jointly (per 29 Jul note) |
| Invoiced credit vs FOPS estimate | 50,663M vs 51,165M (26A, May) | CDM |

## Deployment targets

- **Dataiku**: no native semantic-model object. Two supported paths, both
  generated from `semantic_model.yaml` (keep YAML as the single source):
  1. the agent glossary in `../*.md` (already loaded by the MCP; measures
     layer) — extend entries rather than duplicating them;
  2. DSS **wiki articles** per entity (via `create_wiki_article`) and dataset
     **descriptions/tags** on the golden datasets, so the authority status is
     visible in the Flow. Elvis's collaboration framework (domain projects,
     production deployment) is the org-side counterpart.
- **DataHub**: `datahub_glossary.yaml` ingests directly with the
  `datahub-business-glossary` source; attach terms to the physical datasets
  (Snowflake/PostgreSQL) once those are ingested, and use the
  `status` custom property to surface disputes.

## Limits

Reference frequency is biased toward operational cadence (weekly repayment
beats quarterly closure memos). The SFD corpus over-weights field-reported
sheets. Sheets referenced by shortened IDs could not all be opened — titles
come from link text. And this registry inherits the meetings' own blind spot:
what nobody cites (e.g. the client roster itself) can still be golden; the
measure glossary covers those from data profiling instead.
