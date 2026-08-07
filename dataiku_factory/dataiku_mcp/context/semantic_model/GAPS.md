# Gaps: semantic model vs the existing measure glossary

What the document deep-read surfaced that the glossary (`../*.md`, built
2026-08-06 from data profiling) did not know — and the few places the glossary
knows better. Ordered by risk of a wrong agent answer.

## 1. The glossary picks one basis where the org runs several

The glossary resolves "total credit" and "total repaid" to single datasets.
The meetings show credit legitimately computed five ways (Log / KPI / Synch /
FO / System) with a live FOps ruling ("KPI and Synched to be considered for
now"), and repayment on three bases with a 400M BIF analyst-to-analyst gap.
An agent answering from the glossary alone gives *a* correct number while the
questioner may hold a different-basis number — the exact failure mode of the
"96.3% vs 95.4%" tables. **Fix:** glossary entries for credit/repayment now
need a `basis:` line and a pointer to the perspectives block in
`semantic_model.yaml`.

## 2. Reversed transactions — the glossary caveat was too small

The glossary noted the Jun 15 `WHERE NOT is_reversed` change as a
comparability footnote. The Jul 15 analysis is much stronger: reversed mostly
= internal loan↔savings migration, money NOT lost; plus TREF junk rows; naive
handling misstates a farmer's balance 2×. This upgrades from footnote to a
first-class rule for anything touching `V_FINERACT_COMBINED_TRANSACTIONS*`.

## 3. Missing entities entirely absent from the glossary

- **Invoice (facture)** — the reference document farmers claim against;
  batching, missing-farmer, and email/paper channel issues.
- **Delivery/Logistics chain** — ordered/delivered/returned/distributed/
  dropped distinctions, SAP↔TMS↔Kobo reconciliation, warehouse stock counts.
  The glossary's `distribution.md` covers the farmer-level view only.
- **Synchronisation** as a concept (data-entry progress ≠ physical progress) —
  an agent reading "synch at 97%" needs this.
- **Drops** (26B: ~4Bn BIF) — nowhere in the glossary.
- **Order taking / targets** (order vs target per product per district, FD
  reasons for misses).
- **Exclusion/banning protocol** as a workflow with an in-flight protocol doc
  (glossary has a two-line vocabulary entry).
- **Payment channels** (Payment Hub failed-transaction reconciliation,
  Bancobu wallets, COOPEC fallback, wallet balance caps).
- **Hotline/CC metrics** (Yeastar, answered/abandoned) — new measurable
  domain since Jul 2026.

## 4. Season boundary allocation

The glossary treats seasons as clean partitions. The notes show ~190M BIF of
26A repayments arriving inside the 26B window with an unresolved reallocation
mechanism. Any cross-season comparison near a boundary carries this.

## 5. Claims: counts are time-stamped, deadlines are politics

Glossary reports 75,707 claims in the repository. Meetings show a different
consolidated series (86K → 163.5K by Jul 8) that includes Kobo *and*
AppSheet and three campaigns — the repository the agent profiled covers a
subset (two campaigns, 26A facture + 26B distribution). The glossary's number
is right for its table and wrong as "total claims". Also: claim deadlines
were extended/reopened repeatedly; any claims figure needs an as-of date.

## 6. Where the glossary knows MORE than the documents

Keep these — the semantic model inherits them, not the other way round:

- The `26A_Credit_DistrRepaymentMultiS` grain trap (repayment repeated across
  multi-line farmers; SUM overstates by 127M) — invisible in meetings.
- `OAFID` null traps, `CLIENTSTATUS='303'`, string-typed product columns,
  lookalike `_QC_/_prepared` datasets — all profiling-only knowledge.
- Exact verified figures with dates and non-null counts.

## 7. Governance signals the glossary couldn't see

- Project-level governance is emerging: dedicated season project
  (BURUNDI_BIZOPS_26B) to stop BURUNDI_BIZOPS growth; duplicate 27A projects
  merged; Elvis's framework (domain projects, recipe rights, Snowflake
  production deployment). The agent's `_project_scope.md` should track these
  as the registry of record evolves.
- The claims-correction dashboard and BK performance emails mean *process*
  datasets (`26A_claims_correction_with_status`, `26A_bks_performance_summary`)
  are legitimate agent answers for "how far along are corrections".

## Suggested next actions

1. Add `basis:` lines to credit/repayment glossary entries and cross-link the
   semantic model (small edit, high value).
2. Build the missing measure entries for invoices, deliveries/drops, and
   hotline metrics — each needs one profiling pass to find its dataset.
3. Push `datahub_glossary.yaml` into DataHub and attach terms to the Snowflake/
   PostgreSQL datasets already ingested there.
4. Create DSS wiki articles from the entity blocks (one per entity) so the
   model is visible where analysts work.
5. Take the two OPEN disputes (repayment SSOT, 26B claims SSOT) to the owners
   named in METHODOLOGY.md — the registry can record a ruling within a week of
   one existing.
