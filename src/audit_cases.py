#!/usr/bin/env python3
"""Regression checks for manually verified Basketball Reference cases."""
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "nba_injuries.csv"

EXPECTED = {
    ("Darren Collison", "2018-02-05"): "11",
    ("Isaiah Whitehead", "2017-01-13"): "1",
    ("Enes Kanter", "2017-01-26"): "10",
}

df = pd.read_csv(DATA, dtype={"number of missed games": "string"})
assert df.columns.tolist() == [
    "Player", "Team", "Date", "Body Part", "Injury Description (Raw)",
    "number of missed games", "Height (inches)", "Weight (lb)", "Age at Injury",
]
assert not df.duplicated(["Player", "Team", "Date"]).any(), "duplicate injury episodes remain"
for (player, date), expected in EXPECTED.items():
    rows = df[(df["Player"] == player) & (df["Date"] == date)]
    assert len(rows) == 1, f"expected one row for {player} on {date}"
    actual = rows.iloc[0]["number of missed games"]
    assert actual == expected, f"{player} {date}: expected {expected}, got {actual}"
    print(f"PASS {player} {date}: {actual} games")
print(f"PASS schema and uniqueness: {len(df):,} rows")
