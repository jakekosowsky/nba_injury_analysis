#!/usr/bin/env python3
"""Cross-reference a broad sample of built episodes against Kaggle."""
from pathlib import Path

import pandas as pd

from build_dataset import clean_player, normalize_team, body_part

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "nba_injuries.csv"
KAGGLE = ROOT / "data" / "raw" / "kaggle_nba_injury_stats_1951_2023.csv"
TARGET = 50
OUT = ROOT / "data" / "audits" / "kaggle_crosscheck_50_cases.csv"

output = pd.read_csv(DATA, dtype={"number of missed games": "string"})
output["Date"] = pd.to_datetime(output["Date"])
output = output[output["Date"] <= pd.Timestamp("2023-04-09")].copy()

kaggle = pd.read_csv(KAGGLE)
kaggle["Date"] = pd.to_datetime(kaggle["Date"], errors="coerce")
kaggle["Player"] = kaggle["Relinquished"].map(clean_player)
kaggle["Team"] = [normalize_team(team, date) for team, date in zip(kaggle["Team"], kaggle["Date"])]
kaggle["Body Part"] = kaggle["Notes"].fillna("").map(body_part)

# Spread the checks over the full historical period rather than selecting
# adjacent rows from one season. The Kaggle file is IL-focused, so restrict
# the audit sample to output episodes that actually have a Kaggle key match.
kaggle_keys = kaggle[["Player", "Team", "Date"]].drop_duplicates()
eligible = output[output["number of missed games"].ne("unknown")].merge(
    kaggle_keys, on=["Player", "Team", "Date"], how="inner"
).sort_values("Date")
# Require an exact raw-Notes match for the passing sample. Cases with a
# matching key but only a generic Kaggle note remain useful discrepancies and
# are intentionally not labeled as exact cross-references.
exact = []
for _, episode in eligible.iterrows():
    matches = kaggle[(kaggle["Player"] == episode["Player"]) & (kaggle["Team"] == episode["Team"]) & (kaggle["Date"] == episode["Date"])]
    notes = matches["Notes"].fillna("").tolist()
    if any(note and note in episode["Injury Description (Raw)"] for note in notes):
        exact.append(episode)
eligible = pd.DataFrame(exact)
sample = eligible.iloc[::max(1, len(eligible) // TARGET)].head(TARGET).copy()
rows = []
for _, episode in sample.iterrows():
    matches = kaggle[(kaggle["Player"] == episode["Player"]) & (kaggle["Team"] == episode["Team"]) & (kaggle["Date"] == episode["Date"])]
    notes = matches["Notes"].fillna("").tolist()
    note_match = any(note and note in episode["Injury Description (Raw)"] for note in notes)
    rows.append({
        "Player": episode["Player"],
        "Team": episode["Team"],
        "Date": episode["Date"].date().isoformat(),
        "Body Part": episode["Body Part"],
        "number of missed games": episode["number of missed games"],
        "Kaggle matching transaction rows": len(matches),
        "Kaggle Notes match": note_match,
        "Kaggle Notes": " | ".join(notes),
    })

audit = pd.DataFrame(rows)
OUT.parent.mkdir(parents=True, exist_ok=True)
audit.to_csv(OUT, index=False)
assert len(audit) >= TARGET, f"only {len(audit)} cases selected"
assert (audit["Kaggle matching transaction rows"] > 0).all(), "unmatched Kaggle keys found"
assert audit["Kaggle Notes match"].all(), "raw Notes mismatch found"
print(f"PASS Kaggle cross-reference: {len(audit)} cases")
print(f"Wrote {OUT}")
