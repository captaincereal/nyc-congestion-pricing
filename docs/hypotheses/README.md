# Hypothesis protocol

This study is investigated across many sessions, by different models, with
different ideas. That is a strength — independent attempts on a hard
identification problem — and it carries one specific danger.

## The danger

The dataset is fixed. Every session that tries a specification against it is
another draw. Run enough specifications and one will look clean by chance, and
nothing in the result itself will tell you which kind it is. Keeping the
specification that worked, and quietly not counting the ones that did not, is
how honest people produce false findings. Roth (2022) shows the sharper
version of this: conditioning on a diagnostic passing can leave the surviving
estimate *more* biased than not testing at all.

The defence is not willpower. It is a written record, made before the result
exists, that a later reader can audit.

## The rule

**Every analysis that could change what the study reports gets a hypothesis
record, committed before it runs.**

Exploratory poking around does not need one. The line is whether the output
could end up in the README. If you would quote it, register it.

Two things in the record are frozen once results exist:

- **Prediction** — what you expect, stated before you know.
- **Acceptance criteria** — what result would count as support, what would
  count as refutation, and what would count as uninformative.

Editing either after seeing results is the failure this protocol exists to
prevent. Git history is the enforcement: the record is committed before the
analysis, so a later reader can check the commit order. If the criteria turn
out to be wrong, supersede the record with a new one that says so and explains
why. Do not rewrite it.

**That enforcement does not reach H001 through H004, and a reader should know
it.** `main` is an orphan history rooted at c573209 on 2026-09-12, and those
four records enter in that root commit already carrying their Results. There is
no order on `main` to check for them. For H001, H002 and H003 the order is
demonstrable on the `codex/verify-then-aggregate` branch; for H004 it is not
demonstrable anywhere. From H005 on, the registration commits are on `main` and
the mechanism works as written. The 2026-09-14 entry in
`docs/decision_register.md` has the detail and the commit hashes.

## Reporting

A hypothesis that fails is recorded with the same care as one that succeeds,
and stays in the register. `REGISTER.md` is append-only. The count of
registered hypotheses is itself a result: fifteen attempts with one clean
finding means something different from one attempt with one clean finding, and
the reader is entitled to know which they are looking at.

## Files

| File | Purpose |
|---|---|
| `REGISTER.md` | The index. Every hypothesis, its status and verdict. Append-only. |
| `TEMPLATE.md` | The form to copy. |
| `H0NN-slug.md` | One hypothesis. |
| `H0NN-execution-prompt.md` | A prompt written to hand a hypothesis to a fresh session. Not a record, and not listed in the register. |

Outputs belong to their hypothesis: write tables and figures as
`outputs/tables/H0NN_*.csv` and `outputs/figures/H0NN_*.png` so results cannot
be confused across specifications, and so a superseded hypothesis's artefacts
are identifiable.

## Workflow

1. In a session that holds the project context, invoke the `research-prompt`
   skill. It writes the hypothesis record and emits a prompt.
2. Commit the record. This is the pre-registration step and the order matters.
3. Paste the prompt into a fresh session — a branch, or another model. Starting
   clean is deliberate: a session that already argued for an approach is a poor
   judge of it.
4. That session does the work and fills in Result and Verdict.
5. Update `REGISTER.md`.

Handing the prompt to a model that did not write it is the closest thing here
to an independent replication. Use it.
