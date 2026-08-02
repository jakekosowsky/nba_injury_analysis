#!/usr/bin/env python3
"""Download Basketball Reference team schedules for seasons 1999-00 through 2009-10.

The reference project only bundled 2010-2019 schedules. This downloader keeps
the same game-level columns and adds the missing historical coverage needed by
the injury-duration calculation.
"""
from pathlib import Path
import time

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
OUT = RAW / "all_teams_schedule_2000_2009.csv"

# Basketball Reference franchise codes. The code can change when a franchise
# changes city/name, so aliases are listed separately where necessary.
TEAM_CODES = [
    "ATL", "BOS", "CHH", "CHA", "CHI", "CLE", "DAL", "DEN", "DET",
    "GSW", "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN",
    "NJN", "NOH", "NYK", "ORL", "PHI", "PHO", "POR", "SAC", "SEA",
    "SAS", "TOR", "UTA", "WAS",
]

def team_name(code: str, date: pd.Timestamp) -> str:
    if code == "NJN":
        return "New Jersey Nets"
    if code == "CHH":
        return "Charlotte Hornets"
    if code == "CHA":
        return "Charlotte Bobcats" if date.year < 2014 else "Charlotte Hornets"
    if code == "NOH":
        return "New Orleans Hornets"
    if code == "MEM":
        return "Vancouver Grizzlies" if date.year < 2001 else "Memphis Grizzlies"
    names = {
        "ATL":"Atlanta Hawks", "BOS":"Boston Celtics", "CHI":"Chicago Bulls",
        "CLE":"Cleveland Cavaliers", "DAL":"Dallas Mavericks", "DEN":"Denver Nuggets",
        "DET":"Detroit Pistons", "GSW":"Golden State Warriors", "HOU":"Houston Rockets",
        "IND":"Indiana Pacers", "LAC":"Los Angeles Clippers", "LAL":"Los Angeles Lakers",
        "MIA":"Miami Heat", "MIL":"Milwaukee Bucks", "MIN":"Minnesota Timberwolves",
        "NYK":"New York Knicks", "ORL":"Orlando Magic", "PHI":"Philadelphia 76ers",
        "PHO":"Phoenix Suns", "POR":"Portland Trail Blazers", "SAC":"Sacramento Kings",
        "SEA":"Seattle SuperSonics", "SAS":"San Antonio Spurs", "TOR":"Toronto Raptors",
        "UTA":"Utah Jazz", "WAS":"Washington Wizards",
    }
    return names[code]

def parse_table(html: str, code: str, page_year: int) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for table_id, season_type in (("games", "regular"), ("games_playoffs", "post")):
        table = soup.find("table", id=table_id)
        if table is None:
            continue
        for tr in table.find_all("tr"):
            date_cell = tr.find(attrs={"data-stat": "date_game"})
            opp_cell = tr.find(attrs={"data-stat": "opp_name"})
            if date_cell is None or opp_cell is None:
                continue
            date = pd.to_datetime(date_cell.get("csk"), errors="coerce")
            if pd.isna(date):
                continue
            location = tr.find(attrs={"data-stat": "game_location"})
            opponent = opp_cell.get_text(" ", strip=True)
            overtime = tr.find(attrs={"data-stat": "overtimes"})
            rows.append({
                "Team": team_name(code, date),
                "Year": page_year - 1,
                "Season": season_type,
                "Game_num": tr.find(attrs={"data-stat": "g"}).get_text(strip=True),
                "Date": date.strftime("%Y-%m-%d"),
                "Away_flag": int(location is not None and location.get_text(strip=True) == "@"),
                "Opponent": opponent,
                "OT_flag": overtime.get_text(strip=True) if overtime is not None else pd.NA,
            })
    return rows

def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; NBA-injury-research/1.0)"})
    rows = []
    failures = []
    # page_year 2000 is the 1999-00 season; page_year 2010 is 2009-10.
    for page_year in range(2000, 2011):
        for code in TEAM_CODES:
            url = f"https://www.basketball-reference.com/teams/{code}/{page_year}_games.html"
            try:
                response = session.get(url, timeout=30)
                if response.status_code != 200:
                    failures.append((code, page_year, response.status_code))
                else:
                    rows.extend(parse_table(response.text, code, page_year))
            except Exception as exc:
                failures.append((code, page_year, repr(exc)))
            time.sleep(0.35)
    out = pd.DataFrame(rows)
    if out.empty:
        raise RuntimeError(f"No schedule rows downloaded; failures={failures[:5]}")
    out["Date"] = pd.to_datetime(out["Date"])
    out = out.drop_duplicates(subset=["Team", "Date", "Opponent", "Season"])
    out = out.sort_values(["Date", "Team", "Season", "Game_num"])
    out.insert(0, "Unnamed: 0", range(len(out)))
    RAW.mkdir(parents=True, exist_ok=True)
    out.to_csv(OUT, index=False, date_format="%Y-%m-%d")
    print(f"Wrote {len(out):,} rows to {OUT}")
    print(f"Date range: {out.Date.min().date()} to {out.Date.max().date()}")
    print(f"Failures: {len(failures)}")
    if failures:
        print(failures[:20])

if __name__ == "__main__":
    main()
