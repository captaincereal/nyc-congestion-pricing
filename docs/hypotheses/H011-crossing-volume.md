# H011 — Did tolling reduce vehicle volume entering the zone, measured at the crossings?

| | |
|---|---|
| **Status** | answered — **refutes** |
| **Registered** | 2026-09-15 |
| **Registered by** | Claude Opus 5, the session that ran the source survey. **Has seen no outcome data from this source** — see Prediction. |
| **Answered by** | Claude Opus 5, 2026-09-15 — **the same session that registered it**, at the owner's direction. See Verdict. |
| **Supersedes / superseded by** | none |

## Question

The study has never been able to ask whether the toll reduced the number of
vehicles entering the zone, because the MTA's zone-entry feed begins on the
tolling date. The 2026-09-15 source survey found a feed that does not:
**`ebfx-2m7v`, MTA Bridges and Tunnels Hourly Crossings, beginning 2019** —
13,514,755 rows by facility, direction, hour and vehicle class, running
2019-01-01 to 2026-09-01.

Two of that operator's facilities are entry points to the Congestion Relief
Zone and the rest are not. Did inbound volume fall at the CRZ-bound crossings
relative to the operator's others, and by how much?

## Why it matters

This is the question the public argument is actually about, and no part of this
study has been able to touch it. The entry feed has no before; the speed panel
cannot identify anything; the secondary feed's sensors are dark.

It also gets a comparison group of a kind this project has never had. The
control crossings are run by the same agency, counted by the same equipment,
reported in the same file, over the same dates. Every previous control group
here was "similar streets", chosen by the analyst and rejected out of sample
three times.

If volume fell at the CRZ-bound crossings and held elsewhere, the study has its
first causal estimate of anything the policy was built to do. If it did not, a
widely repeated claim about congestion pricing loses its most obvious support,
which is equally worth reporting.

**Scope disclosure.** `docs/project_brief.md` lists volume as out of scope for
the core analysis and admits it only as a Phase 10 mechanism check. This record
goes beyond the frozen scope deliberately and says so rather than quietly
widening it. The frozen speed question stays closed and nothing here reopens it.

## Prediction

*Frozen once results exist.*

**The disclosure that matters, and it is the opposite of the last four
records.** H007, H008, H009 and H010 each had to disclose that their author had
already seen the numbers being tested. **This author has seen none of this
source's data.** What has been seen is the metadata the survey collected: the
dataset's name, its columns, its row count and its date range. No crossing count
at any facility on any date has been observed, by this session or by anything
else in this repository. That makes this the first clean pre-registration on the
thread, and a reader should weight it accordingly.

What I expect, and how strongly:

**Direction** *(not measured)*. Inbound volume falls at the CRZ-bound crossings
relative to the others. I hold this at about 85%. It is the single most
plausible prediction in the project — a price rose and quantity should fall —
and its strength is why the magnitude matters more than the sign.

**Magnitude** *(not measured)*. Somewhere between 2% and 12%, held loosely at
about 60%. The reasoning is that a tunnel toll is a small share of the total
cost of the trips using it, that some traffic reroutes to free crossings rather
than disappearing, and that the two CRZ-bound tunnels were already tolled before
the CRZ charge was added on top, so the price change is a marginal increase
rather than a new charge.

**Pre-trend quality** *(not measured)*. I expect the restricted pre-period to
look far better than anything the link panel produced, at perhaps 65%. The
crossings are fixed physical assets counted by one system, which removes the
sensor-attrition and roster-churn problems that dominate the speed feed. What I
cannot predict is whether the two CRZ-bound tunnels track the outer-borough
bridges closely enough, since they serve different trip types.

**Vehicle class** *(not measured)*. If a response exists it should sit in the
classes H008 found responsive — cars and motorcycles — with trucks flatter. I
hold this at 60%: freight crossing a tunnel has less discretion than freight
choosing an entry minute, so the H008 pattern may not carry over.

**Substitution to free crossings** *(not measured, and it cuts against the
design)*. Traffic pushed off a tolled tunnel may appear on a control crossing,
which makes the control partly treated and inflates the estimate. This is the
same weakness H009 had with the exempt roadways. It is stated now so it cannot
be discovered later as a convenience.

## Method

**Data.** `ebfx-2m7v` on `data.ny.gov`, via `src.analysis.h008_toll_timing._fetch`
or an equivalent cached Socrata aggregate, cached under `data/raw/`.

**Treatment assignment is read off the data, never assumed.** Pull the distinct
`facility` values first and classify each as a CRZ entry point or not, citing
`docs/project_brief.md`, which names the Hugh L. Carey and Queens–Midtown tunnel
approaches as CRZ-excluded roadways, and H009's detection groups, which include
the Carey Tunnel. **Write the classification down before estimating anything.**
Assuming which crossings enter the zone is the D3 error in a new place, and D3
turned on exactly this kind of inference.

**Sample.** Inbound direction only — a crossing counted outbound measures
vehicles leaving. Confirm from the data which `direction` value is inbound
rather than assuming the label.

**Outcome.** `log(1 + monthly inbound crossings)` per facility × month. Monthly
rather than hourly for the primary, because the question is about volume and an
hourly panel would invite the serial-correlation problem H003 documented.

**Pre-period, restricted in advance and for a stated reason.** 2023-01 through
2024-12, the 24 months the frozen brief asks for. The pandemic is a differential
shock to Manhattan-bound crossings orders of magnitude larger than a toll, and
including it would make the largest pre-treatment violation enormous, which
mechanically drives any Rambachan–Roth breakdown value toward zero. **The full
2019-01 history is reported as a sensitivity and is expected to look much
worse**, so nobody can read the restriction as having been chosen for its
answer.

**Post-period.** 2025-02 through the latest complete month. January 2025 is a
transition month — tolling began on the 5th — and is excluded from the primary
and reported as a sensitivity.

**Estimator.** Two-way fixed effects on facility and month, standard errors
clustered by facility, plus an event study in event-months. Feed the event-study
coefficients and their full cluster-robust covariance to the existing
Rambachan–Roth machinery in `src/analysis/honest_did.py`.

**Inference, and the honest problem with it.** There are nine facilities and two
treated, so cluster-robust asymptotics cannot be trusted — the same regime
H007's verdict flagged at nine treated clusters, and worse. Randomization
inference over facility assignment gives C(9,2) = 36 possible assignments, so
the finest achievable one-sided p is 1/36 ≈ 0.028. **Report the randomization
distribution and treat the clustered standard errors as the weaker number**,
as H001 and H007 both concluded.

**Cuts.** By vehicle class; by facility; by year. A secondary triple-difference
on the hour-of-day profile — facility × hour × post — is reported descriptively
and is not part of the primary.

**Outputs.** `outputs/tables/H011_*.csv`, `outputs/figures/H011_*.png`.

## Acceptance criteria

*Frozen once results exist.*

Primary is the **Rambachan–Roth breakdown value** on the restricted pre-period,
with the point estimate beside it. The breakdown value is chosen because it is a
magnitude, because H002 and H005 already report it on the link panel — 0.005 to
0.171 — so this number is directly comparable to what the failed design achieved,
and because Roth (2022) is the reason not to gate on a pre-trend test.

**Supports** — the toll reduced inbound volume at the crossings it applies to.
Both:

1. **Breakdown value M ≥ 1.0.** The estimate survives post-treatment violations
   as large as the largest violation already visible in the restricted
   pre-period.
2. **The point estimate is a fall of at least 2%**, and the randomization
   distribution puts it outside the middle 90% of facility reassignments.

**Refutes** — this source cannot support the claim either. Any one of:

1. **M < 0.3.** No better than the link panel by any margin worth the ingestion.
2. **The point estimate is smaller than 1% in absolute value.** A change that
   small is not what the public argument is about, whatever its sign.
3. **The estimate is positive** — inbound volume rose at the tolled crossings
   relative to the others — **and M ≥ 0.3**, so the wrong-signed result is not
   merely noise.

**Uninformative** — M lands between 0.3 and 1.0, or the randomization
distribution is too coarse to place the estimate. With 36 possible assignments
this is a live possibility rather than a formality. Report M, the estimate, the
randomization distribution and the implied minimum detectable effect, and say
plainly that the design could not separate the hypotheses.

### Satisfiability, checked before these were frozen

Three criteria failures in this project shared one shape: a bar a true effect
could not clear. The rule installed by H010's amendment is to plant a true effect
of the expected size and confirm the criterion fires. Planting effects in a
synthetic event study of this shape, with the existing `honest_did` machinery:

| Planted effect | Pre-period month-to-month wobble (sd) | Breakdown M |
|---:|---:|---:|
| −3% | 0.002 | 0.93 |
| −3% | 0.005 | 0.38 |
| −6% | 0.002 | **2.44** |
| −6% | 0.005 | 0.97 |
| −10% | 0.002 | **4.45** |
| −10% | 0.005 | **1.78** |
| −10% | 0.010 | 0.89 |

So **M ≥ 1.0 is reachable and demanding**: it needs the effect to run roughly ten
to thirty times the residual month-to-month wobble. An effect in the middle of
the predicted 2–12% range clears it if the crossings are as stable as fixed
counting equipment should make them, and misses it if they are not. That is the
bar doing its job rather than being unreachable, and the table is here so a
reader can check that claim rather than take it.

## Amendment, 2026-09-15 — before execution, after the roster stage

*The criteria above are retained as frozen. This changes the outcome definition
and corrects a count, and it was written after stage one returned the facility
list and before any estimate existed. The gate between the two stages exists to
make exactly this possible.*

### What the roster showed

**There are ten facilities, not nine.** The Robert F. Kennedy Bridge appears
twice, as Bronx (`facility_id` 21) and Manhattan (22) plazas. So randomization
enumerates **C(10,2) = 45** assignments and the finest achievable one-sided p is
**0.022**, where the frozen text says 36 and 0.028. A factual correction.

**"Inbound direction only" is not well defined, and the Method said it was.**
The feed carries fifteen distinct `direction` labels across ten facilities, each
facility with its own. Neither direction of the Cross Bay or Marine Parkway
bridges reaches Manhattan at all, so there is no facility-independent notion of
inbound to filter on.

### What changes

**The primary outcome is total monthly crossings per facility, both
directions.** It is the least arbitrary comparable measure: mixing a
direction-specific count at the treated tunnels with an all-direction count at
the controls compares different quantities.

**This dilutes the effect and the record says so now rather than later.** The
charge applies to one direction of the two treated tunnels, so summing both
roughly halves what is measurable. A true 6% fall on the charged direction shows
up as roughly 3% here, which sits at the lower edge of the 2–12% predicted range
and near the 2% support floor. That is a real loss of power, accepted because the
alternative is an incomparable outcome.

The Manhattan-bound direction at the two treated tunnels is reported as a
**secondary, descriptive** cut via `--direction`, and is not scored.

**No magnitude in the criteria changes.** 0.05, 0.02, 1.0, 0.3 and the 90% band
all stand, as does the Prediction.

### The classification, committed before estimating

`docs/h011_facility_classification.csv` carries all ten facilities with a
`source` for each. Two are treated: **Hugh L. Carey Tunnel**, northbound to
Manhattan landing at the Battery, and **Queens Midtown Tunnel**, westbound to
Manhattan landing near 36th Street. Both are named in `docs/project_brief.md`
and the Carey Tunnel is one of H009's detection groups.

Three exclusions are worth stating because they are judgements rather than
readings. **Henry Hudson** does reach Manhattan, at Dyckman Street, far above
the cordon. **RFK Bronx** records directions that combine destinations — "to
Manhattan or Bronx" — which cannot be split, and its Manhattan leg lands at
125th Street in any case. **RFK Manhattan** records only an outbound direction.

### The author problem, stated again

This amendment was written by the record's author, as H010's was. It changes an
outcome definition rather than a threshold, it was made before any estimate
existed, and it reduces the measurable effect rather than enlarging it. A
sceptical reader should check that last point, which is the one that matters.

## Data required

One Socrata aggregate against a public dataset, no cost, no dependency on the
backfill or the release. The speed archive is not touched.

## Result

Answered 2026-09-15. `python -m src.analysis.h011_crossing_volume --stage estimate`,
dispatched to a hosted runner.

**Panel.** 440 facility-months: 10 facilities over 44 months, 2023-01 to
2026-09, with 2025-01 excluded as the transition month. Two facilities treated,
eight control, from the committed classification.

**The estimate.** Total monthly crossings at the two CRZ-bound tunnels fall
**4.31%** relative to the operator's other crossings
([H011_criteria.csv](../../outputs/tables/H011_criteria.csv)): −0.0440 log
points. That sits inside the record's predicted 2–12% range, and roughly doubles
if the both-directions dilution is taken at face value.

**Randomization inference is as strong as this design permits**
([H011_randomization.csv](../../outputs/tables/H011_randomization.csv)). Across
all 45 facility reassignments the observed estimate is **the most extreme**, at
a share of 1/45 = 0.022, against a 90% band of [−0.0291, +0.0243].

**The breakdown value is 0.034**, against a support bar of 1.0 and a refutation
floor of 0.3.

**The event study says why** ([H011_event_study.csv](../../outputs/tables/H011_event_study.csv)).
The 23 pre-period coefficients wander between **−0.111 and +0.032** with a
standard deviation of 0.043, the largest month-to-month first difference being
0.060. The treated tunnels were already moving against the control bridges,
before the toll existed, by more than the post-period effect. The 20 post
coefficients average −0.064 and range −0.165 to −0.009.

**And the post path is a hump rather than a step.** It runs −0.035 at the first
month, deepens to −0.122 by the sixth, then returns to −0.032, −0.011 and −0.009
by months eight to ten. A persistent price effect on a fixed crossing should
look like a level shift. This does not.

## Verdict

**Refutes**, on criterion 1 as written: the breakdown value of 0.034 is below
the 0.3 floor.

**The comparison the record was built to make.** H002 and H005 report
Rambachan–Roth breakdown values of 0.005 to 0.171 on the link panel. This gives
**0.034 — squarely inside that range.** The crossings feed has six years of
pre-period, one operator, one counting system and fixed physical assets, and on
the statistic that measures whether a design can survive plausible differential
drift it is **no better than the speed panel it was meant to improve on.**

**The point estimate and the inference are both fine, and neither is the
problem.** −4.31% is a plausible magnitude, and being the most extreme of 45
reassignments is the strongest randomization result available here. What fails
is the same thing that failed six times before: the treated and control units
were not on parallel paths beforehand. A pre-period excursion to −0.111 around
mid-2024, recovering by the toll date, is larger than the effect being claimed.

**The hump makes it worse rather than better.** An effect that deepens for six
months and then substantially disappears by month ten is hard to tell from the
pre-period wandering that surrounds it, and it is not the shape a permanent
change in the price of entry should produce.

**What this does not say.** That volume did not fall. A 4.3% fall may well be
real, and the randomization result is genuinely the cleanest this project has
produced on a volume outcome. What the breakdown value says is that this design
cannot separate it from drift the data already show, which is a statement about
the comparison rather than about the world.

**What would change it.** Control crossings that track the treated tunnels
before the toll. The eight used here serve different trip types — outer-borough
commuting and Staten Island traffic against two Manhattan tunnels — and that
difference, not the counting, is what the pre-period exposes.

**On who ran this.** The record's author ran it, at the owner's direction, which
the Prediction's disclosure about clean pre-registration does not cover. The
mitigation is that the verdict is mechanical: criterion 1 is a threshold on one
number, that number is 0.034, and the floor of 0.3 was frozen before any data
was fetched. There was no label to choose.

## Notes

**What this cannot establish.** That the toll improved speeds, reduced
congestion, or changed travel times. It measures vehicles crossing nine fixed
points, and a vehicle that reroutes to a free crossing and still enters the zone
counts as a reduction here while changing nothing on the street.

**Why not the CBD speed series, which is closer to the frozen question.** The
survey found `6p29-6xqn`, monthly taxi and for-hire speeds for the CBD, areas
adjacent to it and the rest of the city, back to October 2019. It is the nearest
thing in the inventory to the study's actual question and it was the first
candidate for this record. Its 213 rows are **exactly 71 months × 3 zones**, so
it carries **one treated unit and two controls**. With one treated unit, time
fixed effects and treated-specific event-time coefficients are collinear, and
permutation inference offers two placebos. It can describe the three series and
it cannot identify anything. That is worth a short descriptive note somewhere and
it is not worth a hypothesis, and saying so is cheaper than discovering it after
an ingestion.

**On the count.** This is the eleventh registered hypothesis and the first
against this source. Ten previous records have run against three other sources,
and a reader weighing this one should know the study has been looking for a long
time. What distinguishes it is stated in the Prediction: its author has seen none
of the data it tests.
