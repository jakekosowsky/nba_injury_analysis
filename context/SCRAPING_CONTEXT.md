# Scraping context

This file records the requirements, sources, methodology, audit rules, and limitations used to build `notebooks/01_scrape_sources.ipynb` and the scripts in `src/`.

## Requirements

The acquisition layer must:

1. Preserve the original source text and raw files before any cleaning.
2. Collect player, team, transaction date, acquired/relinquished status, and the complete injury Notes field.
3. Collect regular-season team-game dates and actual player minutes so missed games and confirmed returns can be calculated later.
4. Collect player birth date, height, and weight for demographics.
5. Collect season-level VORP and minutes for all seasons needed by the three-season pre/post windows.
6. Cache requests, rate-limit repeated page retrieval, and never replace an unavailable source with invented rows.
7. Keep partial post-2023 official injury-report data separate until coverage is complete enough to merge without bias.

## Sources

### Pro Sports Transactions

- Entry point: https://www.prosportstransactions.com/basketball/Search/Search.php
- Role: primary injury-event source.
- Fields used: date, team, acquired player, relinquished player, and Notes.
- Query types: missed-game/injury transactions and inactive-list transactions.
- Important limitation: Cloudflare can return HTTP 403. The notebook leaves failed downloads visible and never labels a blocked date range complete.

### Official NBA team box scores

- Entry point: https://www.nba.com/stats/teams/boxscores
- Role: regular-season team-game dates and player rows with actual minutes.
- Use: confirm the first post-injury appearance, exclude DNP-only roster rows, and measure games played after return.

### Basketball-Reference

- Entry point: https://www.basketball-reference.com/
- Role: historical team schedules, player game-log audits, player biographies, and advanced season tables containing VORP.
- VORP seasons: 1997–2026 in the current union.
- Requests are cached locally and should be run politely.

### Historical Prosports archive

- Kaggle archive: https://www.kaggle.com/datasets/loganlauton/nba-injury-stats-1951-2023
- Role: reproducible historical archive and cross-check through April 2023.
- Caveat: this archive was scraped from Pro Sports Transactions, so it is not an independent medical source.

## Acquisition methodology

1. Create `data/raw/`, `data/processed/`, and `data/audits/` if they do not exist.
2. Query Pro Sports Transactions separately for injury/missed-game rows and inactive-list rows.
3. Follow pagination, remove repeated headers, preserve the full Notes field, and deduplicate exact source rows.
4. Download or copy the historical Prosports archive into `data/raw/kaggle_nba_injury_stats_1951_2023.csv`.
5. Download historical team schedules with `src/download_historical_schedules.py` and store one row per team-game.
6. Retrieve Basketball-Reference advanced tables with `src/ingest_vorp.py`; cache every season page before parsing.
7. Acquire regular-season player box scores separately and retain only rows with actual minutes when creating appearance tables.
8. Write a source inventory showing file name, row count, date range, schema, duplicate count, and retrieval status.

## Acquisition audits

Every raw source should pass these checks before cleaning:

- Required columns exist and date parsing succeeds.
- The earliest and latest dates match the intended coverage.
- Exact duplicate rows are counted and removed deterministically.
- Team schedules have no duplicate team/date combinations and normal seasons contain the expected number of team-games.
- VORP tables have one canonical player-season row after total-team consolidation.
- Cached pages are large enough to be real responses rather than block pages.
- A failed request leaves an explicit failure record; it never creates an empty “complete” file.

Historical injury coverage was cross-checked on 50 cases against the Kaggle archive. A separate 30-case Basketball-Reference audit checks injury-date availability and the first later appearance. Medical wording remains sourced from Prosports Notes; game logs validate availability rather than diagnosis.

## Known limitations

- The core injury archive currently ends on April 9, 2023.
- Official NBA injury-report retrieval after that date is incomplete and remains outside the core table.
- Basketball-Reference game logs can validate returns but usually do not repeat the medical description.
- Scrapers may require reruns because of throttling, HTML changes, or Cloudflare blocking.
- Raw source licensing and access rules should be reviewed before redistributing complete archives.

