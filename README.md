# ECAC Analytics — Harvard Women's Hockey

An internal analytics tool for tracking and reporting advanced hockey statistics for the Harvard women's hockey program. Raw data is sourced from [49ing Data Cockpit](https://49ing.ch) and entered manually after each game. The tool computes derived stats, stores season-long history, and generates printable PDF reports for players and the team.

---

## Stack

| Layer | Tech |
|---|---|
| Backend | Python · FastAPI · SQLAlchemy · SQLite |
| Frontend | React · TypeScript · Vite |
| PDF reports | WeasyPrint · Jinja2 HTML templates |
| Data source | 49ing Data Cockpit (video tagging platform) |

---

## Running locally

**Prerequisites:** Python 3.9+, Node 18+, Homebrew (macOS)

```bash
# Install WeasyPrint system dependencies (macOS)
brew install pango libffi

# Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python migrate_v4.py   # run any pending migrations

# Frontend
cd ../frontend
npm install

# Start both servers (sets required DYLD_LIBRARY_PATH for WeasyPrint)
cd ..
./start.sh
```

The frontend runs on `http://localhost:5173` and the API on `http://localhost:8000`.

---

## Features

- **Game log** — record opponent, date, location, and season per game
- **Team stats entry** — 5v5 core, special teams (PP/PK), and attack scenario mix per game
- **Player stats entry** — spreadsheet-style table: all players visible at once, organized by stat group to match 49ing's layout
- **Aggregate stats** — season totals with Last 1 / Last 3 / Last 5 / Last 10 / All / Custom date filters
- **PDF reports** — per-player and team-wide reports with sparkline trend charts
- **Methodology page** — in-app documentation for every tracked stat

---

## Stat Methodology

All stats default to **5v5 strength state** unless labeled otherwise. Raw inputs come from 49ing's Data Cockpit; derived stats are computed by the backend.

> **Caveats before interpreting any number:**
> - Most research validating Corsi, Fenwick, and xG model behavior comes from men's professional hockey (NHL). These methods have not been specifically validated for women's college hockey.
> - ECAC's ~28-game regular season is shorter than the samples on which these stats were developed. Early-season numbers (first 8–10 games) deserve substantially more caution than late-season totals.
> - Stats that stabilize fastest given the sample size: **CF%** (~20–30 games), **xGF%** (~30–50 games). Goals and shooting percentage require 150–300+ games to stabilize and are not tracked here.

---

### Team Stats

#### 1. Possession Share — CF%
> *"Who controlled the puck?"*

```
CF% = CF For ÷ (CF For + CF Against)
```

Corsi counts every shot attempt — goals, on-goal, missed, and blocked — so it uses far more data per game than on-goal shots alone. More events per game means less randomness and a more reliable signal about which team was actually in control.

---

#### 2. Quality Shot Share — xGF%
> *"Who got the better chances?"*

```
xGF% = xGF ÷ (xGF + xGA)
```

Expected goals (xG) models the goal probability of each unblocked shot using location and shot type. Summing these probabilities gives a volume-adjusted picture of shot quality that is more stable game-to-game than counting actual goals, which are heavily influenced by save quality and randomness.

---

#### 3. Offense Created / Defense Exposed — xGF60 / xGA60
> *"How often were we generating or surrendering quality chances, normalized to a full game?"*

```
xGF60 = (xGF ÷ TOI) × 60
xGA60 = (xGA ÷ TOI) × 60
```

Rate stats remove the effect of TOI differences between games and allow fair comparison across a season. Using xG rather than goals makes the rate more stable.

---

#### 4. Special Teams Splits — 5v4 / 4v5
> *"How effective are we on the power play and penalty kill?"*

```
5v4 CF% = CF For (5v4) ÷ (CF For + CF Against at 5v4)
5v4 xGF% = xGF (5v4) ÷ (xGF + xGA at 5v4)   [same pattern for 4v5]
```

Special teams sample sizes are too small for goal-based measures to stabilize within a season. Corsi and xG use more events per game and give a clearer read on PP/PK structure earlier.

---

#### 5. Attack Scenario Mix
> *"How are we generating our chances — off rushes, forechecks, faceoffs, or sustained pressure?"*

```
Share = scenario xGF ÷ total xGF across all scenarios
```

Scenarios (from 49ing's Attack Scenarios tab, 5v5 filter):
- **Rush** — zone entry followed by a shot within 5 seconds
- **OZ Forecheck** — forecheck possession followed by a shot within 5 seconds
- **OZ Faceoff** — offensive zone faceoff win followed by a shot within 5 seconds
- **Sustained Possession** — 5+ seconds of continuous OZ possession leading to a shot

Mix is xG-weighted (scoring threat share), not frequency-weighted, because 49ing only exposes xG totals per scenario — not shot-attempt counts. Every shot is bucketed into exactly one scenario; rebounds are credited to the originating scenario.

---

### Player Stats

All on-ice player stats measure **what the team does while that player is on the ice** — they are not personal output stats. ICF and ISF are the only stats personal to the individual player.

49ing reports all per-60 values pre-scaled; they are entered directly without recomputation.

---

#### 6. Territorial Impact — On-Ice CF% / xGF% / SF%
> *"Does this player help the team control play and generate quality chances?"*

```
On-Ice CF%  = CF For (on ice) ÷ (CF For + CF Against while on ice)
On-Ice xGF% = xGF (on ice) ÷ (xGF + xGA while on ice)
On-Ice SF%  = SF For (on ice) ÷ (SF For + SF Against while on ice)
```

A player can drive shots and suppress danger without scoring — raw goals don't capture this. On-ice percentage stats measure the team's collective performance during that player's shifts, reflecting her true territorial impact.

---

#### 7. Offensive Drive / Defensive Hold — CF60 / CA60 / FF60 / FA60 / SF60 / SA60
> *"How fast does she drive shot volume for and against?"*

```
CF60, FF60, SF60 = on-ice team shot attempts / unblocked / on-goal per 60 min TOI
CA60, FA60, SA60 = same metrics for opponent output while on ice
```

Reported directly by 49ing pre-scaled to 60-min equivalents. Per-60 rates normalize for ice time, making it fair to compare a player with 8 min TOI to one with 20 min. The three tiers:
- **Corsi (CF/CA)** — all shot attempts including blocked
- **Fenwick (FF/FA)** — unblocked only; removes the blocker's role
- **Shots (SF/SA)** — on-goal only; strictest threshold

Season aggregates use TOI-weighted averages: `season CF60 = Σ(CF60ᵢ × TOIᵢ) / Σ(TOIᵢ)`.

---

#### 8. Shot Quality — xFSh% / xFSv%
> *"How dangerous are the shots with her on ice — and how well does she suppress danger?"*

```
xFSh% = xGF60 ÷ FF60   (avg danger per unblocked shot for; the per-60 scaling cancels)
xFSv% = 1 − (xGA60 ÷ FA60)   (danger suppressed per unblocked shot against)
```

Volume of unblocked shots (FF/FA) tells you one thing; quality tells you another. A player can be on the ice for lots of low-danger shots — xFSh%/xFSv% reveal whether the shots she is involved in are high- or low-danger, independent of volume.

---

#### 9. Deployment — Median Shift Length / TOI
> *"What's her usage context?"*

```
Shift Length = median shift length in seconds (not mean)
TOI          = total 5v5 ice time in minutes
```

Median shift length is used deliberately — it is robust to outlier long shifts that would inflate the mean. TOI contextualizes all rate stats; a player with 8 min 5v5 TOI and one with 20 min are generating stats over very different samples.

*Not tracked: Zone Start Ratio (ZSR). 49ing does not expose per-player offensive/defensive zone faceoff counts.*

---

#### 10. Individual Shooting — ICF / ISF
> *"How much is she personally shooting?"*

```
ICF = individual shot attempts taken by this player (raw game total)
ISF = individual shots on goal by this player (raw game total)
```

The only stats here that are purely personal to the player, not team on-ice totals. Captures offensive zone presence and shooting volume independent of linemates.

---

#### 11. Faceoff Battle — FO% (Forwards)
> *"How well does she win draws?"*

```
Personal Draw Win%  = Personal Draws Won ÷ Personal Draws Taken
On-Ice Team FO%     = Team FO Wins (on ice) ÷ (Team FO Wins + Losses while on ice)
```

49ing's "FO%" label is ambiguous between two distinct measures: (a) the player's own draw win rate, and (b) the team's overall faceoff win rate while that player is on the ice (which includes teammates' draws). Both are captured and displayed separately until confirmed with 49ing's team.

---

#### Not Tracked

| Stat | Reason |
|---|---|
| Rel. xGF% | 49ing does not expose off-ice stats per player. Computing relative impact requires play-by-play tracking data not available through the Data Cockpit. |
| Zone Start Ratio (ZSR) | 49ing does not expose per-player OZ/DZ faceoff counts. |
| Win Probability Trend | 49ing's xG chart plots each individual shot's probability as a point — it does not expose cumulative per-period xGF/xGA as a readable number. Visual estimation from the chart is not accurate enough to enter reliably. |

---

## Data source

All raw inputs come from [49ing's Data Cockpit](https://49ing.ch) platform, which auto-tags video and generates advanced hockey stats. Stat definitions follow 49ing's glossary — not generic hockey-analytics conventions, as some definitions differ.
