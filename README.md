# Valuing NBA Players After Major Injuries

How should NBA front offices value players returning from major injuries? This project evaluates the factors that matter most: recurrence risk, future availability, and retained on-court value.

## Summary

- **Motivation:** Valuing a player after injury matters for trades and free agency. This analysis estimates how much a major injury should change projections of availability, reinjury risk, and on-court value.
- **Method:** Approximately 600 major injury episodes from the past 25 NBA seasons are linked with NBA game logs and performance data. Post-return outcomes account for age, height, prior VORP, and injury mix.
- **Overall impact:** Relative to the baseline, injured players produce about 20% less VORP than expected, are roughly one-third more likely to suffer another major injury, and play 8% fewer games over the next three seasons.
- **Injury type:** Hand injuries show little measurable decline, while ankle and foot injuries are the most costly.
- **Age:** Older players lose substantially more expected VORP after a major injury.

## Detailed methodology

- **Sample:** Approximately 600 major injury episodes from the past 25 NBA seasons.
- **Major injury definition:** A confirmed surgery, tear or rupture, or fracture that resulted in at least 30 missed games or a validated season-ending absence.
- **Follow-up:** Reinjury and availability are measured over the next 246 team games after confirmed return. VORP is measured over the player's first three full seasons back.
- **Comparison group:** The injury sample includes all qualifying major-injury episodes. The no-injury baseline uses top-10 rotation player-seasons, reducing the exposure bias that would arise from comparing injured players with end-of-bench players who rarely play.
- **Controls:** Models account for age, height, pre-injury VORP, and injury mix. Expected VORP follows the same injured player's projected no-injury path based on prior healthy production and the league aging curve.

We evaluate injured players on three outcomes that drive front-office value:

| Metric | Definition | Front-office lens |
|---|---|---|
| Major injury risk after return | Probability of any subsequent major injury during the next 246 team games after confirmed return. Results report overall major-injury risk and separately identify same-body-part reinjuries, which are a subset of the overall risk. | Recurrence risk |
| Games played proportion | Share of the next 246 team games in which the player appears after confirmed return. | Availability |
| VORP lost | Percentage of expected VORP not produced during the player's first three full seasons back. | Retained on-court value |

Expected VORP is the projected path for the same player without the injury, based on prior healthy production and the league's typical aging curve. It is not the performance of a separate comparison player.

## Data acquisition

- [Pro Sports Transactions](https://www.prosportstransactions.com/basketball/Search/Search.php) provides player, team, injury date, and raw injury descriptions.
- [Official NBA team box scores](https://www.nba.com/stats/teams/boxscores) provide game dates and player minutes used to count missed games, confirm returns, and measure post-return availability.
- [Basketball-Reference](https://www.basketball-reference.com/) provides historical schedules, game logs, player biographies, minutes, and VORP.

The full acquisition and merge logic is documented in the [scraping context](context/SCRAPING_CONTEXT.md) and [cleaning context](context/CLEANING_CONTEXT.md).

## Documentation

- [Scraping requirements, sources, methodology, and audits](context/SCRAPING_CONTEXT.md)
- [Cleaning rules, joins, outcome definitions, and regression checks](context/CLEANING_CONTEXT.md)
- [Source-acquisition notebook](notebooks/01_scrape_sources.ipynb)
- [Cleaning and dataset-build notebook](notebooks/02_clean_injuries.ipynb)
- [Recovery and player-value analysis notebook](notebooks/03_analyze_recovery.ipynb)
- [Thirty-case outcome audit](data/analysis/adjusted_multimetric_30_case_audit.csv)
- [Analysis-ready episode data](data/analysis/adjusted_multimetric_episode_data.csv)

## Findings

### Type of injury

Major injuries reduce future availability and on-court value, but the magnitude varies substantially by injury type. Injured players are about one-third more likely than the baseline to suffer another major injury over the next 246 team games (33.8% versus 25.0%) and play about 8% fewer games (64.5% versus 70.3%). Hand injuries show little measurable impact, while ankle and foot injuries show the largest penalties.

Players produce approximately 20% less VORP than expected after a major injury. Body-part estimates generally point in the same direction as the reinjury and availability results, but their confidence intervals overlap; the data do not support a precise ranking of injury types by VORP loss.

![Adjusted outcomes by injury type](assets/injury_type_adjusted_outcomes.png)

### Height

This analysis compares recovery within the major-injury cohort, not baseline injury risk by height. Same-body-part recurrence rises from 11.0% for players below 6'5" to 18.5% for players 6'10" and above after controlling for age and injury mix. Taller players also have larger estimated VORP losses, but only the recurrence difference is statistically significant. Height is therefore a recurrence-risk modifier, not an automatic valuation discount.

![Adjusted outcomes by height](assets/height_three_outcomes.png)

### Age

Age matters substantially for on-court value recovery. After accounting for normal age-related availability differences, injuries affect games played similarly across age groups. Estimated VORP loss is nearly three times as large for players age 27 and older, and the older group's loss is statistically significant. Age should therefore shape the expected performance rebound more than the availability forecast.

![Adjusted outcomes by age](assets/age_selected_three_charts.png)

## Repository structure

```text
notebooks/
  01_scrape_sources.ipynb      Acquire and inventory raw source data
  02_clean_injuries.ipynb      Build injury episodes and run cleaning audits
  03_analyze_recovery.ipynb    Produce the reinjury, availability, and VORP findings
context/
  SCRAPING_CONTEXT.md          Scraping requirements, sources, methodology, and audits
  CLEANING_CONTEXT.md          Cleaning rules, joins, methodology, and regression checks
src/                           Reusable scraper, builder, and audit scripts
data/analysis/                 Compact analysis inputs and audit extracts
assets/                        README figures
```

## Run the project

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
jupyter lab
```

Run the notebooks in numeric order. Raw source files are intentionally not committed; the scraping notebook explains how to acquire them and where to place archives that require manual download.

## Audit status and limitations

- The build consolidates 12,165 injury episodes from 2000 through April 2023.
- A 50-case Kaggle cross-check and a 30-case Basketball-Reference audit were used to verify injury descriptions, dates, teams, and return logic.
- Regression checks include Darren Collison (11 games), Isaiah Whitehead (1), and Enes Kanter (10).
- Unknown durations remain unknown rather than being imputed; they are never treated as major injuries.
- Official post-April-2023 injury coverage is incomplete and is not silently merged into the core injury table.
- Results are descriptive associations, not causal estimates. Retirement, roster selection, and small subgroups can affect availability and VORP estimates.

## Future work

- Estimate how multiple major injuries compound and whether their effects differ from a first major injury.
- Test whether playing through an injury increases the risk of a later major reinjury, quantifying the trade-off between short-term availability and long-term health.
- Apply the framework to college players to evaluate NBA draft prospects.
- Add complete post-2023 injury-report coverage.
- Test stricter same-structure and same-side recurrence definitions.
