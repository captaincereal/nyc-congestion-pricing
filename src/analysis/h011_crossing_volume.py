"""H011 — did tolling reduce vehicle volume entering the zone, at the crossings?

Record: docs/hypotheses/H011-crossing-volume.md, committed first.

`ebfx-2m7v` carries hourly crossings by facility, direction and vehicle class
from 2019, so two facilities that enter the Congestion Relief Zone can be
compared against the same operator's crossings that do not, over a real
pre-period, on one counting system.

**Two stages, and the gate between them is the point.** The record requires the
treatment classification to be read off the data and written down before
anything is estimated, because assuming which crossings enter the zone is the D3
error in a new place. So:

    python -m src.analysis.h011_crossing_volume --stage roster

emits the facility roster and stops. A person or a later session classifies each
facility, commits `docs/h011_facility_classification.csv`, and only then:

    python -m src.analysis.h011_crossing_volume --stage estimate

runs. The estimate stage refuses to start without that file, so the
classification cannot be smuggled in as a default.

**Written by the record's author and deliberately not run by them.** Whoever
executes this fills in Result and Verdict.
"""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import logging
import urllib.parse
import urllib.request

import numpy as np
import pandas as pd

from src.config import DOCS_DIR, RAW_DIR, TABLES_DIR

log = logging.getLogger(__name__)

DATASET = "ebfx-2m7v"
DOMAIN = "data.ny.gov"
CACHE_DIR = RAW_DIR / "mta_crossings"
CLASSIFICATION = DOCS_DIR / "h011_facility_classification.csv"

# Frozen in the record, with reasons stated there.
TREATMENT_MONTH = "2025-01"  # tolling began 2025-01-05; excluded as transition
PRE_START = "2023-01"  # the 24 months the brief asks for
PRE_END = "2024-12"
POST_START = "2025-02"
REFERENCE_K = -1

SUPPORT_M = 1.0
SUPPORT_EFFECT = 0.02
REFUTE_M = 0.3
REFUTE_EFFECT = 0.01
RANDOMIZATION_BAND = 0.90


def _fetch(select: str, group: str, where: str | None = None) -> pd.DataFrame:
    """One cached Socrata aggregate against this dataset.

    Deliberately local rather than imported from `h008_toll_timing`: that helper
    is bound to the entry-counts dataset, its behaviour is pinned by tests three
    records depend on, and widening its signature to take a dataset id would put
    those at risk for fifteen lines of reuse.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256(f"{DATASET}|{select}|{group}|{where}".encode()).hexdigest()[:16]
    cache = CACHE_DIR / f"agg_{key}.parquet"
    if cache.exists():
        return pd.read_parquet(cache)
    rows: list[dict] = []
    offset, page = 0, 50_000
    while True:
        params = {"$select": select, "$group": group, "$limit": page, "$offset": offset}
        if where:
            params["$where"] = where
        url = f"https://{DOMAIN}/resource/{DATASET}.json?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=180) as response:
            batch = json.load(response)
        rows.extend(batch)
        if len(batch) < page:
            break
        offset += page
    frame = pd.DataFrame(rows)
    frame.to_parquet(cache, index=False)
    log.info("fetched %s rows grouped by %s", f"{len(frame):,}", group)
    return frame


def facility_roster() -> pd.DataFrame:
    """Every facility and direction the feed carries, with its span and volume.

    Stage one. This is what a classification has to be written against, and it
    is the whole reason the estimate stage will not start without one.
    """
    frame = _fetch(
        "facility,facility_id,direction,count(*) as row_count,"
        "sum(traffic_count) as crossings,min(date) as earliest,max(date) as latest",
        "facility,facility_id,direction",
    )
    for column in ("row_count", "crossings"):
        frame[column] = pd.to_numeric(frame[column])
    return frame.sort_values(["facility", "direction"]).reset_index(drop=True)


def load_classification(path=CLASSIFICATION) -> pd.DataFrame:
    """The committed treatment assignment, or a refusal to proceed without it."""
    if not path.exists():
        raise SystemExit(
            f"{path} does not exist.\n"
            "H011 will not estimate against an assumed classification. Run\n"
            "  python -m src.analysis.h011_crossing_volume --stage roster\n"
            "read the facility list it writes, decide which facilities are CRZ\n"
            "entry points citing docs/project_brief.md, and commit the file with\n"
            "columns facility,is_crz_entry,source. Assuming this is the D3 error."
        )
    frame = pd.read_csv(path)
    missing = {"facility", "is_crz_entry", "source"} - set(frame.columns)
    if missing:
        raise SystemExit(f"{path} is missing columns: {sorted(missing)}")
    if frame["source"].isna().any() or (frame["source"].astype(str).str.strip() == "").any():
        raise SystemExit(f"{path}: every row needs a `source` saying how it was decided.")
    frame["is_crz_entry"] = frame["is_crz_entry"].astype(bool)
    if not frame["is_crz_entry"].any():
        raise SystemExit(f"{path}: no facility is marked as a CRZ entry point.")
    if frame["is_crz_entry"].all():
        raise SystemExit(f"{path}: every facility is marked treated, leaving no control.")
    return frame


def monthly_panel(classification: pd.DataFrame, direction: str | None = None) -> pd.DataFrame:
    """Facility x month crossings, log1p, over the frozen window.

    **All directions by default**, per the 2026-09-15 amendment. The roster
    showed fifteen distinct direction labels across ten facilities and no
    facility-independent notion of "inbound": neither direction of the Cross Bay
    or Marine Parkway bridges goes to Manhattan at all. Summing both directions
    is the least arbitrary comparable outcome. It dilutes the effect, because
    the charge applies to one direction of the treated tunnels, and the record
    says so rather than leaving it to be discovered.

    `direction` restricts to one label, for the secondary cut at the treated
    tunnels only.
    """
    where = f"direction='{direction}'" if direction else None
    frame = _fetch(
        "facility,date_trunc_ym(date) as month,sum(traffic_count) as crossings",
        "facility,date_trunc_ym(date) as month",
        where=where,
    )
    frame["crossings"] = pd.to_numeric(frame["crossings"])
    frame["month"] = pd.to_datetime(frame["month"]).dt.strftime("%Y-%m")
    rows_in = len(frame)
    frame = frame[(frame["month"] >= PRE_START) & (frame["month"] != TREATMENT_MONTH)]
    log.info(
        "rows in %s -> %s after the frozen window and the transition month",
        f"{rows_in:,}",
        f"{len(frame):,}",
    )
    frame = frame.merge(classification[["facility", "is_crz_entry"]], on="facility", how="inner")
    frame["log_crossings"] = np.log1p(frame["crossings"])
    frame["post"] = frame["month"] >= POST_START
    return frame.sort_values(["facility", "month"]).reset_index(drop=True)


def _absorb(values: np.ndarray, *code_sets: np.ndarray) -> np.ndarray:
    """Alternating-projection demeaning, enough for two balanced factors."""
    out = values.astype(float).copy()
    for _ in range(50):
        before = out.copy()
        for codes in code_sets:
            means = np.zeros((codes.max() + 1,) + out.shape[1:])
            counts = np.bincount(codes, minlength=codes.max() + 1)
            np.add.at(means, codes, out)
            out -= ((means.T / counts).T)[codes]
        if np.max(np.abs(out - before)) < 1e-12:
            break
    return out


def did_estimate(panel: pd.DataFrame, treated: np.ndarray | None = None) -> float:
    """Two-way fixed effects on facility and month; returns the ATT in logs.

    `treated` overrides the classification, which is what randomization
    inference needs in order to reassign treatment among the facilities.
    """
    facility_codes, facilities = pd.factorize(panel["facility"], sort=True)
    month_codes, _ = pd.factorize(panel["month"], sort=True)
    flag = panel["is_crz_entry"].to_numpy() if treated is None else treated[facility_codes]
    interaction = (flag & panel["post"].to_numpy()).astype(float)

    y = _absorb(panel["log_crossings"].to_numpy(), facility_codes, month_codes)
    x = _absorb(interaction, facility_codes, month_codes)
    denominator = float(x @ x)
    if denominator <= 0:
        return float("nan")
    return float((x @ y) / denominator)


def randomization(panel: pd.DataFrame) -> dict:
    """Reassign treatment across every combination of the same size.

    With nine facilities and two treated there are 36 assignments, so the finest
    achievable one-sided p is about 0.028. That ceiling is reported rather than
    hidden, per the record.
    """
    facilities = sorted(panel["facility"].unique())
    n_treated = int(panel.drop_duplicates("facility")["is_crz_entry"].sum())
    observed = did_estimate(panel)
    draws = []
    for combination in itertools.combinations(range(len(facilities)), n_treated):
        flag = np.zeros(len(facilities), dtype=bool)
        flag[list(combination)] = True
        draws.append(did_estimate(panel, treated=flag))
    draws = np.array([d for d in draws if np.isfinite(d)])
    lower, upper = np.percentile(
        draws, [100 * (1 - RANDOMIZATION_BAND) / 2, 100 * (1 + RANDOMIZATION_BAND) / 2]
    )
    return {
        "observed": observed,
        "n_assignments": len(draws),
        "finest_one_sided_p": 1 / len(draws) if len(draws) else float("nan"),
        "band_low": float(lower),
        "band_high": float(upper),
        "outside_band": bool(observed < lower or observed > upper),
        "share_at_least_as_extreme": float(np.mean(np.abs(draws) >= abs(observed))),
    }


def event_study(panel: pd.DataFrame) -> dict:
    """Treated x event-month coefficients with their full cluster-robust vcov.

    The off-diagonal terms are the point: the Rambachan-Roth restriction is on
    differences between adjacent event-time coefficients, whose variance depends
    on their covariance. Passing only the diagonal would understate it.
    """
    months = sorted(panel["month"].unique())
    reference = pd.Period(TREATMENT_MONTH, freq="M")
    event = {m: (pd.Period(m, freq="M") - reference).n for m in months}
    ks = sorted({event[m] for m in months} - {REFERENCE_K})

    facility_codes, _ = pd.factorize(panel["facility"], sort=True)
    month_codes, _ = pd.factorize(panel["month"], sort=True)
    treated = panel["is_crz_entry"].to_numpy().astype(float)
    k_of_row = np.array([event[m] for m in panel["month"]])

    design = np.column_stack([treated * (k_of_row == k) for k in ks])
    y = _absorb(panel["log_crossings"].to_numpy(), facility_codes, month_codes)
    X = _absorb(design, facility_codes, month_codes)

    xtx = X.T @ X
    beta = np.linalg.solve(xtx, X.T @ y)
    resid = y - X @ beta
    inverse = np.linalg.inv(xtx)
    meat = np.zeros_like(xtx)
    for cluster in range(facility_codes.max() + 1):
        rows = facility_codes == cluster
        score = X[rows].T @ resid[rows]
        meat += np.outer(score, score)
    n_clusters = facility_codes.max() + 1
    vcov = inverse @ meat @ inverse * (n_clusters / max(n_clusters - 1, 1))
    return {
        "k": ks,
        "beta": beta,
        "se": np.sqrt(np.diag(vcov)),
        "vcov": vcov,
        "n_obs": int(len(panel)),
        "n_clusters": int(n_clusters),
    }


def breakdown_value(moments: dict) -> float:
    """Smallest violation multiple at which the robust set stops excluding zero.

    Directly comparable to the 0.005-0.171 H002 and H005 report on the link
    panel, which is why the record chose it.
    """
    from diff_diff import HonestDiD

    from src.analysis.honest_did import to_container

    return float(HonestDiD(method="relative_magnitude").breakdown_value(to_container(moments)))


def evaluate_criteria(breakdown_value: float, effect: float, drawn: dict) -> dict:
    """The frozen criteria, applied mechanically. The Verdict is not written here."""
    support = bool(
        breakdown_value >= SUPPORT_M
        and effect <= -SUPPORT_EFFECT
        and drawn.get("outside_band", False)
    )
    refute_1 = bool(breakdown_value < REFUTE_M)
    refute_2 = bool(abs(effect) < REFUTE_EFFECT)
    refute_3 = bool(effect > 0 and breakdown_value >= REFUTE_M)
    return {
        "supports": support,
        "refute_1_breakdown_below_floor": refute_1,
        "refute_2_effect_negligible": refute_2,
        "refute_3_wrong_signed_and_not_noise": refute_3,
        "uninformative": bool(not support and not (refute_1 or refute_2 or refute_3)),
        "breakdown_value": breakdown_value,
        "effect_log": effect,
        "effect_pct": float(np.expm1(effect) * 100),
        # Named so a reader (or a prefix match) cannot mistake a threshold for
        # a condition that fired.
        "threshold_support_m": SUPPORT_M,
        "threshold_refute_m": REFUTE_M,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("roster", "estimate"), required=True)
    parser.add_argument("--out-prefix", default="H011")
    parser.add_argument(
        "--direction",
        default="",
        help="restrict to one direction label, for the secondary cut only",
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.stage == "roster":
        roster = facility_roster()
        path = TABLES_DIR / f"{args.out_prefix}_facility_roster.csv"
        roster.to_csv(path, index=False)
        log.info("wrote %s with %s facility-direction rows", path, len(roster))
        log.info("\n%s", roster.to_string(index=False))
        log.info(
            "Stage one ends here by design. Classify these facilities, commit %s, "
            "then run --stage estimate.",
            CLASSIFICATION,
        )
        return

    classification = load_classification()
    panel = monthly_panel(classification, args.direction or None)
    panel.to_csv(TABLES_DIR / f"{args.out_prefix}_panel.csv", index=False)

    drawn = randomization(panel)
    pd.DataFrame([drawn]).to_csv(TABLES_DIR / f"{args.out_prefix}_randomization.csv", index=False)

    moments = event_study(panel)
    pd.DataFrame({"k": moments["k"], "beta": moments["beta"], "se": moments["se"]}).to_csv(
        TABLES_DIR / f"{args.out_prefix}_event_study.csv", index=False
    )
    value = breakdown_value(moments)

    verdict = evaluate_criteria(value, drawn["observed"], drawn)
    pd.DataFrame([verdict]).to_csv(TABLES_DIR / f"{args.out_prefix}_criteria.csv", index=False)
    log.info("ATT %.4f log points (%.2f%%)", drawn["observed"], verdict["effect_pct"])
    log.info("breakdown value %.4f", value)
    log.info("randomization %s", drawn)
    log.info("criteria as frozen and amended: %s", verdict)


if __name__ == "__main__":
    main()
