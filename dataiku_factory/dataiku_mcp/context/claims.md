# Claims and corrections

## claims
aliases: claims, claim, réclamation, réclamations, ibirego, how many claims, claims submitted, farmer complaints
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT(*)
grain: one row per claim
verified: 2026-08-06
A claim is a farmer-raised correction request — a payment that never landed, a
wrong input quantity, a duplicate account, a death. Field Officers collect them
on Kobo or AppSheet, Bookkeepers and RBMs quality-check them, and the accepted
ones are applied as corrections to credit or repayment. This is why credit and
repayment totals move after a season looks closed.

As of 2026-08-06: 75,707 claims from 52,856 distinct accounts across 84
district values, submitted between 2026-04-09 and 2026-06-25.

Count rows for claims and `COUNT_DISTINCT(account_id)` for farmers — 75,707
against 52,856, because a farmer can raise several claims. Reporting one when
the question wanted the other overstates or understates by 43%. Say which you
reported. `account_id` is null in 5 rows.

The DSS dataset is `burundi_claims_repository`; the PostgreSQL table behind it
is `public.burundi_bizops_fo_claims` on connection `Burundi_AppSheet_DB_Prod`.
Never build SQL from the dataset name.

Beware the lookalikes — BURUNDI_BIZOPS holds 115 datasets matching "claims".
`burundi_claims_repository` is the normalised, one-row-per-claim repository and
is the answer for counting. `KOBO_Claims_Flattened` is the raw Kobo export: 120
columns, every field typed string, one prefixed block per claim type
(`missing_amt_*`, `duplicate_*`, `over_under_*`, `error_intrats_*`,
`unknown_*`, `deceased_*`, `kurako_*`, `ongerako_*`). It is useful for reading
what a farmer actually submitted and useless for aggregating. The 25 or so
`KOBO_Claims_<District>` datasets are per-district API pulls, not a total.

## claims by type
aliases: claim types, types de réclamation, issue type, what are farmers claiming, claim breakdown
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT(*)
grain: one row per claim
verified: 2026-08-06
Group by `issue_type`. The values are stored bilingually as
`Kirundi / French` in a single string, so match on a substring rather than an
equality — the full label for a missing payment is
`Amahera abura / Paiement manquant`.

The twelve types and their 2026-08-06 counts:

| issue_type | claims |
| --- | --- |
| Ikosa mu nyongera mwimbu canke mu bikoresho / Err. quantité | 36,154 |
| Amahera abura / Paiement manquant | 22,471 |
| Kurako / Ongerako | 6,775 |
| Amahera yishuwe menshi canke yishuwe make / Sur/Sous-paiement | 2,514 |
| Ibindi / Autre | 2,047 |
| Amahera yarenzeko / Surpaiement | 1,700 |
| Akarusho k'umukuru w'umugwi / Bonus GL | 1,252 |
| Umunwanyi afise numero zibiri / Membre double | 1,252 |
| Umunwanyi atazwi / Membre inconnu | 800 |
| Umunwanyi yapfuye / Membre décédé | 430 |
| Umunwanyi abura / Membre manquant | 249 |
| Umunwanyi ari mu mugwi canke umutumba utariwo / Err. groupe/site | 63 |

"Err. quantité" is the one usually called *erreur intrants* or *error
intrants* in meetings — a wrong input quantity recorded against a farmer. It
is the largest category by a wide margin and its corrections move the season
credit total: applying them raised 26A credit by BIF 136M.

## claim amounts
aliases: claim amount, value of claims, montant des réclamations, how much is claimed
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: SUM(amount_bif)
grain: one row per claim
verified: 2026-08-06
**`amount_bif` is only meaningful for three claim types.** It is populated in
22,471 of 22,471 missing-payment claims, 6,775 of 6,775 Kurako/Ongerako claims
and 2,514 of 2,514 over/under-payment claims — and in fewer than 20 rows for
every other type. Summing it across all claims produces a number that reads
like a total exposure but is really just those three categories.

Always report the non-null count beside the total, and prefer to filter to a
single `issue_type` first. A quantity-error claim carries its correction in
`corrected_qty` and `products_concerned`, not in `amount_bif`.

## claim status
aliases: claim status, claims pending, claims resolved, claims processed, statut des réclamations
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT(*)
grain: one row per claim
verified: 2026-08-06
Group by `status`. On 2026-08-06 **every one of the 75,707 rows has status
`Soumis`** (submitted) — no claim in this table has been marked resolved, and
`resolved_by` and `resolved_date` are correspondingly unused.

Do not read that as "no claims have been processed". Corrections are tracked
elsewhere in the flow (`26A_claims_correction_with_status`,
`26A_claims_status_flags`, `claims_26a_review_queue`) and the Dataiku claims
dashboard is what BizOps watches. Treat this table as the submission record
and say so; if someone asks how many claims are outstanding, ask which
tracker they mean rather than answering `75,707`.

## claims by season
aliases: claims by season, 26A claims, 26B claims, which season are claims for
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT(*)
grain: one row per claim
verified: 2026-08-06
There is no season column. Group by `dataset`, which holds the source the
claim was raised against: `Facture 26A` (72,282 claims) and
`Distribution 26B` (3,425). Earlier seasons are not in this table — 25A and
25B claims live in the `25A_*_claims` / `25B_*_claims` datasets, one per claim
type, and were collected on a different form.

## Kurako Ongerako
aliases: kurako, ongerako, kurako ongerako, repayment transfer, reallocation, wrong account payment
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT(*)
filter: issue_type LIKE 'Kurako%'
grain: one row per claim
verified: 2026-08-06
Kirundi for "take from / add to". A repayment was credited to the wrong
farmer, so an amount is subtracted from one account (*kurako*) and added to
another (*ongerako*). One claim row carries both sides: `account_id` is the
account to debit and `ongerako_account_id` the account to credit, with
`ongerako_name` for the recipient.

6,775 such claims on 2026-08-06 covering 230,340,445 BIF. Do not double-count
by treating the two account columns as two separate claims. These are the
adjustments RBMs were trained on and Bookkeepers QC, and they are the reason a
single farmer's repayment can change without any new money arriving.

## claim submission rate
aliases: claim submission rate, have farmers claimed, % of farmers who claimed, claims coverage
project: BURUNDI_BIZOPS
dataset: burundi_claims_repository
measure: COUNT_DISTINCT(account_id)
grain: one row per claim
verified: 2026-08-06
A derived figure BizOps quotes as "of the farmers with an outstanding
underpayment, what share have filed a claim" — 38.6% on the 26A dashboard,
and only 14.3% among the high-risk cases. A low rate is the operational
signal: it means underpayments are going unexplained rather than being
disputed.

Computing it requires joining this table's `account_id` to the underpaying
accounts in `26A_Credit_DistrRepaymentMultiS` (see repayment.md). Do not
approximate it as claims ÷ all farmers — the denominator is farmers *in
underpayment*, not the whole roster. Confirm the join key with the Burundi
BizOps team before publishing a rate; the account identifiers come from
different systems and have not been checked for format drift here.
