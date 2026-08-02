#!/usr/bin/env python3
"""Build the schedule-free NBA injury event dataset."""
from __future__ import annotations

import argparse
import re
import time
import unicodedata
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "nba_injuries.csv"

TEAM_MAP = {
    "76ers": "Philadelphia 76ers", "Blazers": "Portland Trail Blazers", "Bobcats": "Charlotte Bobcats",
    "Bucks": "Milwaukee Bucks", "Bullets": "Washington Bullets", "Bulls": "Chicago Bulls",
    "Cavaliers": "Cleveland Cavaliers", "Celtics": "Boston Celtics", "Clippers": "Los Angeles Clippers",
    "Grizzlies": "Memphis Grizzlies", "Hawks": "Atlanta Hawks", "Heat": "Miami Heat",
    "Jazz": "Utah Jazz", "Kings": "Sacramento Kings", "Knicks": "New York Knicks",
    "Lakers": "Los Angeles Lakers", "Magic": "Orlando Magic", "Mavericks": "Dallas Mavericks",
    "Nets": "Brooklyn Nets", "Hornets": "Charlotte Hornets", "Portland Trailblazers": "Portland Trail Blazers", "Sonics": "Seattle SuperSonics",
    "Nuggets": "Denver Nuggets", "Pacers": "Indiana Pacers", "Pelicans": "New Orleans Pelicans",
    "Pistons": "Detroit Pistons", "Raptors": "Toronto Raptors", "Rockets": "Houston Rockets",
    "Spurs": "San Antonio Spurs", "Suns": "Phoenix Suns", "Thunder": "Oklahoma City Thunder",
    "Timberwolves": "Minnesota Timberwolves", "Warriors": "Golden State Warriors", "Wizards": "Washington Wizards",
}

def body_part(note: str) -> str:
    n = note.lower()
    rules = [
        ("foot", ["foot"]), ("toe", ["toe"]), ("heel", ["heel"]),
        ("ankle", ["ankle"]), ("achilles", ["achilles"]), ("calf", ["calf"]),
        ("shin", ["shin"]), ("tibia", ["tibia"]), ("fibula", ["fibula"]),
        ("ACL", ["acl"]), ("knee", ["knee", "patella", "meniscus", "mcl"]),
        ("quad", ["quad", "quadriceps"]), ("hamstring", ["hamstring"]),
        ("groin", ["groin"]), ("hip", ["hip", "adductor"]), ("femur", ["femur"]),
        ("leg", ["leg"]), ("chest", ["chest", "pectoral"]), ("shoulder", ["shoulder", "rotator cuff"]),
        ("back", ["back"]), ("collarbone", ["collarbone"]), ("ribs", ["rib"]),
        ("abdominal", ["abdom", "abductor", "oblique"]), ("neck", ["neck"]),
        ("head", ["head", "concussion"]), ("eye", ["eye"]), ("nose", ["nose"]),
        ("hand", ["hand"]), ("finger", ["finger", "thumb"]), ("arm", ["arm"]),
        ("elbow", ["elbow"]), ("bicep", ["bicep"]), ("tricep", ["tricep"]), ("wrist", ["wrist"]),
    ]
    for label, needles in rules:
        if any(x in n for x in needles):
            return label
    return "other"

def clean_player(value: object) -> str:
    name = "" if pd.isna(value) else str(value)
    name = name.split("/")[0]
    name = re.sub(r"\([^)]*\)", "", name)
    name = re.sub(r"\b(Jr|Sr|II|III|IV)\.?\b", "", name, flags=re.I)
    return re.sub(r"\s+", " ", name.replace(".", "")).strip()

def name_key(value: object) -> str:
    """Normalize names for joins to the Basketball Reference bio table."""
    text = "" if pd.isna(value) else str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = text.replace("*", "").lower()
    text = re.sub(r"\([^)]*\)", "", text)
    text = re.sub(r"\b(jr|sr|ii|iii|iv)\b", "", text)
    return re.sub(r"[^a-z0-9]", "", text)

def height_inches(value: object) -> float:
    """Convert Basketball Reference's feet-inches height to inches."""
    text = "" if pd.isna(value) else str(value).strip()
    match = re.match(r"^(\d+)-(\d+)$", text)
    if not match:
        return float("nan")
    return int(match.group(1)) * 12 + int(match.group(2))

def load_bios() -> pd.DataFrame:
    path = RAW / "basketball_reference_player_bios.csv"
    if not path.exists():
        return pd.DataFrame()
    bios = pd.read_csv(path)
    bios["_name_key"] = bios["Player"].map(name_key)
    bios["_birth"] = pd.to_datetime(bios["Birth Date"], errors="coerce")
    bios["_height_inches"] = bios["Ht"].map(height_inches)
    bios["_weight_lb"] = pd.to_numeric(bios["Wt"], errors="coerce")
    bios["From"] = pd.to_numeric(bios["From"], errors="coerce")
    bios["To"] = pd.to_numeric(bios["To"], errors="coerce")
    return bios

def enrich_demographics(rows: pd.DataFrame) -> pd.DataFrame:
    """Add BRef-derived height, weight, and exact age at injury."""
    bios = load_bios()
    rows = rows.copy()
    rows["Height (inches)"] = pd.NA
    rows["Weight (lb)"] = pd.NA
    rows["Age at Injury"] = pd.NA
    if bios.empty:
        return rows
    by_name = {key: group for key, group in bios.groupby("_name_key", sort=False)}
    for index, row in rows.iterrows():
        candidates = by_name.get(name_key(row["Player"]))
        if candidates is None or candidates.empty:
            continue
        year = pd.Timestamp(row["Date"]).year
        in_year = candidates[(candidates["From"].isna() | (candidates["From"] <= year)) & (candidates["To"].isna() | (candidates["To"] >= year))]
        bio = (in_year if not in_year.empty else candidates).iloc[0]
        rows.at[index, "Height (inches)"] = bio["_height_inches"]
        rows.at[index, "Weight (lb)"] = bio["_weight_lb"]
        if pd.notna(bio["_birth"]):
            injury_date = pd.Timestamp(row["Date"])
            birth = pd.Timestamp(bio["_birth"])
            rows.at[index, "Age at Injury"] = injury_date.year - birth.year - ((injury_date.month, injury_date.day) < (birth.month, birth.day))
    rows["Height (inches)"] = pd.to_numeric(rows["Height (inches)"], errors="coerce").astype("Int64")
    rows["Weight (lb)"] = pd.to_numeric(rows["Weight (lb)"], errors="coerce").astype("Int64")
    rows["Age at Injury"] = pd.to_numeric(rows["Age at Injury"], errors="coerce").astype("Int64")
    return rows

def normalize_team(value: object, date: pd.Timestamp) -> str:
    """Use the team's historical name so transactions join to schedules."""
    if pd.isna(value) or str(value).strip() == "":
        return None
    # Prosports uses the bare label "Hornets" for both the Charlotte and New
    # Orleans franchises. The date disambiguates the historical franchise.
    if str(value).strip() == "Hornets":
        if date < pd.Timestamp("2002-07-01"):
            return "Charlotte Hornets"
        if date < pd.Timestamp("2013-06-18"):
            return "New Orleans Hornets"
        return "Charlotte Hornets"
    team = TEAM_MAP.get(str(value), str(value))
    if team in {"Charlotte Bobcats", "Charlotte Hornets"}:
        return "Charlotte Bobcats" if date < pd.Timestamp("2014-05-20") else "Charlotte Hornets"
    if team in {"New Jersey Nets", "Brooklyn Nets"}:
        return "New Jersey Nets" if date < pd.Timestamp("2012-06-18") else "Brooklyn Nets"
    if team in {"New Orleans Hornets", "New Orleans Pelicans"}:
        return "New Orleans Hornets" if date < pd.Timestamp("2013-06-18") else "New Orleans Pelicans"
    return team

def is_injury(note: str) -> bool:
    n = note.lower().strip()
    excluded = ["suspension", "rest", "family", "personal", "birth", "death", "virus", "headache", "flu", "sick", "illness", "infection", "pneumonia", "gastro", "appende", "nausea", "pox", "dizziness", "poisoning", "bronchitis", "health and safety protocols", "health and safety", "covid", "covid-19", "protocols"]
    return n not in {"placed on il", "placed on il (p)"} and not any(x in n for x in excluded)

def scrape(url: str, output: Path) -> None:
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    links = [a.get("href") for a in soup.find_all("a")]
    urls = [url] + ["https://www.prosportstransactions.com/basketball/Search/" + x for x in links[4:-4] if x]
    rows = []
    for i, page in enumerate(urls):
        table = pd.read_html(page)[0]
        table = table.iloc[1:].copy()
        table.columns = ["Date", "Team", "Acquired", "Relinquished", "Notes"]
        for col in ["Acquired", "Relinquished"]:
            table[col] = table[col].astype("string").str.replace(r"^\s*[•·]\s*", "", regex=True)
        rows.append(table)
        if i < len(urls) - 1:
            time.sleep(2)
    output.parent.mkdir(parents=True, exist_ok=True)
    pd.concat(rows, ignore_index=True).drop_duplicates().to_csv(output, index=False)

def read_raw(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(columns={"Unnamed: 0": "source_row"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Notes"] = df["Notes"].fillna("").astype(str).str.strip()
    df["Player"] = df["Relinquished"].map(clean_player)
    df["Team"] = [normalize_team(team, date) for team, date in zip(df["Team"], df["Date"])]
    return df[df["Date"].notna() & df["Player"].ne("") & df["Team"].notna()].copy()

def read_transactions(path: Path) -> pd.DataFrame:
    """Read all transactions, including activation rows with no Relinquished player."""
    df = pd.read_csv(path)
    df = df.rename(columns={"Unnamed: 0": "source_row"})
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df["Notes"] = df["Notes"].fillna("").astype(str).str.strip()
    df["Team"] = [normalize_team(team, date) for team, date in zip(df["Team"], df["Date"])]
    return df[df["Date"].notna()].copy()

def read_kaggle_sources(path: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Split Kaggle's combined Prosports archive into injury and IL events."""
    all_events = read_transactions(path)
    all_events = all_events[all_events["Date"] >= pd.Timestamp("2000-01-01")].copy()
    all_events["Player"] = all_events["Relinquished"].map(clean_player)
    placement = all_events["Notes"].str.contains(
        r"placed on (il|injured list|inactive list|disabled list)", case=False, regex=True, na=False
    )
    starts = all_events[all_events["Acquired"].isna() & all_events["Relinquished"].notna()].copy()
    il = starts[placement.loc[starts.index] & starts["Notes"].map(is_injury)].copy()
    missed = starts[~placement.loc[starts.index] & starts["Notes"].map(is_injury)].copy()
    return missed, il, all_events

def load_schedule() -> pd.DataFrame:
    paths = [RAW / "all_teams_schedule_2010_2020.csv"]
    historical = RAW / "all_teams_schedule_2000_2009.csv"
    if historical.exists():
        paths.append(historical)
    schedule = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    schedule["Date"] = pd.to_datetime(schedule["Date"], errors="coerce")
    schedule["Team"] = [normalize_team(team, date) for team, date in zip(schedule["Team"], schedule["Date"])]
    return schedule[schedule["Date"].notna()].drop_duplicates(subset=["Team", "Date", "Opponent", "Season"]).copy()

def load_bref_counts() -> pd.DataFrame:
    """Load manually or programmatically verified Basketball Reference counts."""
    path = RAW / "basketball_reference_game_log_backfill.csv"
    if not path.exists():
        return pd.DataFrame(columns=["Player", "Team", "Date", "number of missed games"])
    counts = pd.read_csv(path, parse_dates=["Date"])
    counts["Player"] = counts["Player"].map(clean_player)
    counts["Team"] = [normalize_team(team, date) for team, date in zip(counts["Team"], counts["Date"])]
    counts["number of missed games"] = pd.to_numeric(counts["number of missed games"], errors="coerce")
    return counts.dropna(subset=["Player", "Team", "Date", "number of missed games"])

def is_major_injury(value: object) -> bool:
    """A major injury is at least 30 missed games or explicitly season-ending."""
    if isinstance(value, str):
        if value.strip().lower() == "season ending":
            return True
        try:
            return float(value) >= 30
        except ValueError:
            return False
    return pd.notna(value) and float(value) >= 30

def add_future_major_injury_metrics(rows: pd.DataFrame) -> pd.DataFrame:
    """Add three-year future-major-injury flags and the first qualifying date."""
    rows = rows.copy()
    rows["Major Injury in Next 3 Years"] = "No"
    rows["Major Injury in Next 3 Years - Same Body Part"] = "No"
    rows["Next Major Injury Date"] = pd.NaT
    major = rows["number of missed games"].map(is_major_injury)
    for _, player_rows in rows.groupby("Player", sort=False):
        player_rows = player_rows.sort_values("Date")
        major_rows = player_rows.loc[major.loc[player_rows.index]]
        if major_rows.empty:
            continue
        for index, row in player_rows.iterrows():
            future = major_rows[(major_rows["Date"] > row["Date"]) & (major_rows["Date"] <= row["Date"] + pd.DateOffset(years=3))]
            if future.empty:
                continue
            first = future.iloc[0]
            rows.at[index, "Major Injury in Next 3 Years"] = "Yes"
            rows.at[index, "Next Major Injury Date"] = first["Date"]
            if not future[future["Body Part"] == row["Body Part"]].empty:
                rows.at[index, "Major Injury in Next 3 Years - Same Body Part"] = "Yes"
    return rows

def season_ending(note: str) -> bool:
    return bool(re.search(r"out for (the )?season|season ending|remainder of (the )?season", note, re.I))

def build() -> pd.DataFrame:
    kaggle_path = RAW / "kaggle_nba_injury_stats_1951_2023.csv"
    if kaggle_path.exists():
        _, kaggle_il, all_events = read_kaggle_sources(kaggle_path)
        # Kaggle supplies the long historical IL archive. Preserve the
        # separate missed-game archive for 2010–2019, where it contains the
        # injury date that can precede the later IL placement.
        missed = read_raw(RAW / "prosportstransactions_scrape_missedgames_2010_2019.csv")
        missed = missed[missed["Relinquished"].notna() & missed["Notes"].map(is_injury)].copy()
        il = kaggle_il
        legacy_il = read_raw(RAW / "prosportstransactions_scrape_IRL_2010_2019.csv")
        legacy_il = legacy_il[legacy_il["Acquired"].isna() & legacy_il["Relinquished"].notna() & legacy_il["Notes"].map(is_injury)].copy()
        il = pd.concat([il, legacy_il], ignore_index=True).drop_duplicates(subset=["Date", "Team", "Player", "Notes"])
        il_all = all_events
        mg_all = read_transactions(RAW / "prosportstransactions_scrape_missedgames_2010_2019.csv")
    else:
        missed = read_raw(RAW / "prosportstransactions_scrape_missedgames_2010_2019.csv")
        il = read_raw(RAW / "prosportstransactions_scrape_IRL_2010_2019.csv")
        missed = missed[missed["Relinquished"].notna() & missed["Notes"].map(is_injury)].copy()
        il = il[il["Acquired"].isna() & il["Relinquished"].notna() & il["Notes"].map(is_injury)].copy()

    # An injury can be recorded twice on the same date: once as a missed-game
    # event and once as an IL placement. Prefer the IL note because it is the
    # episode-level record and contains the more useful description.
    il_keys = set(zip(il.Player, il.Team, il.Date))
    missed = missed[[key not in il_keys for key in zip(missed.Player, missed.Team, missed.Date)]].copy()

    # Activation/return events define the end of an injury episode. We use
    # both Prosports tables because short DTD injuries often return through
    # the missed-game table rather than the IL table.
    if not kaggle_path.exists():
        il_all = read_transactions(RAW / "prosportstransactions_scrape_IRL_2010_2019.csv")
        mg_all = read_transactions(RAW / "prosportstransactions_scrape_missedgames_2010_2019.csv")
    activations = pd.concat([
        il_all[il_all["Acquired"].notna()][["Date", "Team", "Acquired"]].assign(Player=lambda x: x.Acquired.map(clean_player)),
        mg_all[mg_all["Acquired"].notna()][["Date", "Team", "Acquired"]].assign(Player=lambda x: x.Acquired.map(clean_player)),
    ], ignore_index=True)
    schedule = load_schedule()
    bref_counts = load_bref_counts()
    bref_keys = {
        (row.Player, row.Team, row.Date): int(row["number of missed games"])
        for _, row in bref_counts.iterrows()
    }

    starts = pd.concat([
        il.assign(_source="inactive_list"),
        missed.assign(_source="missed_game"),
    ], ignore_index=True).sort_values(["Player", "Team", "Date"])
    # Prosports can publish multiple missed-game notes on the same date for
    # one player. They are descriptions of one event, not separate injuries.
    combined_starts = []
    for _, group in starts.groupby(["Player", "Team", "Date"], sort=False):
        row = group.iloc[0].copy()
        row["Notes"] = " | ".join(dict.fromkeys(group["Notes"].tolist()))
        row["_source"] = "inactive_list" if (group["_source"] == "inactive_list").any() else "missed_game"
        combined_starts.append(row)
    starts = pd.DataFrame(combined_starts)
    episodes = []
    for _, r in starts.iterrows():
        future = activations[(activations.Player == r.Player) & (activations.Team == r.Team) & (activations.Date > r.Date) & (activations.Date <= r.Date + pd.Timedelta(days=90))].sort_values("Date")
        end = future.iloc[0].Date if not future.empty else None
        is_season_ending = season_ending(r.Notes)
        item = {"Player": r.Player, "Team": r.Team, "Date": r.Date, "count_start": r.Date if r._source == "inactive_list" else None, "end": None if is_season_ending else end, "season_ending": is_season_ending, "Notes": r.Notes}
        if episodes and item["Player"] == episodes[-1]["Player"] and item["Team"] == episodes[-1]["Team"]:
            previous = episodes[-1]
            overlaps = (
                previous["end"] is not None and item["Date"] < previous["end"]
            ) or (
                previous["season_ending"] and item["Date"] <= previous["Date"] + pd.Timedelta(days=90)
            )
            if overlaps:
                previous["end"] = max(x for x in [previous["end"], item["end"]] if x is not None) if previous["end"] is not None or item["end"] is not None else None
                if item["count_start"] is not None:
                    previous["count_start"] = min(x for x in [previous["count_start"], item["count_start"]] if x is not None)
                previous["season_ending"] = previous["season_ending"] or item["season_ending"]
                if item["Notes"] not in previous["Notes"].split(" | "):
                    previous["Notes"] += " | " + item["Notes"]
                continue
        episodes.append(item)

    rows = []
    for episode in episodes:
        key = (episode["Player"], episode["Team"], episode["Date"])
        if episode["season_ending"]:
            count = "season ending"
        elif key in bref_keys:
            count = bref_keys[key]
        elif episode["end"] is None:
            count = "unknown"
        else:
            count_start = episode["count_start"] or episode["Date"]
            team_schedule = schedule[schedule.Team == episode["Team"]]
            if team_schedule.empty or count_start < team_schedule.Date.min() or episode["end"] > team_schedule.Date.max() + pd.Timedelta(days=1):
                count = "unknown"
            else:
                count = int(((schedule.Team == episode["Team"]) & (schedule.Date >= count_start) & (schedule.Date < episode["end"])).sum())
        rows.append({"Player": episode["Player"], "Team": episode["Team"], "Date": episode["Date"], "Body Part": body_part(episode["Notes"]), "Injury Description (Raw)": episode["Notes"], "number of missed games": count})
    out = pd.DataFrame(rows).sort_values(["Date", "Player"], ignore_index=True)
    out = add_future_major_injury_metrics(out[["Player", "Team", "Date", "Body Part", "Injury Description (Raw)", "number of missed games"]])
    return enrich_demographics(out)

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scrape", action="store_true", help="scrape fresh Prosports files before building")
    parser.add_argument("--begin-date", default="2000-01-01")
    parser.add_argument("--end-date", default="2026-07-26")
    args = parser.parse_args()
    if args.scrape:
        base = "https://www.prosportstransactions.com/basketball/Search/SearchResults.php?Player=&Team=&BeginDate={}&EndDate={}&{}&Submit=Search"
        scrape(base.format(args.begin_date, args.end_date, "InjuriesChkBx=yes&PersonalChkBx=yes"), RAW / "prosportstransactions_scrape_missedgames_2010_2019.csv")
        scrape(base.format(args.begin_date, args.end_date, "ILChkBx=yes"), RAW / "prosportstransactions_scrape_IRL_2010_2019.csv")
    result = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {len(result):,} rows to {OUT}")

if __name__ == "__main__":
    main()
