---
name: research-prompt
description: Turn accumulated project context into ONE pre-registered research prompt to hand to a fresh session or a different model. Use whenever the user wants to test a hypothesis, try an alternative specification, chase down why a result looks the way it does, or hand an open question to another chat — and especially when they say "what should we test next", "write me a prompt for", "branch a chat to look at", "make a prompt I can paste", or are about to run a new analysis against data they have already looked at. The output is a prompt, not an answer. It exists to stop the garden of forking paths, so prefer it over answering the question directly whenever the analysis could change what a study reports.
---

# Research prompt

You are writing a prompt for someone else to execute — a fresh session, often a
different model. You are not doing the analysis.

That separation is the point. A session that has already argued for an approach
is a poor judge of it, and a session carrying the full history of a project
inherits its assumptions along with its facts. Handing a clean prompt to a model
that did not write it is the closest thing available to an independent
replication.

## Why this skill exists

The dataset is fixed. Every specification tried against it is another draw. Run
enough and one looks clean by chance, and nothing in the result itself reveals
which kind it is. Keeping the specification that worked while not counting the
ones that did not is how careful people produce false findings.

The defence is a record written *before* the result exists. So this skill
produces two artefacts, in this order:

1. **A hypothesis record**, committed before the analysis runs. Its prediction
   and acceptance criteria are frozen from that moment.
2. **A prompt**, which the user pastes elsewhere.

If the project has a hypothesis protocol (look for `docs/hypotheses/README.md`),
follow it and use its template and numbering. If it does not, create the record
anyway as a single markdown file next to the analysis, and mention that the
project might want a protocol.

## Step 1 — Find the real question

Read the conversation and the repo state. You are looking for a question whose
answer would *change what the project reports*. Most things that feel like open
questions do not clear that bar.

Test each candidate against three filters:

- **Decision relevance.** If both possible answers lead to the same write-up,
  drop it. Say so rather than registering it.
- **Answerable now.** Prefer questions answerable with data on hand. A question
  blocked on a pending ingest is worth registering with its blockage named, but
  do not let it crowd out work that could run today.
- **Not already answered.** Check the register and the decision log. Re-running
  a settled question wastes a session and inflates the multiplicity count.

Pick **one**. A prompt asking for four things gets four shallow answers. If
several questions deserve attention, say so and offer to write the others as
separate prompts — that is the workflow, not a limitation of it.

When the user has named the question, take it. When they have not, propose the
one you would pick and say briefly why it beats the alternatives.

## Step 2 — Write the hypothesis record

Fill the project's template. Two fields carry the weight:

**Prediction.** What you expect, before knowing. "No idea" is a legitimate and
valuable entry — a genuinely open question is worth more than a confirmation.
What is not legitimate is leaving it vague so that any result can be read as
consistent with it.

**Acceptance criteria.** Three outcomes decided in advance: what supports, what
refutes, and what would mean the test could not distinguish them. Name that
third one honestly. A wide confidence interval around zero is not evidence of no
effect, and a test too weak to separate the hypotheses is a real outcome that
must be reportable as one. Designs that can only confirm are not tests.

Commit the record before the analysis runs. The commit order is the evidence.

## Step 3 — Write the prompt

The prompt goes to a session with no memory of this conversation, so it must
carry its own context. Assemble it from this shape:

```
## What you are doing
One paragraph: the question, and what changes depending on the answer.

## What you need to know
The project state relevant to THIS question. Not a tour of the repo —
the specific facts, numbers and file paths needed. Name the files worth
reading rather than pasting their contents.

## The hypothesis, pre-registered
Point at the record. State the prediction and the three acceptance
criteria inline so they cannot be quietly reinterpreted.

## Method
What to run. Leave implementation choices open where the executing
session is better placed to make them; pin down anything that would
change what the result means.

## Constraints
Budget, runtime, environment, dependencies. Carry these forward
explicitly — a fresh session cannot infer them.

## What to report
The numbers with their uncertainty, which acceptance criterion was met,
what it changes, and what it does not settle.

## Boundaries
What this analysis cannot establish, so the executing session does not
overclaim on your behalf.
```

Four things earn their place in almost every prompt of this kind:

**Separate the estimator from the inference.** Most reviews collapse them and
miss the whole class of problems where the point estimate is fine and the
standard errors are fiction. Ask about each explicitly.

**Ask what would change the conclusion, not what is wrong.** Ranking by severity
surfaces a list of caveats. Ranking by "what would move the answer" surfaces the
two things worth doing.

**Require the null to be reportable.** State plainly that a documented
non-result, or a documented inability to identify the effect, is a successful
outcome. Without that, a model will reach for something positive to hand back.

**Demand verifiable citations.** Models fabricate plausible references in
methodological domains, confidently and in correct format. Ask for author, year
and venue, and ask it to flag anything it cannot cite precisely rather than
guessing. Tell the user to spot-check.

## Step 4 — Hand it over

Output the prompt in a single fenced block so it can be copied whole. Say which
file holds the record and that it should be committed before the prompt is run.

Then stop. Do not begin the analysis, and do not speculate about how it will
come out — a prediction from you in the same breath as the prompt gives the
executing session an anchor to drift toward, which is exactly what the fresh
context was meant to avoid.

## Keeping it honest

- One question per prompt.
- Predictions and acceptance criteria are frozen once results exist. If the
  criteria turn out to be badly chosen, supersede the record with a new one
  explaining why. Do not edit them.
- Register failures and abandoned attempts with the same care as successes. The
  count of attempts is itself a result the reader is entitled to.
- If the honest answer to "what should we test next" is "nothing yet, this is
  blocked on X", say that instead of manufacturing a hypothesis. A prompt
  written to fill a slot wastes a session and adds to the multiplicity count for
  nothing.
