"""Secondary summaries retain local hours and exclude duplicate/DST ambiguity."""

import pandas as pd

from src.analysis import spillover_diagnostics as sd


def test_secondary_dedup_and_naive_time_rules(tmp_path, monkeypatch):
    primary = tmp_path / "panel.parquet"
    pd.DataFrame(
        {
            "link_id": ["a"],
            "ts_hour": pd.to_datetime(["2025-01-05 00:00"]),
            "treatment_group": ["boundary"],
            "post": [True],
            "median_speed_mph": [10.0],
        }
    ).to_parquet(primary)
    raw = tmp_path / "secondary.parquet"
    pd.DataFrame(
        [
            ("1", "2025-01-05T00:00:00", "8"),
            ("2", "2025-01-05T00:00:00", "12"),
            ("3", "2025-01-05T00:30:00", "16"),
            ("4", "2024-11-03T01:15:00", "99"),
            ("5", None, "99"),
            ("6", "2025-01-05T01:00:00", None),
        ],
        columns=["id", "data_as_of", "speed"],
    ).assign(link_id="secondary-a", borough="Manhattan", link_name="FDR example").to_parquet(raw)
    monkeypatch.setattr(sd, "HOURLY_PANEL_PATH", primary)
    monkeypatch.setattr(sd, "TABLES_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["spillover_diagnostics", "--secondary-parts", str(raw)])
    sd.main()
    result = pd.read_csv(tmp_path / "spillover_secondary_monthly.csv")
    assert len(result) == 1
    assert result.loc[0, "month"] == "2025-01-01"
    assert result.loc[0, "readings"] == 2
    assert result.loc[0, "link_hours"] == 1
    assert result.loc[0, "mean_hourly_median_mph"] == 14
