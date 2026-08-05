# Credit and repayment

## total credit
aliases: total credit, credit total, how much credit, total lending, credit with CET, credit avec CET
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(Credit_avec_CET)
grain: one row per farmer per distribution record
verified: 2026-08-04
The headline credit figure, inclusive of CET. As of 2026-08-04:
41,097,314,734 across 532,455 rows.

**Only 418,746 of those 532,455 rows have a value** — `Credit_avec_CET` is null
in 21.4% of rows. Always report the non-null count alongside the total.
`aggregate_dataset` returns it automatically as
`Credit_avec_CET__non_null_count`.

Never estimate this from a sample. The nulls are not evenly spread: a 1,000-row
read reports 3.9% null and a mean of 107,714, while a 5,000-row read reports
21.1% and 112,526. Neither resembles the true mean of 98,144.

## credit excluding CET
aliases: credit 26B, Credit_26B, credit without CET, base credit
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(Credit_26B)
verified: 2026-08-04
Season 26B credit before CET is added. Use this only when someone explicitly
asks to exclude CET; the default meaning of "credit" in Burundi reporting is
`Credit_avec_CET`. If a question is ambiguous, ask which is meant rather than
picking — the two differ by the whole CET component.

## CET
aliases: CET, cotisation, CET amount
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(CET)
verified: 2026-08-04
The component that distinguishes `Credit_avec_CET` from `Credit_26B`. Stored as
a bigint on the same row. Has not been profiled for nulls — check the non-null
count before reporting a total.

## multi-season credit
aliases: multisaison, multiseason, multi season credit, repeat season
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(multiseason_Credit26B)
verified: 2026-08-04
`Multisaison` is a bigint flag and `Multisaison detail` a text description;
`multiseason_Credit26B` carries the credit amount. Note the inconsistent
spelling across the three columns — French `Multisaison` for the flag and detail,
English `multiseason` for the amount. Quote column names exactly;
`Multisaison detail` contains a space and must be quoted in SQL.

## cumulative transactions
aliases: transactions, repayment, repaid, cumulative transaction amount, how much repaid
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(CUMULATIVE_TRANSACTION_AMOUNT)
verified: 2026-08-04
Total transacted per farmer record. Treat this as the repayment-side figure
against `Credit_avec_CET`, but do not present a repayment *rate* from these two
columns without confirming with the Burundi BizOps team that they are on the
same basis and period — the dataset name says Distribution, not Repayment, and
the definitional risk is higher than the arithmetic.

`Transactions_details_concat` is a concatenated text field, not a number. Do not
try to aggregate it.
