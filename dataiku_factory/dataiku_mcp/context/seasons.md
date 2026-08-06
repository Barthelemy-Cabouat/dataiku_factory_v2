# Seasons and the season cycle

Vocabulary entries. These carry no dataset — they exist so the agent can read
a question correctly before it goes looking for one. See `_conventions.md`.

## season code
kind: vocabulary
aliases: season, saison, 24A, 24B, 25A, 25B, 26A, 26B, 27A, 27B, what season, which season
verified: 2026-08-06
Burundi runs two agricultural seasons a year, labelled by the two-digit
calendar year plus `A` or `B`. `A` is the first season of the year, `B` the
second. So 26A precedes 26B, and 27A follows 26B.

**Almost nothing in this glossary is season-agnostic.** Datasets, columns and
dashboards are built per season: `Credit_26A` and `Repayment26A` on one
dataset, `Credit_26B` and `Credit_avec_CET` on another, `27A_Enrol_*` in its
own project. A question that names no season cannot be answered from a single
dataset — ask which one is meant.

Several seasons are always live at once, at different stages. In mid-2026
BizOps was simultaneously closing 24A/24B/25A, finishing 25B claims, running
26A corrections, collecting 26B repayment and enrolling 27A. "The current
season" is therefore ambiguous; "the season we are collecting repayment for"
and "the season we are enrolling" are different answers.

## season stage
kind: vocabulary
aliases: season stage, season cycle, season closure, clôture, write-off, season closed
verified: 2026-08-06
A season moves through enrolment and order taking, then distribution of
inputs, then repayment collection, then claims and corrections, then
reconciliation, then closure and write-off. Figures are provisional until
closure — credit and repayment totals for a season still in claims will keep
moving, which is why a number quoted last week may not reproduce today.

Closure happens in Roster and, increasingly, CLIF. A write-off proposal is
submitted before final closure. Once a season is closed its totals stop
changing; before that, always date the figure you quote.

## what multiseason means
kind: vocabulary
aliases: what is multiseason, why multiseason, multiseason products, produits multisaison
verified: 2026-08-06
For the measure, see "multi-season credit" in credit.md — this entry explains
the concept, not the number.

Products sold on credit that spans more than one season — solar lamps,
cookstoves, phones — as distinct from the season's own inputs. Multiseason
credit is carried in its own column and is a real component of the headline
credit figure: for 26A it was 5,379,090,507 BIF of the 50,965,187,549 total.

Two operational consequences worth knowing. A farmer holding multiseason
products cannot abandon the programme mid-term, and a district that forgets
multiseason in a credit calculation gets the total wrong — this happened in
Nyabihanga and is a recurring source of reconciliation variance.

Watch the spelling. The flag and detail columns use French `Multisaison`, the
amount column sometimes uses English `multiseason` (`multiseason_Credit26B` on
the 26B distribution view). Quote column names exactly.

## what CET means
kind: vocabulary
aliases: what is CET, why CET, frais d'enregistrement, registration fee, does credit include CET
verified: 2026-08-06
For the measure, see "CET" in credit.md — this entry explains the concept, not
the number.

A per-farmer charge added on top of season credit. It is large enough to
matter: 6,613,755,000 BIF of the 26A total. "Credit" in Burundi reporting
means credit **including** CET by default (`Credit_avec_CET`,
`Total_Credit_CET`); the base figure without it is `Credit_26B` / `Credit_26A`.
If a question just says "credit", it means the inclusive figure — but the two
differ by the whole CET component, so ask if the context is a reconciliation.

## banning
kind: vocabulary
aliases: banning, banned farmers, ban list, farmer banning, blacklist
verified: 2026-08-06
Excluding a farmer from a future season for non-repayment. BizOps documented
and implemented a standardised banning process during 2025, and reduced the
required gap from two seasons to one — a farmer can now be banned for a
shortfall in the immediately preceding season. Banning lists are a season-
closure output and are decided after claims are resolved, not from a raw
underpayment number.

## abandon
kind: vocabulary
aliases: abandon, abandonment, dropout, farmer left, attrition
verified: 2026-08-06
A farmer leaving the programme mid-season, as opposed to being banned. Not
available for farmers holding multiseason products. Handled alongside deceased
clients and GL bonus cleanup in the distribution invoice workflow, so a
question about attrition may be answered from claims data rather than from the
client roster.
