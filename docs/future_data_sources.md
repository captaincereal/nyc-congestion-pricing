# Future data sources (Phase 10 — do not add yet)

The core analysis uses **only** the speed feeds: the NYC DOT E-Z Pass
local-street feeds (`erdf-2akx` + `6a2s-2t65`, primary) and the Traffic Speeds
NBE feed (`i4gi-tjb9`, secondary — spillover onto the toll-exempt highways).
The sources below are deferred until the speed-based DiD / event study is stable
and has passed its diagnostics. Each is added only to answer a *specific*
question.

| Source | Socrata / access | Question it would answer |
|---|---|---|
| MTA Congestion Relief Zone vehicle entries | `data.ny.gov` resource `t6yz-b64h` | Did *volume* entering the zone fall? Does it corroborate the speed change (mechanism check)? |
| NYC DOT Traffic Volume Counts | `data.cityofnewyork.us` resource `7ym2-wayt` | Segment-level volume near the boundary — spillover in counts, not just speeds. |
| NYC TLC trip records (yellow / green / FHV) | TLC monthly parquet files | Trip times, fares, pickup/dropoff shifts across the cordon. |

The earlier scaffold wired all of these into `download.py` and the SQL at once.
That was rolled back on 2026-09-07 to keep Phases 1–9 to the speed feeds alone.
The dataset ids above are recorded here so the work isn't lost.

## Already added

- **Weather (Open-Meteo ERA5, Central Park).** Added in Phase 7 —
  `src/data/download_weather.py`, hourly, requested in local time so it joins
  `ts_hour` with no conversion, and not hosted on `data.cityofnewyork.us` so it
  costs the speed backfill nothing. The post period is materially colder/snowier
  than the pre period, which biases the DiD estimate *downward*; used only as a
  robustness check (treated × weather interactions), never as a level control.

## 2026-09-14 — the MTA entries are in, and TLC is deferred on evidence

**MTA Congestion Relief Zone vehicle entries (`t6yz-b64h`) are no longer
future.** H008, H009 and H010 all use them, as cached Socrata aggregates under
`data/raw/mta_crz/`. The question in the table above — did volume entering the
zone fall — remains unanswerable, because the series begins on the tolling date.
What the source turned out to support is a different question the table did not
anticipate: the toll's own peak/overnight price discontinuity identifies a
retiming response without needing parallel trends.

**NYC TLC trip records: recommended against, for now.** The argument is not
about effort or access. TLC covers yellow, green and for-hire vehicles, and
H008 measured that class at both price boundaries
([H008_by_vehicle_class.csv](../outputs/tables/H008_by_vehicle_class.csv)):
τ = **−0.021** at 05:00 and **+0.004** at 21:00, against −0.862 and +0.254 for
cars and pickups. Taxis and FHVs pay a per-trip surcharge and drive to a
passenger's schedule, so the one design in this project that does not rest on
parallel trends is invisible in TLC data by construction. A TLC
before-and-after across the cordon would inherit the identification failure that
H001 through H006 documented.

What would justify revisiting it is an outcome other than link speed —
zone-to-zone trip duration with a genuine pre-period — which the README names as
one of three things capable of changing the answer. That is a different
hypothesis from anything registered, and it would need its own record.

**The distribution is still unverified, and this session could not verify it.**
The table above says monthly parquet files. The session writing this entry could
not reach `d37ci6vzurychx.cloudfront.net`, `www.nyc.gov`, `data.ny.gov` or
`data.cityofnewyork.us` — its sandbox network policy denied CONNECT to every
one, including the two endpoints this project downloads from daily. So the
failure says nothing about the sources and the claim stands unconfirmed. Anyone
reopening TLC should confirm the endpoint from a runner with normal egress
before writing any ingestion code, rather than trusting either the table above
or this paragraph.

## 2026-09-15 — a survey exists; run it before designing around any of this

The table at the top of this file and the paragraphs above it were written from
memory and from what the project happened to have used. Neither has been checked
against what the agencies currently publish, and this project has already lost
weeks to a feed whose coverage was assumed rather than measured.

`src/data/source_recon.py` settles that by asking. It searches Socrata's
discovery API for datasets bearing on the questions the speed study could not
answer, then reports each one's columns, date range and row count, and probes
the handful of non-Socrata URLs that are otherwise guesses. **Datasets are found
by searching rather than by asserting ids**, and a test enforces that: nothing is
described that a search did not return.

Dispatch the **Source recon** workflow. The runners have network; a sandbox may
not. It writes `docs/source_recon.md` for a reader and
`outputs/tables/source_recon.json` for a later session, and it takes no draw
against fixed data, so it is safe to repeat whenever an inventory goes stale.

The questions it is scoped to, none of which the speed study could answer:

- Did vehicle volume fall on crossings that feed the zone, against crossings run
  by the same operator that do not? Same counting equipment, same reporting, a
  genuine pre-period — a far better comparison than "similar streets". The known
  weakness is that traffic shifting *between* crossings makes the control partly
  treated, the same problem H009 hit with the exempt roadways.
- Did people switch to transit inside the zone relative to outside?
- Are there street-level vehicle counts with a pre-period near the cordon?
- Is there a door-to-door travel-time outcome with a long pre-period? This
  revisits TLC, and **narrows the recommendation made earlier on this page**:
  taxi records are useless for the *timing* question, because H008 measured that
  class at essentially zero response, and that says nothing about their value for
  travel time between fixed zone pairs, where the pre-period runs to a decade.

**The survey endorses nothing.** Which source can answer which question is a
judgement for a registered hypothesis. This only establishes what exists.
