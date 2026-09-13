# H008 — Do drivers retime entries to avoid the peak toll rate?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5, session that completed the archive and answered H007 |
| **Answered by** | |
| **Supersedes / superseded by** | none |

## Question

The Congestion Relief Zone toll is not a single price. It is higher during a
peak window and discounted overnight, and the switch happens at a fixed clock
time — 05:00 and 21:00 on weekdays, 09:00 and 21:00 at weekends. Derived from
the feed itself, not assumed: `time_period` is `Peak` for hours 05–20 Monday to
Friday and 09–20 on Saturday and Sunday, `Overnight` otherwise.

Do drivers respond to that price by moving *when* they enter the zone?

## Why it matters

Every previous hypothesis here has asked whether the toll changed traffic
*conditions*, and the answer has been that this design cannot tell. That failure
is about the comparison group: treated and control streets were already drifting
apart, and no control construction repaired it.

This question does not need a comparison group. The counterfactual is the
minutes on the other side of a price change, so identification rests on a
discontinuity rather than on parallel trends — the assumption that killed
H001 through H006. It also uses a different dataset, so it is a fresh draw
rather than another pass at the speed panel.

If drivers do retime, the study gains its first positive, causally interpretable
finding: a measured behavioural response to congestion pricing. If they do not,
that is substantive too — a toll whose time structure changes nothing about
entry timing is evidence about how the policy actually operates.

Either way this does **not** revisit the speed finding. Retiming is not the same
as reduced congestion, and nothing here licenses a claim about speeds.

## Prediction

*Frozen once results exist.*

**Disclosure first, because it changes how this section should be read.** The
raw weekday discontinuities have already been seen. Exploratory scoping on
2026-09-13, before this record was written, aggregated all 20 months of weekday
entries into 10-minute blocks and found entries jumping **+10.8%** at 21:00
against a declining evening trend, and falling **−27.0%** at 05:00 against a
rising morning ramp — the two largest boundary movements of the day, and the
only two where a price changes. Predicting that those exist would be no
prediction at all. The criteria below are therefore set on quantities that have
**not** been measured, and each is marked.

What I have not looked at, and what I expect:

**The weekend 09:00 boundary** *(not measured)*. Weekends have a later peak
start. If the notch is a price response it must appear at 09:00 on Saturday and
Sunday and be absent at 09:00 on weekdays, where no price changes. I hold this
at about 80%, and it is the single most informative test here, because a daily
rhythm cannot know what day of the week it is.

**Placebo boundaries under a proper specification** *(not measured)*. The crude
scoping used a linear extrapolation of the previous hour's slope, which
misbehaves where the series curves — it flagged 06:00 at −12% purely because of
the morning ramp, and midnight at −14%, which is a calendar boundary rather than
a toll one. Under a local polynomial the toll boundaries should separate
cleanly from the other twenty-two. I hold this at roughly 70%; midnight is the
one I expect to survive as a genuine non-price discontinuity.

**Vehicle class** *(not measured)*. Trucks pay considerably more per entry than
cars, so the absolute saving from waiting is larger, and freight scheduling is
plausibly more responsive than commuting. I expect classes 2 and 3 to bunch
proportionally harder than class 1 — but I hold this weakly, at perhaps 60%,
because delivery windows may be contractually fixed in ways commuting is not.
A reversal here would be interesting rather than fatal.

**Detection group** *(not measured)*. The notch should appear at most of the
twelve entry points rather than being driven by one or two. If it is
concentrated in a single crossing, that points at a local artefact.

I do not have a prediction for the magnitude under the RD specification and am
not inventing one. The 10.8% raw figure conflates the notch with the ordinary
evening decline, and the specification is meant to separate them.

## Method

**Data.** MTA Congestion Relief Zone Vehicle Entries, `t6yz-b64h` on
data.ny.gov, 6,314,112 rows covering 2025-01-05 to the present. Entries are
already aggregated to 10-minute blocks — `minute_of_hour` takes values
0, 10, 20, 30, 40, 50 — which sets the finest available resolution and caps how
close to the cutoff the design can look. Columns used: `toll_date`,
`hour_of_day`, `minute_of_hour`, `day_of_week`, `time_period`, `vehicle_class`,
`detection_group`, `crz_entries`.

Pulled as Socrata aggregates rather than bulk-downloaded; nothing here needs the
row-level file. Cached under `data/raw/mta_crz/` so the run is reproducible.

**Estimand.** This is a bunching design at a price notch, not a conventional
regression discontinuity, and the difference matters for how it is read. In a
standard RD, manipulation of the running variable invalidates the design and a
density test is run to detect it. Here the running variable is clock time,
agents can manipulate it perfectly, and **that manipulation is the effect being
measured**. The McCrary logic is inverted: excess mass at the boundary is the
finding, not the threat. Framework as in Saez (2010) and the review in Kleven
(2016); local polynomial estimation follows Calonico, Cattaneo and Titiunik
(2014). Full citations under References, with a note on what was verified.

**Specification.** For each boundary *b* (24 of them, of which 2 are toll
boundaries on weekdays and 2 at weekends), on blocks within a ±60-minute
bandwidth — six 10-minute blocks either side:

    log(1 + entries_dt) = α + τ·post_t + f(m_t) + g(m_t)·post_t + δ_d + ε_dt

where `m_t` is minutes from the boundary, `post_t` indicates the far side,
`f` and `g` are local polynomials of order 1 (order 2 reported as a
sensitivity), and `δ_d` are date fixed effects so the estimate comes from
within-day variation rather than from day-to-day level differences. τ is the
log discontinuity. Standard errors clustered by date.

Bandwidth ±60 minutes and polynomial order 1 are chosen now and frozen. A ±30
and a ±90 minute bandwidth are reported as sensitivities, not as alternatives to
be selected among.

**Samples.** Weekday and weekend estimated separately throughout, because their
peak windows differ and that difference is the identifying test.

**Inference.** The placebo distribution is the primary yardstick, as in H001 and
H007. Estimate τ at all 24 boundaries in each sample; the toll boundaries are
judged against the distribution of the non-toll ones rather than against a
nominal p-value, because the underlying series has structure at every hour and a
t-statistic against zero would overstate significance.

**Cuts.** Overall; by `vehicle_class`; by `detection_group`.

**Outputs.** `outputs/tables/H008_*.csv` and `outputs/figures/H008_*.png`.

## Acceptance criteria

*Frozen once results exist.*

Evaluated on the **21:00 weekday** boundary as primary, with everything else
reported.

**Supports** — drivers retime to avoid the peak rate. All three must hold:

1. **Day-of-week discrimination.** At 09:00, the weekend estimate is negative
   (entries drop as peak begins) and the weekday estimate at the same clock time
   is smaller in absolute value by at least a factor of three. A daily rhythm
   cannot distinguish Saturday from Tuesday; a price can.
2. **Separation from placebos.** |τ| at both weekday toll boundaries exceeds the
   maximum |τ| across all non-toll boundaries in the same sample, excluding
   midnight, which is excluded in advance as a calendar boundary rather than
   discovered to be inconvenient.
3. **Sign.** τ is positive at 21:00 (price falls, entries rise) and negative at
   05:00 and weekend 09:00 (price rises, entries fall).

**Refutes** — the pattern is not a price response. Any one of:

1. The weekday 09:00 estimate is comparable to the weekend 09:00 estimate,
   meaning the notch tracks the clock rather than the toll.
2. A majority of non-toll boundaries show |τ| of the same order as the toll
   boundaries, meaning the series is discontinuous everywhere and the design
   cannot isolate anything.
3. The discontinuity is confined to one or two detection groups, indicating a
   local measurement artefact rather than a city-wide behavioural response.

**Uninformative** — the placebo distribution is wide enough that the toll
boundaries sit inside it without a majority of placebos being large, so the test
separates nothing. Report the placebo spread and the implied minimum detectable
discontinuity, and say plainly that the design could not distinguish the two
hypotheses at this resolution. Ten-minute blocks are coarse and this is a real
possibility, not a formality.

## Data required

All available, none blocked. No new ingestion beyond Socrata aggregate queries
against a public dataset, and no cost. The primary E-Z Pass archive is not used
and is not affected.

**Not required and deliberately not used:** the hourly speed panel. This
hypothesis does not touch it, and no result here bears on the speed finding.

## Result

*Filled in after running. Leave empty until then.*

## Verdict

*Filled in after running.*

## References

Cited with what was verified noted, per the project's standing rule that
anything not precisely citable is flagged rather than guessed:

- **Saez, Emmanuel (2010).** "Do Taxpayers Bunch at Kink Points?" *American
  Economic Journal: Economic Policy* 2(3). The bunching-at-a-notch framework
  this design borrows. Volume and issue believed correct; page range not
  verified here and should be checked before publication.
- **Kleven, Henrik Jacobsen (2016).** "Bunching." *Annual Review of Economics*,
  volume 8. Survey of the method and its identifying assumptions. Page range not
  verified.
- **Calonico, Sebastian, Matias D. Cattaneo and Rocío Titiunik (2014).**
  "Robust Nonparametric Confidence Intervals for Regression-Discontinuity
  Designs." *Econometrica* 82(6). Local polynomial estimation and bias-corrected
  inference. Page range not verified.
- **Roth, Jonathan (2022).** "Pretest with Caution." *American Economic Review:
  Insights* 4(3). Already relied on by this project's protocol; cited here
  because it is why the criteria above are frozen before the run.

The MTA toll schedule is taken from the dataset's own `time_period` column
rather than from the published tariff, so no citation to MTA tolling documents
is made. If the published schedule is ever quoted in the writeup, it must be
cited and checked, and any disagreement with the feed reported.

## Notes

**On the ordering.** The Prediction section discloses that the weekday raw
discontinuities were seen before this record was written. That is the second
time in this project — H007 did the same — and both times the reason was the
same: establishing whether an analysis is feasible at all requires looking. The
defence is that the frozen criteria rest on quantities not yet measured, each
marked in the Prediction, and that the most decisive of them, the weekend 09:00
boundary, has not been touched at all.

**What this cannot establish.** That the toll reduced congestion, that it
reduced total entries, or anything about speed. Retiming an entry is not
avoiding one. A driver who enters at 21:05 instead of 20:55 has responded to the
price without changing whether they drove, and the welfare and congestion
consequences of that are outside what this measures.

**Why not an RD on the tolling start date.** Because `t6yz-b64h` begins on
2025-01-05, the day tolling began, so it carries no pre-treatment period and can
support no before-and-after comparison. That is recorded in the README and is
why this design uses within-period price variation instead.
