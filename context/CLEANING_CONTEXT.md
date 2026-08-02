# Cleaning context

This file records the requirements, source joins, methodology, and audits used to build `notebooks/02_clean_injuries.ipynb` and `src/build_dataset.py`.

## Required output

The core injury-episode table must contain:

`Player, Team, Date, Body Part, Injury Description (Raw), number of missed games, Major Injury in Next 3 Years, Major Injury in Next 3 Years - Same Body Part, Next Major Injury Date, Height (inches), Weight (lb), Age at Injury`

The build also retains resolution source, confirmed return date, and review status when available so every duration can be audited.

## Source joins

| Source | Join keys | Purpose |
|---|---|---|
| Prosports injury and IL rows | normalized player, historical team, date | Start injury episodes and retain raw Notes |
| Activation transactions | normalized player, historical team, later date | Candidate episode endpoint |
| Team schedules | historical team, date range | Count scheduled games missed |
| Player appearances | normalized player, team, game date | Confirm the first actual return |
| Player biographies | normalized name and active-year range | Add height, weight, and age at injury |
| VORP player-seasons | canonical/aliased player name and season | Build pre/post performance windows |

## Cleaning methodology

1. Parse dates and standardize player names without punctuation, suffix noise, or parenthetical annotations.
2. Normalize teams to their historical names so transactions join to the correct schedule.
3. Remove rest, illness, personal leave, suspensions, health-and-safety protocols, and non-injury roster moves.
4. Retain the original Notes text and derive a normalized body part with an ordered keyword hierarchy.
5. Categorize MCL injuries as `knee`.
6. Combine same-player/team/date DNP and inactive-list rows into one start event; keep distinct Notes joined with ` | `.
7. Collapse continuation rows that overlap an open episode rather than counting them as new injuries.
8. Resolve the endpoint from activation transactions or the first later appearance with actual minutes.
9. Count team games from the episode start through the day before the confirmed return.
10. Use `season ending` only when the Notes or game-log evidence supports no same-season return; use `unknown` when no defensible endpoint exists.
11. Enrich demographics from the biography table and compute exact age on the injury date.
12. Define a major injury as at least 30 missed games or `season ending`; `unknown` is not major.
13. Search each player's later episodes through the inclusive three-year window for any major injury and for a major injury to the same normalized body part.

## VORP and availability methodology

- Availability is the share of scheduled regular-season games played after a confirmed return.
- VORP comparisons use three complete seasons before and three complete seasons after the injury/return window.
- Expected VORP is the same player's prior healthy production adjusted by the league aging curve.
- Traded-player VORP uses the total-team row when available; otherwise team rows are summed.
- Partial VORP windows remain labeled partial rather than being pooled silently with complete windows.

## Required audits

The cleaner must verify:

- No duplicate player/team/date episode keys.
- No missing required columns.
- Numeric missed-game values are between 0 and 82 for regular-season-only episodes.
- `30` is major, `29` is not, `season ending` is major, and `unknown` is not.
- Future injuries occur strictly after the index date and no later than three calendar years afterward.
- Same-body recurrence uses the normalized body part, including MCL-to-knee mapping.
- DNP roster rows without minutes do not count as appearances.
- A return on another team is not treated as a same-team activation without separate evidence.

### Regression cases

| Player | Injury date | Expected result |
|---|---|---|
| Darren Collison | 2018-02-05 | 11 missed games |
| Isaiah Whitehead | 2017-01-13 | 1 missed game |
| Enes Kanter | 2017-01-26 | 10 missed games |
| Glen Davis | 2013-02-01 | Season-ending; next-season return is not a next-day reinjury |
| Rajon Rondo | 2013-10-29 | Continuing ACL recovery, not a new ACL injury episode |

The current full-row audit recomputed the future-major metrics for all 12,165 episodes. The final resolution audit leaves unresolved endpoints as `unknown` rather than creating false precision.

## Known limitations and interpretation

- `season ending` can include a late-season injury with few remaining games; downstream analysis should also inspect actual missed games and injury evidence.
- Older unresolved cases can remain unknown when no activation or reliable game-log endpoint exists.
- Height, age, and VORP matching are intentionally conservative; unmatched records remain missing.
- Injury type, age, and height results are descriptive associations, not causal effects.

