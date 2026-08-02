#!/usr/bin/env python3
"""Independently validate future-major-injury fields in the final CSV."""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "nba_injuries.csv"
AUDIT = ROOT / "data" / "audits" / "future_major_injury_audit.csv"

df = pd.read_csv(DATA, parse_dates=["Date", "Next Major Injury Date"])
expected_columns = [
    "Player", "Team", "Date", "Body Part", "Injury Description (Raw)",
    "number of missed games", "Major Injury in Next 3 Years",
    "Major Injury in Next 3 Years - Same Body Part", "Next Major Injury Date",
    "Height (inches)", "Weight (lb)", "Age at Injury",
]
assert df.columns.tolist() == expected_columns, df.columns.tolist()

def is_major(value):
    if isinstance(value, str):
        if value.strip().lower() == "season ending":
            return True
        try:
            return float(value) >= 30
        except ValueError:
            return False
    return pd.notna(value) and float(value) >= 30

expected_map = {}
major = df["number of missed games"].map(is_major)
for _, player_rows in df.groupby("Player", sort=False):
    player_rows = player_rows.sort_values("Date")
    major_rows = player_rows.loc[major.loc[player_rows.index]]
    for index, row in player_rows.iterrows():
        future = major_rows[(major_rows["Date"] > row["Date"]) & (major_rows["Date"] <= row["Date"] + pd.DateOffset(years=3))]
        if future.empty:
            expected_map[index] = ("No", "No", pd.NaT)
            continue
        first = future.iloc[0]
        same = future[future["Body Part"] == row["Body Part"]]
        expected_map[index] = ("Yes", ("Yes" if not same.empty else "No"), first["Date"])

def expected_for(index):
    return expected_map[index]

# Check every row, not just the audit sample.
checks = []
for index in df.index:
    exp = expected_for(index)
    act = (
        df.at[index, "Major Injury in Next 3 Years"],
        df.at[index, "Major Injury in Next 3 Years - Same Body Part"],
        df.at[index, "Next Major Injury Date"],
    )
    dates_match = (pd.isna(exp[2]) and pd.isna(act[2])) or (pd.notna(exp[2]) and pd.Timestamp(exp[2]) == pd.Timestamp(act[2]))
    assert exp[:2] == act[:2] and dates_match, f"metric mismatch at row {index}: expected {exp}, got {act}"

# Explicit edge-case tests for the stated definition.
assert not is_major("unknown")
assert is_major("season ending")
assert is_major("30")
assert not is_major("29")

# MCL is now categorized as knee unless the text also contains the higher-priority ACL signal.
mcl_only = df[df["Injury Description (Raw)"].str.contains(r"mcl", case=False, na=False) & ~df["Injury Description (Raw)"].str.contains(r"acl", case=False, na=False)]
assert mcl_only["Body Part"].eq("knee").all(), "MCL-only rows not categorized as knee"

# Produce a readable 30-row audit sample: rows with a future major event first,
# then same-body-part cases, then deterministic fill from the full dataset.
has_future = df["Major Injury in Next 3 Years"].eq("Yes")
same_future = df["Major Injury in Next 3 Years - Same Body Part"].eq("Yes")
chosen = list(df.index[has_future & same_future][:10]) + list(df.index[has_future & ~same_future][:10])
chosen += [i for i in df.index if i not in chosen][: max(0, 30 - len(chosen))]
chosen = chosen[:30]
audit_rows = []
for index in chosen:
    row = df.loc[index]
    exp = expected_for(index)
    audit_rows.append({
        "Player": row["Player"], "Initial Date": row["Date"], "Initial Body Part": row["Body Part"],
        "Initial Missed Games": row["number of missed games"], "Expected Future Major": exp[0],
        "Actual Future Major": row["Major Injury in Next 3 Years"],
        "Expected Same Body Part": exp[1], "Actual Same Body Part": row["Major Injury in Next 3 Years - Same Body Part"],
        "Expected First Major Date": exp[2], "Actual First Major Date": row["Next Major Injury Date"],
        "Audit Result": "PASS",
    })
pd.DataFrame(audit_rows).to_csv(AUDIT, index=False, date_format="%Y-%m-%d")
print(f"PASS full-row metric audit: {len(df):,} rows")
print(f"PASS MCL recategorization: {len(mcl_only):,} MCL-only rows")
print(f"PASS sample audit: {len(audit_rows)} rows written to {AUDIT}")
print("Future major flag counts:")
print(df["Major Injury in Next 3 Years"].value_counts().to_string())
print("Same-body-part flag counts:")
print(df["Major Injury in Next 3 Years - Same Body Part"].value_counts().to_string())
