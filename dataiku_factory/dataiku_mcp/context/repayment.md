# Repayment, underpayment and overpayment

## total repaid
aliases: total repaid, repayments, remboursement, total repayment, how much have farmers repaid, montant remboursé
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Repayment26A)
grain: one row per farmer account for season 26A
verified: 2026-08-06
The season-26A repayment total. As of 2026-08-06: 50,293,053,526 BIF across
494,952 rows, no nulls.

This dataset is the per-farmer credit-and-repayment view for **26A only**. The
season is baked into the column names (`Credit_26A`, `Repayment26A`), so it
cannot answer a question about another season. For 26B the equivalent
repayment figure is `CUMULATIVE_TRANSACTION_AMOUNT` on
`26B_Distribution_AppSheet_View` — see "cumulative transactions" in credit.md.
Ask which season is meant if the question does not say; BizOps routinely runs
three or four seasons in parallel.

Beware the lookalikes. BURUNDI_BIZOPS holds 119 datasets matching "repayment".
`26A_Credit_DistrRepaymentMultiS` is the agreed one. Do not use
`..._prepareforexport`, `..._with_OCR_progress_site`, `..._FORPRINTING`,
`..._Ready_for_superset` or any `..._Check*` variant — these are export and
QC stages of the same flow and each returns a plausible but different number.
The `26B_Repayment_KPI*` datasets are a Google Sheet sync with one column per
week, mostly typed as string; they are a field-reporting artifact, not a
measure source.

## total credit 26A
aliases: 26A credit, credit 26A, total credit 26A, crédit 26A
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Total_Credit_CET)
grain: one row per farmer account for season 26A
verified: 2026-08-06
The headline 26A credit figure. As of 2026-08-06: 50,965,187,549 BIF.

`Total_Credit_CET` is exactly `Credit_26A + Multisaison + CET`, checked
against the data on 2026-08-06, and BizOps reporting quotes that split:
base credit 38,972,342,042, multiseason 5,379,090,507, CET 6,613,755,000.

Do not confuse this with "total credit" in credit.md, which is 26B
(`Credit_avec_CET` on `26B_Distribution_AppSheet_View`). The two are different
seasons and will never reconcile.

## repayment rate
aliases: repayment rate, taux de remboursement, % repaid, repayment performance, how are repayments going
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Repayment26A) / SUM(Total_Credit_CET)
grain: one row per farmer account for season 26A
verified: 2026-08-06
Computed, not stored. On 2026-08-06 this gives 98.7% for 26A.

Two caveats that matter more than the arithmetic. First, **the published rate
includes overpayments**, so it can exceed 100% at group or district level —
the SFD weekly KPI table shows districts at 100.01% and 100.64%. A rate above
100% is not a data error; it means some members paid more than they owed.
Second, the figure BizOps quotes in the Monday systems meeting is taken from
the 26A dashboard after claims corrections, so it moves as claims are
processed. Reporting 98.7% when the meeting minute says 98.5% is a timing
difference, not a contradiction — say which basis you used.

Never compute a repayment rate by dividing across two different datasets
(for example repayment from this dataset against credit from the distribution
view). The row populations differ.

## underpayment
aliases: underpayment, underpayments, sous-paiement, outstanding, arrears, who still owes, montant restant
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Total_Credit_CET - Repayment26A) where Repayment26A < Total_Credit_CET
grain: one row per farmer account for season 26A
verified: 2026-08-06
Credit not yet repaid, summed over **only the farmers who are short**.
Overpaying farmers must not cancel out underpaying ones. On 2026-08-06 for
26A: 4,630,107,152 BIF across 150,089 farmer accounts in 5,241 groups.

Netting the two sides instead — `SUM(Total_Credit_CET) - SUM(Repayment26A)`
over all rows — gives about 672M BIF. That is a different quantity, and
quoting it as "underpayment" understates the collections problem by a factor
of seven. Report the gross figure unless someone explicitly asks for the net
position.

This measure needs an expression, and `aggregate_dataset` only accepts plain
column names — `SUM(Total_Credit_CET - Repayment26A)` is rejected. Use
`execute_sql_query` on connection `Development` against
`"BURUNDI_BIZOPS"."26A_CREDIT_DISTRREPAYMENTMULTIS"`.

Expect the dataset figure to sit above the dashboard figure. The 26A · Crédit
& Underpayment dashboard quoted 778M BIF over 111.5K farmers, because the
dashboard applies claims corrections and offsets eligible overpayments from
the preceding season; this dataset is the position before those adjustments.
The 25B report showed the same two-step: BIF 1.5Bn before offsetting 25A
overpayments and BIF 1.2Bn after. Always say which basis you used, and do not
present a dataset number as if it were the dashboard number.

`26A_underpayment_v1`, `25B_underpayment` and about thirty other
`*_underpayment*` datasets exist in the project; several have empty schemas
(never built or since dropped) and will return nothing. Compute from
`26A_Credit_DistrRepaymentMultiS` rather than trusting a stale snapshot.

## high-risk underpayment
aliases: high risk farmers, high-risk underpayment, big underpayments, farmers owing more than 50k
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: COUNT_DISTINCT(AccountID) where Total_Credit_CET - Repayment26A > 50000
grain: one row per farmer account for season 26A
verified: 2026-08-06
BizOps uses a fixed BIF 50,000 threshold to define a high-risk case. The
threshold is a reporting convention, not a property of the data — if someone
asks for "high risk" without naming a number, use 50,000 and say so.

On 2026-08-06 the 26A dataset holds 26,841 such accounts carrying
2,494,892,503 BIF, i.e. 54% of all underpayment exposure sits in 18% of the
short accounts. The dashboard quotes about 14K farmers and the 25B report
quoted 5K farmers with BIF 562.5M — again the dashboard is post-corrections
and post-offsets, so expect it to be lower.

Needs `execute_sql_query`; `aggregate_dataset` cannot take an expression in
its `where`.

## overpayment
aliases: overpayment, overpayments, surpaiement, overpaid, paid too much, prepayment
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Repayment26A - Total_Credit_CET) where Repayment26A > Total_Credit_CET
grain: one row per farmer account for season 26A
verified: 2026-08-06
Money received beyond what a farmer owed. On 2026-08-06 for 26A:
3,957,973,129 BIF across 192,868 farmer accounts — comparable in size to the
underpayment, and the reason repayment rates can print above 100%.

Overpayments are carried forward and offset against the next season's
underpayment, which is why underpayment gets reported both gross and net of
them. Needs `execute_sql_query`, as above.

Claims filed about overpayment are a separate record: see `saison_surpaiement`
and `credits_surpaiement` on `burundi_claims_repository` (claims.md), which
capture which season an overpayment came from. In Fineract, overpayments are
credited to the collection account as prepayments — the description on
`V_FINERACT_COMBINED_TRANSACTIONS` says so explicitly.

## repayment by district
aliases: repayment by district, repayment by site, repayment per colline, who is behind on repayment
project: BURUNDI_BIZOPS
dataset: 26A_Credit_DistrRepaymentMultiS
measure: SUM(Repayment26A)
grain: one row per farmer account for season 26A
verified: 2026-08-06
Group by `DISTRICT_NAME` (62 distinct values) or `SITE_NAME_CLEAN`. The raw
`districtPP` / `sitePP` / `groupPP` columns are the un-cleaned originals from
the source sheet; `groupPP_cleaned` and `SITE_NAME_CLEAN` are the cleaned
versions and are what BizOps groups on. `DISTRICT_NAME` is null in 1,844 rows.

62 distinct districts is more than the ~35 operational districts in the field,
so the column carries spelling variants. Do not present it as a clean district
list without checking the values.

## mobile money repayment
aliases: mobile money, MM, MM repayment, lumicash, digital payment, cash vs mobile money
project: BURUNDI_BIZOPS
dataset: 26A_Mobile_money_repayments
measure: COUNT(*)
verified: 2026-08-06
Repayment arrives either as mobile money or as cash collected at site. The 26A
split reported in the systems meeting was MM 18Bn against cash 32Bn. Mobile
money collection was being expanded to 400 sites through 2025, so the split
shifts season to season and is not a stable ratio.

**The name lies twice.** Despite "26A_Mobile_money_repayments", the DSS
dataset points at `PRODUCTION.LOANS.V_FINERACT_COMBINED_TRANSACTIONS` on the
`Production` connection — 5,920,775 rows covering **every season and every
Fineract account**, and covering loan repayments, prepayments (overpayments
credited as prepayments) and savings, not only mobile money. An unfiltered
`COUNT(*)` here answers neither "how many 26A transactions" nor "how much came
in by mobile money". Filter by season and by transaction type before
reporting anything from it, and check the schema first —
`resolve_dataset_sql_location` will show you where it really points.

Note also that on 2026-06-15 the underlying CLIF repayments table was changed
to exclude reversed repayments (`WHERE NOT is_reversed`); figures computed
before and after that date are not comparable.
