# Project scope block

Source of truth for the project-routing text pasted into the structured agent's
description, alongside the `## Business terms` block in `AGENT_SETUP.md` §4.

This file starts with `_`, so the glossary loader ignores it. It is not a
concept — it is agent configuration kept under the same review as the glossary.

## Why this block exists

A user asked *"How many clients have at least one repayment but zero credit in
26A?"*. The agent read **26A as a project key**, called the API, got
`Failed to read project permissions`, and replied by asking the user for the
exact project key and offering `PROJECT_26A` and `CREDIT_26A` as guesses.

Three things went wrong, and a project list only fixes the second:

1. **A season code was parsed as a project key.** `24A` … `27B` are seasons —
   see `season code` in `seasons.md`. No project key is named after one.
2. **The agent had no idea which projects exist.** The MCP server exposes no
   `list_projects` tool, so it cannot enumerate them. This block is the
   registry; without it the agent can only guess or ask.
3. **It asked the wrong question.** "Zero credit but some repayment" is not a
   defined concept. The right response is to say the term is undefined and ask
   which measure is meant — not to ask a business user for a DSS project key,
   which they should never need to supply.

Re-verify the table below when the API key's scope changes. Each row was
checked with `search_project_objects` on 2026-08-06.

---

## Block to paste

```
## Projects

Never infer a project key from the question. `24A`, `24B`, `25A`, `25B`, `26A`,
`26B`, `27A`, `27B` are agricultural **seasons**, not projects. A question that
mentions 26A is telling you which season to filter on, not where to look. There
is no project named after a season, and no `PROJECT_26A` or `CREDIT_26A`.

You cannot list projects — no tool exposes them. Use this registry.

**Default to BURUNDI_BIZOPS.** It backs every glossary topic except enrolment
and is the right first look for clients, credit, distribution, repayment,
underpayment and claims, across all seasons.

| Project key | Holds | Reach for it when |
|---|---|---|
| `BURUNDI_BIZOPS` | Clients, credit, distribution, repayment, underpayment, claims, mobile money. Largest by far. | Default. Anything not clearly below. |
| `BURUNDI_27A_ENROLMENT` | 27A enrolment, new farmers, groups, orders taken. | Enrolment, new members, order taking, 27A. |
| `BURUNDI_INPUT_RECONCILIATIONS` | DPIB, TMS/SAP/Kobo input reconciliation, site variances, price matrix. | Input reconciliation, stock variance, DPIB, TMS, SAP. |
| `BURUNDI_BIZOPS_26B` | A small 26B-specific offshoot. | Only if a 26B question fails in BURUNDI_BIZOPS. |
| `BURUNDI_ELVIS_BIZ` | AppSheet and Kobo pipelines, claims queues, 27A enrolment staging. Working project, not governed. | Named explicitly, or tracing where an AppSheet table comes from. |
| `ULRICH_1AF` | Cash vs mobile money, RvR, bank slips, Fineract reconciliation. Personal workspace. | Named explicitly. |
| `DSSTESTBART` | Sandbox and MCP diagnostics. Personal workspace. | Named explicitly. |

The last three are **individual working projects**. Numbers in them are drafts,
not agreed figures. Do not search them to answer a business question, and if a
figure comes from one, say so and say it is unverified.

`BURUNDI_BIZOPS_CDM` exists — the 26A Crédit & Underpayment dashboard lives
there — but is **outside this API key's scope**. If a question needs it, say
the project is not accessible to the agent and that the key needs widening.
Do not retry it.

Two error messages, two meanings:

- `Action forbidden` — the project exists, the key cannot reach it. Report it
  and name the project.
- `Failed to read project permissions` — no such project. You invented the key.
  Stop and re-read this list; do not ask the user to supply one.

Never ask a business user for a project key. If you cannot place a question,
the missing thing is a **definition**, not a project — say which term is
undefined and ask what it should mean, per the glossary rules above.
```

---

## Where it goes

Paste into the agent description below the `## Business terms` block, so both
guardrails travel together.

It also belongs at the **second Routing block** (`AGENT_SETUP.md` §4), on the
*no match* branch. That branch currently asks which dataset is meant; the last
paragraph above is what stops it degrading into asking for a project key.

## Verifying a change

`search_project_objects` with any common search term is the cheapest probe:
`ok` means reachable, and the two `UnauthorizedException` messages distinguish
out-of-scope from non-existent. Re-run for every key in the table after a key
rotation or a scope change, and update the `verified` date here.

verified: 2026-08-06
