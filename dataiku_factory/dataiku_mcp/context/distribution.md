# Distribution and inputs

## distribution records
aliases: distributions, deliveries, distribution count, how many distributions
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: COUNT(*)
grain: one row per farmer per distribution record
verified: 2026-08-04
532,455 rows as of 2026-08-04. This is a row count, not a farmer count — the
grain has not been confirmed as one-row-per-farmer. For a farmer count use
`COUNT_DISTINCT(AccountID)` and say explicitly which you reported.

The DSS dataset is `26B_Distribution_AppSheet_View`; the PostgreSQL table behind
it is `BURUNDI_BIZOPS_26b_distribution_appsheet_view` on connection
`Burundi_AppSheet_DB_Prod`. Never build SQL from the dataset name — an agent
that tried got `relation "26B_Distribution_AppSheet_View" does not exist`, and
the lookalike `BURUNDI_ELVIS_BIZ_26b_distribution_appsheet_view_copy` sits
beside it in the same schema.

## fertiliser quantities
aliases: fertiliser, fertilizer, uree, urea, fomi, inputs delivered, input quantities
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(<column>)
verified: 2026-08-04
Each input is its own column, one per product, so "total fertiliser" requires
naming the columns rather than a single measure. The fertiliser-family columns
are `uree` (urea), `fomi_imbura`, `fomi_bagara` and `ishwagara`.

Units are not recorded in the schema. Confirm with the Burundi BizOps team
whether these are kilograms, bags or units before summing across products —
adding a kg column to a bag column produces a number that means nothing. Report
per-product totals unless someone has confirmed a common unit.

## seed and crop inputs
aliases: seed, seeds, maize seed, crop inputs, sc_403, haraka
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(<column>)
verified: 2026-08-04
Seed varieties are separate columns: `sc_403`, `sc_637`, `sc_719`, `pan_53`,
`pan_691`, `haraka_101`. The names are variety codes, not quantities of a single
"seed" product.

`ipaswari`, `ishiga` and `isuka` are further input columns in the same block;
their product meaning has not been documented here. Ask rather than assume.

## non-agricultural products
aliases: solar, biolite, phones, itel, cookstove, non-ag products, assets
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: SUM(<column>)
verified: 2026-08-04
Product columns outside the agricultural inputs: `biolite_625` (cookstove),
`skp_400` (solar), `itel_5606`, `itel_5627`, `itel_2160` (phones), `ihema`,
`pics` (storage bags), `isafuriya`.

Watch the types. Several of these are stored as **string**, not numeric —
`skp_400`, `biolite_625`, `itel_5606` and `itel_2160` are strings while
`itel_5627` is a double. `SUM` on a string column will either fail or coerce
unpredictably. Check the schema with `inspect_dataset_schema` before
aggregating, and report a `COUNT` of non-empty values instead where the column
is text.

## geography of distribution
aliases: distribution by district, deliveries by site, where were inputs delivered
project: BURUNDI_BIZOPS
dataset: 26B_Distribution_AppSheet_View
measure: COUNT(*)
verified: 2026-08-04
Group by `District`, `Colline` or `CLIF_site`. Note these are the distribution
dataset's own geography columns and are *not* the same fields as the client
roster's `DISTRICTNAME` / `GOVTDISTRICTNAME` in VFINERACT_CLIENTS_BI. Do not
join or compare the two hierarchies without checking that the values line up.
