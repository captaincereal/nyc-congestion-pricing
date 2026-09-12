# Source execution — 2026-09-12

The owner's ordering is source verification, frozen-window backfill, then
registered temporal aggregation. No D1–D7 design recommendation is adopted.
H002 and D2 construction remain deferred until a contiguous pre-period is held.

The original hosted Backfill run 34707558019 failed at 18:10:58 UTC. July 4
exhausted five HTTP attempts with 180-second read timeouts; August and September
2024 landed and were published, but the failed download step skipped verification.
The release therefore grew from eight to ten held months, with five contiguous
complete pre-treatment months (August–December 2024), while the original eight
remained unverified. The original June three-day receipt predates this runner
and is not evidence of hosted verification progress. This failure is retained.

The replacement Python controller uses a shared 285-minute source budget on
standard public GitHub runners, with a 350-minute job cap and six-hour schedule.
It verifies the original eight hash-bound inputs before any new downloads.
Raw-count checks and deterministic replay are resumable per calendar day;
immutable release snapshots preserve the manifest, receipts and in-flight day
checkpoints every twelve minutes or completed month, and on failure. Canonical
JSON files are compatibility copies written after the durable snapshot.
Source retries respect the shared deadline; failed large pages fall back to
smaller indexed pages without advancing the offset. Neither a green budget
exit nor a verified flag without complete receipts satisfies the strict gate.

After the original-eight gate, held unchecked additions are verified and missing
months are prioritized backwards from December 2024 to January 2023, then forward
through August 2026. This operational order grows the pre-period adjoining
treatment. It does not extend the window into 2021–22 or adopt a control design.
The frozen target is 44 months, including 24 full pre-treatment months.
New downloads count raw pages and preserve hash-bound sampling evidence while
assembling each immutable part; unchecked legacy day checkpoints are replayed.

Analysis restoration fails closed on corruption, missing assets and digest
mismatches. Existing diagnostics wait until every used input has complete
versioned receipts. H003 uses only the separately pinned original eight parts
and geometry; newly landed months cannot silently change its registered sample.
Its hourly schedule waits on the strict gate and retains completed results.
Daily peak is the lead H003 metric under the prospective owner amendment,
committed before execution. All secondary results and failures remain reported.

Run summaries and `source_status.json` lead with contiguous pre-period depth,
then coverage against 44, verified input counts and calendar-day receipt counts.
Receipts establish agreement at their recorded check time; they cannot guarantee
that the upstream historical feed will never be revised later.
