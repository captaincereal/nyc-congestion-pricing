# Project brief

The canonical, up-to-date brief with frozen definitions lives at
**[`docs/project_brief.md`](docs/project_brief.md)**.

Short version:

- **Question**: effect of NYC congestion pricing (tolling from 2025-01-05) on
  traffic speeds inside the Congestion Relief Zone, and spillover to nearby areas.
- **Primary outcome**: hourly median traffic speed (mph) on a road segment.
- **Method**: difference-in-differences + event study, with robustness and
  placebo tests. Standard errors clustered by segment.
- **Data**: NYC DOT Traffic Speeds NBE (`i4gi-tjb9`) only, for the core analysis.
- **Principles**: no correlation-as-causation; don't change treatment/control
  definitions after seeing results without documenting; report nulls; report
  confidence intervals; document missing data; raw data stays unchanged; every
  transformation reproducible.
