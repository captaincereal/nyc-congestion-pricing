# H0NN — <short title>

| | |
|---|---|
| **Status** | proposed / running / answered / superseded / abandoned |
| **Registered** | YYYY-MM-DD |
| **Registered by** | session or model that wrote this |
| **Answered by** | session or model that ran it |
| **Supersedes / superseded by** | H0NN, or none |

## Question

One or two sentences. A question with a possible answer, not a topic.

## Why it matters

What changes about what the study reports, depending on the answer. If nothing
changes either way, this is not worth registering — say so and stop.

## Prediction

*Frozen once results exist.*

What you expect, and roughly how strongly. "No idea" is a legitimate and useful
entry; a genuinely open question is worth more than a confirmation. What is not
legitimate is filling this in afterwards.

## Method

The specification, the estimator, the sample, the inference procedure. Enough
that someone else could implement it from this alone.

## Acceptance criteria

*Frozen once results exist.*

Three outcomes, decided in advance:

- **Supports** — what result would count as support.
- **Refutes** — what result would count against.
- **Uninformative** — what result would mean the test could not distinguish
  them. Name this one honestly; wide confidence intervals around zero are not
  evidence of no effect, and a test that cannot separate the hypotheses is a
  real and reportable outcome.

## Data required

What the analysis needs, and whether it is on hand. If it is blocked on the
backfill, say which months.

## Result

*Filled in after running. Leave empty until then.*

Numbers, with uncertainty. Where the artefacts are.

## Verdict

*Filled in after running.*

Which of the three criteria was met, and what it changes. If the criteria
turned out to be poorly chosen, say so plainly — and supersede this record
rather than editing the frozen sections above.

## Notes

Anything a later reader needs: implementation surprises, assumptions made in
passing, things that looked wrong and turned out not to be.
