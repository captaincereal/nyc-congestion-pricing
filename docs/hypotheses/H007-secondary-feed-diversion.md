# H007 — Can the secondary highway feed identify diversion onto toll-exempt in-zone routes?

| | |
|---|---|
| **Status** | proposed |
| **Registered** | 2026-09-13 |
| **Registered by** | Claude Opus 5, session picking up `docs/agent_handoff.md` |
| **Answered by** | |
| **Supersedes / superseded by** | none |

## Question

The primary E-ZPass panel contains no units where diversion would show: the five
`boundary` links straddle 60th Street, and the nearest control link is about
808 m from the cordon. The secondary DOT Traffic Speeds feed (`i4gi-tjb9`) does
contain them — nine links on the FDR Drive, the West Side Highway / 12th Avenue
and West Street, all inside the zone and all exempt from the toll. Those are the
roads a driver uses to cross Manhattan without paying.

Can that feed identify whether traffic diverted onto them after 2025-01-05?

## Why it matters

The README currently reports the spillover question as unanswerable on the
primary roster rather than answered in the negative, and Phase 10 has never run.
Either answer changes the writeup.

If the feed identifies diversion, the study gains a mechanism section with an
estimate, and the spillover limitation narrows from "no units" to "no units in
the primary feed, but the secondary feed covers the exempt routes and says X".

If it does not, the limitation is confirmed on the one source that was supposed
to rescue it, and the study reports a second documented failure to identify —
this time for a reason that may be about measurement rather than about parallel
trends. That distinction is worth having in writing, because it says different
things about what better data would fix.

## Prediction

*Frozen once results exist.*

I expect this to fail, for two reasons, and I hold the second more strongly than
the first.

The weaker reason is the pattern of the study: the joint pre-trend test has
rejected in every sample and on every control set tried so far, and highways in
other boroughs are not obviously a better comparison for the FDR than
Manhattan surface streets were for each other. I expect the pre-trend test to
reject here too, at perhaps 60–70% confidence.

The stronger reason is measurement. Exploratory inspection of the raw feed
before writing this record (see Notes — this ordering matters and is disclosed
deliberately) shows that readings coded `speed = 0` carry `travel_time = 0` and
`status = -101`, and that their frequency peaks overnight rather than at rush
hour. They are outages, not standstills. Their share on the nine exempt in-zone
links runs 16% in 2023, 33% in 2024, 42% in 2025 and 50% in 2026, while the
control links hold flat near 17–20% throughout. If that holds up under the
per-hour, per-link accounting this analysis will do, the treated group's
observation set is being selected differently over time from the control group's,
and no fixed-effects estimator repairs that. I put roughly 85% on the
availability criterion below being breached.

I do not have a prediction for the sign or size of the ATT and am not
formulating one, because I expect the diagnostics to make it unreadable. If
forced: diversion onto exempt roads implies *slower* speeds there, so a negative
coefficient, but I would not bet on recovering it.

What would genuinely surprise me: flat pre-trends on this feed. Highway links
are more homogeneous than surface streets, and it is possible that the
comparison works better here than anything tried on the primary panel. That is
the case worth being open to, and it is why this is worth running rather than
asserting.

## Method

**Panel.** Build `data/processed/secondary_hourly_panel.parquet` with the same
schema the primary panel uses, so `src/analysis/did.py`,
`src/analysis/event_study.py`, `src/analysis/placebo_space.py` and
`src/analysis/honest_did.py` run against it unmodified. One row per
link × hour.

**Window.** 2023-01-01 through 2026-05-31. The feed holds 2023-01 … 2026-07 but
**2026-06 is missing**, so the window stops at 2026-05 to stay contiguous;
2026-07 is dropped rather than leaving a hole mid-panel. That gives 24
pre-treatment months and 17 post-treatment months, against the primary panel's
23 and 4.

**Outcome.** Hourly median of `speed`, in mph, over readings with `speed > 0`.
Zero-speed readings are dropped as missing, not averaged in as 0 mph. They carry
`travel_time = 0` and `status = -101`, and `AGENTS.md` already requires missing
numeric values to be `NaN` rather than `0`. An hour with no positive reading is
absent from the panel, not zero.

**Groups**, from `src.data.geo.classify_segment` on the decoded
`encoded_poly_line` (precision 5), never on `link_name`:

- **Treated** — the 9 `exempt_in_zone` links: FDR N/S between Catherine Slip and
  25th St, FDR S Catherine Slip to the Brooklyn Bridge, 12th Ave N 40th–57th,
  12th Ave S 57th–45th, 11th Ave s Gansevoort to West St, West St S Spring St to
  the BBT portal, and the two BBT Manhattan portal/toll-plaza links.
- **Control** — the 116 `control` links, all outside Manhattan.
- **Held out of both** — the 6 `boundary` links (they cross the 60th St line),
  the 5 `crossing` links (Lincoln Tunnel tubes and the Brooklyn Bridge / FDR
  connector: these measure the queue to enter, a different behaviour), and
  link_id `4616339` and `4616340`. Those last two are labelled
  `borough = Manhattan` but their geometry lies mostly in Brooklyn; they are
  approaches to the Brooklyn and Manhattan Bridges. `classify_segment` calls
  them `treated` because it trusts the borough label — see Notes. They are
  neither clean diversion receivers nor clean controls, so they are excluded and
  the exclusion is reported.

**Estimator.** Two-way fixed effects on link and hour-of-sample, as
`src/analysis/did.py` implements it, with `treated × post` the coefficient of
interest. Samples: all, weekday peak, weekday off-peak, weekend, matching the
primary cuts.

**Inference.** Randomization inference is **primary**, not a supplement. Nine
treated clusters is far below where cluster-robust asymptotics are trustworthy,
and H001 already measured those standard errors running up to 1.5× too tight on
a panel with 333 clusters. Reassign treatment at random among control links,
9 at a time, 500 draws, and report the share of draws producing an effect at
least as extreme. Cluster-robust standard errors are reported alongside, clearly
labelled as the weaker of the two.

**Diagnostics**, in this order, because an earlier one failing makes the later
ones unreadable:

1. **Availability.** Per group per month, the share of link-hours with at least
   one positive reading, out of hours where the link appears in the feed at all;
   and the count of links reporting. Compare the pre-mean to the post-mean for
   each group and take the difference in differences of those shares. Report the
   link roster entering and leaving the feed.
2. **Event study** by month, ±12 months around 2025-01-05, then the joint Wald
   test that all pre-treatment leads are zero, using the full cluster covariance
   (`event_study.pretrend_test`, method `cluster_robust_wald_chi2`). The
   corrected test, not the superseded sum-of-squared-t version.
3. **Rambachan & Roth (2023)** breakdown value via `src/analysis/honest_did.py`,
   at the ±12-month horizon.

**Outputs.** `outputs/tables/H007_*.csv` and `outputs/figures/H007_*.png`, per
the namespacing rule. Both analysis modules take `--out-prefix`.

## Acceptance criteria

*Frozen once results exist.*

Evaluated on the **all-hours** sample, with the other three cuts reported.

**Supports** — the feed identifies diversion. All three must hold:

1. The differential change in valid-hour availability between treated and
   control, pre-period mean to post-period mean, is **under 5 percentage
   points** in absolute value.
2. The joint pre-trend test **fails to reject** at the 5% level.
3. The randomization-inference p-value for the observed ATT is **below 0.05**.

If all three hold, the sign of the ATT is the finding: negative means measured
diversion onto the exempt routes, positive means the opposite.

**Refutes** — the feed does not identify diversion. Any one of:

1. The differential availability change is **5 percentage points or more**. The
   groups' observation sets are moving apart; the comparison is between
   different samples of hours, not different roads.
2. The joint pre-trend test **rejects** at the 5% level.
3. The Rambachan–Roth breakdown value is **below 0.5**, meaning the estimate
   survives only violations less than half the size of those already visible
   before the toll.

**Uninformative** — availability is parallel and the pre-trend test passes, but
the randomization-inference p-value is at or above 0.05 and the null
distribution is wide enough that a diversion effect of the size the toll
plausibly produced would not have been detected. This is the honest third
outcome and it must be reported as such: nine treated links is a small design,
and failing to find an effect in it is not evidence that none occurred. If this
is the verdict, report the minimum detectable effect alongside it.

The 5-percentage-point availability bar is set on the reasoning that the primary
study's headline effect was 1.17 mph on a pre-treatment treated mean near
10 mph, about 12%. A differential shift of 5% of observations between hours of
the day moves a group's mean hourly speed by more than that, because the spread
between the fastest and slowest hours on these links is far wider than 12%. A
selection effect able to manufacture the entire effect being estimated
disqualifies the design.

## Data required

All on hand. Nothing is blocked on the backfill.

- `data/raw/dot_speeds/*.parquet` — 42 monthly parts, 42.2M rows, 2023-01 …
  2026-07 with 2026-06 absent. 138 distinct links.
- `src/data/geo.py` — classifier, unchanged.
- No new ingestion, no network, no cost.

The primary E-ZPass archive is **not** required. This analysis does not touch it
and does not wait for 2023-01 or the post-period extension.

## Result

*Filled in after running. Leave empty until then.*

## Verdict

*Filled in after running.*

## Notes

**Disclosure on ordering.** The zero-speed diagnosis described under Prediction
was done *before* this record was written, as exploratory work to establish
whether the analysis was feasible at all. It is disclosed rather than hidden,
because the 5-percentage-point availability criterion was written by someone who
already knew the raw yearly zero rates diverged by roughly 25 points. The
criterion is not tuned to that number — any threshold below about 20 points
returns the same verdict — but a reader is entitled to know the order things
happened in. No difference-in-differences, event study, or any estimate of the
ATT has been run on this feed. The prediction above was written with no estimate
in hand.

**Why zeros are outages.** Three independent signatures, measured on the full
42.2M rows: `travel_time` is 0 for 9,128,628 of 9,129,474 zero-speed readings
(a genuine standstill has a large travel time, not a zero one); `status` is
`-101` on every one of them; and the zero rate peaks overnight, 56% at 03:00
against 38% through the afternoon, which is the inverse of the congestion
pattern. The existing `src/analysis/spillover_diagnostics.py` filters only
`speed_mph IS NOT NULL` and therefore averages these in as 0 mph. Its committed
output `outputs/tables/spillover_secondary_monthly.csv` is contaminated by this
and should be treated as superseded by whatever this analysis produces.

**The primary panel is not affected.** Checked directly: zero-speed readings are
at most 0.014% of observations in any `treatment_group × post` cell of
`data/processed/hourly_panel.parquet`. This is a secondary-feed problem and
nothing in the README's headline finding rests on it.

**`classify_segment` trusts the borough label.** `geo.py` defines
`_in_manhattan_envelope` and its docstring calls it "the geometric backstop",
but `classify_segment` never calls it — the function has no call sites. For the
primary feed this is harmless: all 176 Manhattan-labelled E-ZPass segments lie
inside the envelope. On the secondary feed it mislabels the two BQE bridge
approaches, which is why they are held out explicitly above rather than left to
the classifier.

**Link roster is unstable.** `AGENTS.md` records that 25 sensors stopped
reporting in autumn 2024 and never returned. The control group here falls from
115 reporting links in 2023 to 102–103 from 2024 on. The panel is unbalanced and
must be treated as such; the availability diagnostic exists partly to measure
this.
