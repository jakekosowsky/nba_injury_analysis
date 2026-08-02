#!/usr/bin/env python3
"""Ingest Basketball Reference advanced VORP tables for all seasons needed."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import time
import requests
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "vorp_by_player_year.csv"
RAW_OUT = RAW / "basketball_reference_vorp_all_years.csv"
CACHE = RAW / "bref_vorp_cache"
YEARS = range(1997, 2027)
HEADERS = {"User-Agent": "Mozilla/5.0 (research dataset; cached Basketball Reference ingestion)"}

def fetch(year):
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"NBA_{year}_advanced.txt"
    if path.exists() and path.stat().st_size > 1000:
        return year, path.read_text(encoding="utf-8")
    url = f"https://r.jina.ai/http://www.basketball-reference.com/leagues/NBA_{year}_advanced.html"
    for attempt in range(4):
        try:
            response = requests.get(url, headers=HEADERS, timeout=90)
            response.raise_for_status()
            path.write_text(response.text, encoding="utf-8")
            time.sleep(0.25)
            return year, response.text
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 ** attempt)

def parse(year, text):
    lines = text.splitlines()
    header_index = next(i for i, line in enumerate(lines) if (line.startswith("Rk\tPlayer\tAge\tTeam") or line.startswith("| Rk | Player | Age | Team")) and "VORP" in line)
    pipe_format = lines[header_index].startswith("|")
    header = [x.strip() for x in (lines[header_index].strip("|").split("|") if pipe_format else lines[header_index].split("\t"))]
    vorp_index = header.index("VORP")
    rows = []
    for line in lines[header_index + 1:]:
        if line.startswith("Leaders"):
            break
        if pipe_format:
            if not re.match(r"^\|\s*\d+\s*\|", line):
                continue
            fields = [x.strip() for x in line.strip("|").split("|")]
        else:
            if not re.match(r"^\d+\t", line):
                continue
            fields = line.split("\t")
        if len(fields) <= vorp_index:
            continue
        fields = [re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", x).replace("**", "").strip() for x in fields]
        try:
            age = int(float(fields[2]))
            vorp = float(fields[vorp_index])
        except (ValueError, IndexError):
            continue
        rows.append({"Season": year, "Player": fields[1].strip().replace("*", ""), "Age": age, "Team": fields[3].strip(), "G": fields[5], "MP": fields[7], "VORP": vorp})
    return rows

def canonicalize(raw):
    raw = raw.copy()
    raw["Team"] = raw["Team"].astype(str)
    raw["VORP"] = pd.to_numeric(raw["VORP"], errors="coerce")
    raw["Age"] = pd.to_numeric(raw["Age"], errors="coerce").astype("Int64")
    total_mask = raw["Team"].str.match(r"^\d+TM$") | raw["Team"].eq("TOT")
    selected = []
    for (_, _), group in raw.groupby(["Season", "Player"], sort=False):
        totals = group[total_mask.loc[group.index]]
        if not totals.empty:
            selected.append(totals.iloc[-1])
        elif len(group) == 1:
            selected.append(group.iloc[0])
        else:
            row = group.iloc[0].copy()
            row["Team"] = "/".join(group["Team"].astype(str).tolist())
            row["VORP"] = group["VORP"].sum()
            row["G"] = pd.to_numeric(group["G"], errors="coerce").sum()
            row["MP"] = pd.to_numeric(group["MP"], errors="coerce").sum()
            selected.append(row)
    out = pd.DataFrame(selected).sort_values(["Season", "Player"], ignore_index=True)
    age_mean = out.groupby("Age")["VORP"].transform("mean")
    out["Age Mean VORP"] = age_mean
    out["Age-Adjusted VORP Index"] = out["VORP"] / age_mean.where(age_mean.abs() > 1e-9)
    return out[["Season", "Player", "Age", "Team", "G", "MP", "VORP", "Age Mean VORP", "Age-Adjusted VORP Index"]]

def main():
    results = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(fetch, year) for year in YEARS]
        for future in as_completed(futures):
            year, text = future.result()
            results.extend(parse(year, text))
            print(f"parsed {year}", flush=True)
    raw = pd.DataFrame(results).sort_values(["Season", "Player", "Team"], ignore_index=True)
    RAW.mkdir(parents=True, exist_ok=True)
    raw.to_csv(RAW_OUT, index=False)
    canonicalize(raw).to_csv(OUT, index=False)
    print(f"wrote raw {len(raw):,} rows to {RAW_OUT}")
    print(f"wrote canonical {len(canonicalize(raw)):,} player-season rows to {OUT}")

if __name__ == "__main__":
    main()
