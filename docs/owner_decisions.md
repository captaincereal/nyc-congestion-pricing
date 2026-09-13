# Decisions for the owner — 2026-09-12

The present data and comparison pool do not identify the toll's causal effect
on speed or diversion. This is a finding about the implemented design, not an
estimate of zero effect. The corrected joint pre-period tests reject in every
sample. The full frozen pre-period is still absent and the primary archive is
unverified. `decision_register.md` records the numerical evidence and code fixes.

The following recommendations are **not adopted**. The handoff explicitly
reserves D1–D7 to the owner. D4 was already resolved before this work.

## D1 — Retain the unfiltered median as primary; report quality sensitivities

Keep the current primary outcome and make minimum probe depth and an 80 mph
ceiling separate specifications. The expanded staging has 10.97% of readings
with at most three probes and 0.1125% above 80 mph; its maximum is 7,043.9 mph.
Those are sensor-quality problems, but their presence alone does not establish
which primary filter is appropriate. The sensitivity table includes hours
with at least three observations and a minimum of four probes per reading,
and a separate exclusion of hours containing any reading above 80 mph. These
are hour-level exclusions; they do not reconstruct the median after filtering
individual readings. No raw values have been changed.

## D2 — Develop controls using pre-treatment matching and held-out validation

Do not promote the naive pool or choose the control pool with the most
favorable post-treatment coefficient. Use the frozen 2023–24 archive to fit
controls on pre-treatment weekly speed changes and hourly/weekday profiles,
then evaluate their trends on a held-out pre-treatment period. Freeze the
features, matching rule, holdout dates and acceptance criteria before using
post-treatment outcomes to compare candidates. Geographic restrictions remain
sensitivity specifications; geography alone does not satisfy the brief.

Before matching, define wholly outside near-boundary links geometrically and
exclude them from controls. Recommend a 500 m distance band as a candidate
definition, with 250 m and 1 km bands reported separately. This distance is a
proposed design choice, not an empirically validated threshold. The current
code excludes only five segments that straddle 60th Street and leaves 15
Manhattan segments wholly north of the line eligible for the control roster.
The [distance audit](../outputs/tables/boundary_distance_audit.csv), using the
existing line and a local metric projection, finds none of those controls
within 500 m and nine within 1 km (nearest about 808 m). Thus a 500 m band
does not currently identify any wholly outside primary link; it reveals a
coverage limitation rather than demonstrated contamination at that distance.

Wait for the contiguous pre-period to evaluate this recommendation. The
current three contiguous pre-treatment months cannot validate a two-year
design. Failure of the corrected tests is evidence against the current pool;
it does not establish that every possible control strategy will fail.

## D3 — Reclassify the four northern 11th Avenue surface-street segments

Recommend moving `108104`, `116080`, `80108` and `81116` into treatment after
owner approval. Their names span 23rd through 57th Streets on 11th Avenue.
The blanket `1[12]th Ave` exemption conflates these local streets with Route 9A.
The [MTA toll definition](https://congestionreliefzone.mta.info/tolling) exempts
the West Side Highway/Route 9A. The
[MTA connection map](https://www.mta.info/map/36226) distinguishes the highway
along 12th Avenue from the northern 11th Avenue surface street. This
recommendation is an inference from those official sources and the segment
names/geometry; do not replace the exemption with a rule that makes all of
11th Avenue non-exempt, because the southern Route 9A alignment differs.

## D5 — Keep bridge directions separate in an exploratory crossing analysis

Retain both Williamsburg Bridge segments as separate outcomes. `194196` is
eastbound from Manhattan to Brooklyn; `197195` is westbound into Manhattan.
The old description calling both an entry queue was incorrect. A pooled
crossing estimate would mix entry and exit behavior, and two links provide
very little independent information for clustered inference. Neither belongs
in the primary surface-street model.

## D6 — Normalize only derived corridor labels when corridor analysis begins

Keep original names and IDs intact. Add an auditable lookup for abbreviations
and corrupted dash characters before producing any corridor aggregate. The
current secondary diagnostic is at link × month, so spelling variants do not
split a corridor estimate: no corridor estimate is produced yet.

## D7 — Complete the frozen window beginning January 2023

Do not extend to 2021–22 now. Only eight of 44 complete target months are held,
with July–September 2024 missing and no 2023 observations in the primary
archive. Completing the agreed window is more informative than adding COVID
recovery years. The 12-month diagnostic milestone does not replace the brief's
24-month pre-treatment requirement.

Approval of these directions authorizes the next design step. It does not
approve a causal result in advance; all failed tests, placebos, verification
failures and null results must remain in the report.

---

A prompt for taking a second opinion on these six is in
[`owner_decision_prompt.md`](owner_decision_prompt.md). It recommends rather
than adopts: these decisions stay reserved to the owner, and the prompt is
written so a model cannot quietly settle one.
