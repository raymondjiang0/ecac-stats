# ECAC Stats Expansion — Design Spec

**Date:** 2026-08-18
**Author:** Raymond Jiang (w/ Claude)
**Status:** Approved for planning

---

## 1. Overview

The current tool tracks 5 team stats and 4 player stats sourced from 49ing's Data Cockpit, entered manually per game. The coaches have requested ~10 additional stats/features, several of which require raw data that 49ing does not expose but InStat does. Manual entry is also the largest ongoing pain point.

This spec covers:

1. Adopting InStat as a second, coexisting data source (schema-level).
2. Building an automated ingest pipeline for both PDFs (InStat) and screenshots (either platform), with Claude vision as the extractor for images.
3. Rolling out ~15 new stats across three tiers, plus one auto-flag layer for coach-visible anomalies.
4. Explicitly documenting what is not possible with either data source (with reasons).

The goal is to move the tool from a static per-game data-entry app into a proactive analytics tool: less time entering, more time coaching from the outputs.

---

## 2. Data source strategy

### Decision: Option B — source flag on `Game`, native storage per source

Both 49ing and InStat data may be entered for the same or different games throughout the season. The tool must handle:

- Games entered only from 49ing (per-60 rates, xG by attack scenario)
- Games entered only from InStat (raw counts, hit/pass matrices, puck battles by zone)
- Games with both sources ingested (rare but possible)

Each source is stored in its native shape. A `data_source` column on `Game` records which source(s) supplied data. When both are present for a game, **49ing values take precedence** for stats that both sources cover.

### Why not the alternatives

- **Option A (raw counts everywhere)** requires reverse-engineering raw counts from 49ing's per-60 values (multiply by TOI), which introduces rounding drift on every ingest. 49ing also doesn't publish all raw counts (attack-scenario xG is exposed only as a total).
- **Option C (convert InStat to 49ing shape)** discards InStat's unique detail — the hit matrix, pass matrix, and per-zone puck battles have no per-60 analog. This would delete the exact data that unlocks half the coach asks.

### Stat availability model

Each stat is declared with the set of sources it can be computed from. Aggregation queries filter to games where required source data exists. Player reports render "N/A (source not available for this window)" where applicable, so nothing lies about coverage.

---

## 3. Schema migration

### Changes to existing tables

**`Game`** — add:
```python
data_source = Column(String, nullable=False, default="49ing")
# values: "49ing" | "instat" | "both"
```

Migration backfills all existing rows to `"49ing"`. No other changes to existing tables — `PlayerGameStats` and `TeamGameStats` continue to hold 49ing-shape data.

### New tables

**`PlayerGameStatsInStat`** — raw counts per player per game, InStat-native fields:

```
player_id, game_id (FK, unique together)

Individual shooting:
  shots, shots_on_goal, blocked_shots
  pp_shots, pp_shots_on_goal

On-ice Corsi (raw):
  corsi_plus, corsi_minus

Physical:
  hits_delivered, hits_received

Puck battles (per zone):
  pb_won_dz, pb_total_dz
  pb_won_oz, pb_total_oz
  pb_won_nz, pb_total_nz

Turnovers/recoveries:
  puck_losses, puck_losses_dz
  puck_recoveries, puck_recoveries_oz

Zone entries:
  entries_pass, entries_stick, entries_dump
```

**`TeamGameStatsInStat`** — team-level InStat-only fields:

```
game_id (FK, unique)

Special teams detail:
  pp_shots, pp_time_seconds_in_oz, pp_time_seconds_total
  pk_opp_breakouts, pp_opp_breakouts_allowed

Puck possession (5v5):
  puck_possession_seconds_total
  oz_possession_seconds, oz_possession_pct

Shot quality (team):
  scoring_chance_shots, scoring_chance_shots_on_goal
```

Note: TOI, faceoffs, goals, assists remain on the existing `PlayerGameStats` table regardless of source — they're identical fields across both platforms.

### Aggregation layer

New module `app/stats/sources.py` declares source availability per stat:

```python
STAT_SOURCES = {
    "cf60":              {"49ing", "instat"},
    "xgf60":             {"49ing"},
    "puck_battle_pct":   {"instat"},
    "attack_scenario":   {"49ing"},
    "hits_delivered":    {"instat"},
    "entries_stick":     {"instat"},
    # ...
}
```

Aggregation queries filter game set by source availability before computing. UI shows "N/A" badges when a requested stat's source is missing for the window.

### Conflict resolution

When `data_source == "both"`, 49ing values win for overlapping fields. This is a per-source-of-truth call, not a computed merge.

### Migration steps

1. Alembic migration: add `data_source` column with default `"49ing"`, backfill existing rows.
2. Create `PlayerGameStatsInStat` and `TeamGameStatsInStat` tables.
3. Add `STAT_SOURCES` declaration + aggregation-layer filter logic.
4. UI: source picker at game creation; per-stat availability badges on player report.

**Estimated effort:** 3–4 days.

### Deferred to Phase 2 (post-ingest)

- `PlayerPassMatrix` — per-game, per-player-pair pass counts (from InStat page 10/18).
- `PlayerHitMatrix` — per-game, per-player-pair hit counts (InStat page 9/17).

These enable pass connectivity and hit engagement stats but are unreasonable to enter manually (~200 non-zero cells per game). Deferred until the ingest pipeline can populate them automatically. **Circle back on these — do not drop.**

---

## 4. Ingest pipeline

### Goal

One-upload workflow: user drops a file (PDF or screenshots), system extracts all fields it can find, user reviews and corrects, commits to DB. Manual per-field entry remains available in parallel.

### Input routing

| Input type | Extractor | Rationale |
|---|---|---|
| InStat PDF | `pdfplumber` text extraction + template-specific parser | InStat PDFs are text-layer, not scanned. Parsing is deterministic and ~100% accurate on structured tables. |
| Screenshot (any source) | Claude API vision → JSON via structured output | 49ing is a web dashboard; coaches may screenshot rather than export. Handles arbitrary image input. |
| Failed PDF parse | Fallback to vision on rendered page | Resilience to layout changes. |

### Template system

Each source page has a named template: input schema (fields to extract, expected types) + target DB table. Initial set:

- `instat_main_stats` — InStat page 3/11 (per-player TOI, Corsi, faceoffs, shots, hits)
- `instat_challenges` — InStat page 7/15 (puck battles by zone)
- `instat_turnovers_entries` — InStat page 3/11 lower blocks
- `instat_team_stats` — InStat page 2 (team-level, xG, possession, PP/PK)
- `49ing_on_ice_rates` — 49ing player tab screenshot
- `49ing_team_5v5` — 49ing team tab screenshot
- `49ing_attack_scenarios` — 49ing attack scenarios tab screenshot

Templates live in `app/ingest/templates.py` as config dictionaries — no code changes needed to add a new one.

### Auto-detection (single-upload UX)

**PDF path:** page 1 text sniff → detect InStat header → walk pages by header pattern (`"PLAYERS' STATS"`, `"CHALLENGES"`, `"GAME TIME DISTRIBUTION"`, etc.) → auto-run the matching template on each detected section. One PDF upload = ~5 template runs in one workflow.

**Screenshot path:** for each uploaded image, cheap first-pass vision call ("what page/tab is this from?") classifies the source. Confident matches auto-route to their template. Ambiguous images fall back to a "pick template" prompt.

### Extraction flow

```
1. User uploads file(s), picks target game
2. Server auto-detects → runs templates
3. Per-template validation:
     - jersey numbers match roster
     - numeric fields parse
     - "won / total" fields satisfy won ≤ total
     - Failed validations flagged, not rejected
4. Review UI:
     - Left sidebar: per-template tabs with status (✓ / ⚠️ / ✗)
     - Right: split-screen extracted-form + source page (zoomable)
     - Every field's original text on hover for verification
     - Save-draft supported
5. "Commit all" button → atomic write to DB
```

### Vision call specifics

- **Model:** Claude Sonnet 4.6 by default (~5× cheaper than Opus, sufficient for tables). Auto-retry with Opus 4.7 if >20% of fields fail validation.
- **Structured output:** template's field schema passed as `response_format` JSON schema. Vision returns strict-shape JSON.
- **Cost cap:** hard limit of $1/game in a settings table.

### Storage & audit

- Uploaded files: `backend/uploads/{game_id}/{timestamp}_{template}.{ext}`. Never deleted.
- New table `ExtractionRun`: `{run_id, game_id, template, source_file_path, raw_response_json, validated_at, committed_at}`. Lets us re-run extraction if prompts improve, without re-uploading.

### Component breakdown

Backend:
- `app/ingest/templates.py` — template definitions
- `app/ingest/pdf_parser.py` — pdfplumber wrappers per template
- `app/ingest/vision.py` — Claude API client + structured output
- `app/ingest/validators.py` — field-level validation
- `app/routers/ingest.py` — upload / extract / review / commit endpoints

Frontend:
- `/ingest/upload` — file picker + game picker
- `/ingest/review/{run_id}` — split-screen review UI
- Integrated into existing game entry as an alternative to manual entry

### API key handling

`ANTHROPIC_API_KEY` will be added to environment at build time. SDK dep (`anthropic>=0.40.0`) is already installed in `backend/requirements.txt` — key is deferred pending acquisition from the coach.

### Estimated effort

~2.5 weeks focused work:
- Templates + InStat PDF parsers: ~4 days
- Vision integration + 49ing templates: ~3 days
- Review UI (split-screen, edit, commit): ~4 days
- ExtractionRun table + audit + cost budget: ~2 days
- Real-game testing: ~2 days

---

## 5. Tier 1 quick wins

Ship on **existing 49ing schema** — no migration required. ~1 week total.

### 5.1 Position-aware comparisons

Each stat block on the player report gains two baselines:
- Team average (existing behavior)
- Position-group average (new)

Position groups:
- **F** — all forwards (default for most stats)
- **C** — centers (for faceoff-heavy stats)
- **W** — wingers
- **D** — defenders
- **G** — goalies

Per-stat cohort declared alongside the aggregation query. Cohort assignments:
- **C only:** Personal Draw Win%, On-Ice Team FO%
- **F (all forwards):** all other forward-relevant stats
- **D:** defender-relevant stats
- **G:** goalie stats

Delta shown as colored indicator: green = better than both baselines, yellow = better than one, red = below both.

**Effort:** ~1 day.

### 5.2 TOI trend flags

For each player per report window:

```
toi_L3   = mean TOI over last 3 games played
toi_L10  = mean TOI over last 10 games played
```

Flag conditions:
- `(toi_L3 - toi_L10) / toi_L10 > 0.10` → ⬆ "trending up" badge
- `(toi_L3 - toi_L10) / toi_L10 < -0.10` → ⬇ "trending down" badge
- Per-game: `game_toi / toi_L10 < 0.50` → "reduced role" badge on that game
- Per-game: `game_toi / toi_L10 > 1.50` → "expanded role" badge on that game

Presented as badges next to game rows in the game log; summary card at top of player report.

**Effort:** ~1–2 days.

### 5.3 Auto-flag engine

Generalization of the TOI trend logic to any stat, config-driven:

```python
FLAG_RULES = [
    Rule("toi_5v5",      window=3, baseline=10, z_threshold=1.0, label="TOI shift"),
    Rule("on_ice_xgf%",  window=3, baseline=10, z_threshold=1.0, label="xG% shift"),
    Rule("cf60",         window=3, baseline=10, z_threshold=1.0, label="Corsi shift"),
    Rule("xfsh%",        window=5, baseline=15, z_threshold=1.2, label="shot quality shift"),
    # extend as we learn what coaches watch
]
```

For each rule per player:
```
baseline_mean, baseline_std = TOI-weighted mean / stddev over last {baseline} games
window_mean = TOI-weighted mean over last {window} games
z = (window_mean - baseline_mean) / baseline_std
raise flag if |z| > threshold
```

Player report shows a compact "Flags this window" panel (0–3 badges, clickable to jump to stat block).

**Effort:** ~4 days (2 engine, 2 UI).

---

## 6. Tier 2 stats

Ship after schema migration + ingest pipeline. Uses new InStat fields. ~2 weeks total.

| Stat | Source | Notes |
|---|---|---|
| Contested Puck Win % | InStat only | Player report block with DZ/OZ/NZ split. |
| Impact Score (renamed Intrinsic +/-) | Both | Composite z-scores; see methodology §9. |
| Special Teams v2 | Both | Adds PP shots/min, PP OZ ratio, PK opp-breakouts rate. |
| Zone Entry Composition | InStat only | Per-player pass / stick / dump splits. |
| Turnover Location Ratio | InStat only | DZ loss share, OZ recovery share. |
| Danger-Zone Shot Share | Both | Player's HD shots ÷ team's HD shots. |

Full formulas in §9.

---

## 7. Tier 3 stats

Ship after Tier 2. ~1.5 weeks total.

| Stat | Source | Notes |
|---|---|---|
| Shot Threat by Scenario, All Players | InStat only | Filter chips on shots view: location, positional/counter-attack. |
| Defensive Disruption Index | Both (partial InStat) | Composite proxy; clearly labeled. |
| Goalie Stats + Limitations | Both | Team + per-goalie splits. Prominent caveats banner. |

---

## 8. Deferred / Not possible

### Deferred to Phase 2 (requires ingest pipeline)

- **Pass Connectivity Map** — heatmap visualization from `PlayerPassMatrix`. Line chemistry made visible.
- **Hit Engagement Profile** — from `PlayerHitMatrix`. Who initiates contact, receives, avoids.
- **Pass Isolation flag** — auto-detect players whose outgoing passes concentrate on 1–2 teammates.

Rationale: matrix tables (~200 non-zero cells/game each) are unreasonable to enter manually. Once ingest pipeline can populate them for free, all three visualizations become straightforward.

### Separate project (Phase 3)

- **In-app chatbot** — LLM-driven insight/query interface over the DB. Rough shape: Claude API with tool-use exposing DB query functions. Requires its own spec + plan. ~2–3 weeks. Blocked on all other stats being populated in DB first.

### Not possible with current data sources

- **Where the puck goes after a hit** — neither InStat nor 49ing tracks post-hit puck destination. InStat's hit matrix records who hit whom, but not the puck's next state. Would require third-party video review or an alternative data provider. **Cut from scope.**
- **True WOWY (with-or-without-you) / Rel. xGF%** — requires per-player off-ice splits that neither platform exposes.
- **Zone Start Ratio (ZSR)** — requires per-player OZ/DZ faceoff counts, not exposed by either platform.
- **Win probability trend by period** — requires cumulative period-by-period xGF/xGA breakouts, not exposed as readable numbers.

---

## 9. Stat methodology (canonical reference)

All new/refined stats documented in the format used by the existing MethodologyPage. This is the source of truth; the in-app page mirrors it (see §11).

### 9.1 Impact Score (replaces "intrinsic +/-")

> *"One number for how much this player is helping the team win, controlling for position."*

**Components** — each computed per game, z-normalized against season distribution within the player's position group:

```
z_xg     = z_position ( on-ice xGF60 - xGA60 )         [both sources]
z_terr   = z_position ( on-ice CF% )                   [both sources]
z_battle = z_position ( puck battle W% )               [InStat only, dropped if absent]
z_entry  = z_position ( (pass entries + stick entries) / total entries )
                                                        [InStat only, F/W only]
```

**Per-game:**
```
Impact_game = mean(available z-scores)
```

**Season aggregate (TOI-weighted):**
```
Impact_season = Σ(Impact_game_i × TOI_i) ÷ Σ(TOI_i)
```

Displayed clamped to [-3, +3]. Hover reveals component z-scores.

**Interpretation:** 0 = position average; +1 = top 16%; +2 = top 2.5%.

**Why over raw +/-:** raw +/- counts goals during 5v5, which is a tiny event count in a 28-game season and is heavily influenced by save quality and randomness. Impact Score uses shot-based signals (xG, Corsi, battle W%) with 10–50× the event volume per game and much faster stabilization.

**Limitations:**
- Not adjusted for teammate quality (no WOWY available).
- Not adjusted for opponent quality.
- Not adjusted for zone starts.
- Games with <5 min TOI excluded.
- Component availability depends on source; InStat weeks include battle/entry, 49ing weeks don't.
- First 8–10 games: interpret with caution.

### 9.2 Contested Puck Win % (coach ask #4)

> *"How often does she come out with the puck when it's up for grabs?"*

```
PB Win %  = Σ pb_won ÷ Σ pb_total          (all zones, all games)
PB DZ %   = Σ pb_won_dz ÷ Σ pb_total_dz
PB OZ %   = Σ pb_won_oz ÷ Σ pb_total_oz
PB NZ %   = Σ pb_won_nz ÷ Σ pb_total_nz
```

**Source:** InStat only.

**Interpretation:** varies by role. Defenders' DZ%, forwards' OZ% are most role-relevant.

**Limitations:** doesn't measure difficulty; open-ice vs board battles not split; N/A on 49ing weeks.

### 9.3 Special Teams v2 (coach ask #10)

**PP Shot Rate:**
```
PP Shots/min = total PP shots ÷ total PP minutes
```
Cleaner efficiency measure than raw shot count (confounded by opportunity count).

**PP OZ Retention:**
```
PP OZ Ratio = PP time in OZ ÷ total PP time
```
Answers whether the PP is generating chances or getting cleared.

**PK Containment:**
```
PK Opp Breakout Rate = opponent breakouts allowed ÷ number of PKs
```
Low = better; PK forecheck is disrupting entries.

**Source:** all three require InStat's PP/PK time-in-zone tracking.

### 9.4 Zone Entry Composition

> *"How does this player get into the offensive zone — carry, pass, or dump?"*

```
Entry Pass %   = entries via pass ÷ total entries
Entry Stick %  = entries via stickhandling ÷ total entries
Entry Dump %   = entries via dump-in ÷ total entries
```

**Source:** InStat only.

**Limitations:** doesn't measure post-entry outcome. A failed carry and a successful dump are weighted equally here.

### 9.5 Turnover Location Ratio

> *"Where does she lose the puck — where it's cheap, or where it hurts?"*

```
DZ Loss Share      = puck losses in DZ ÷ total puck losses
OZ Recovery Share  = puck recoveries in OZ ÷ total puck recoveries
```

**Interpretation:** OZ losses are largely acceptable (aggressive plays). DZ losses become chances against.

**Source:** InStat only.

### 9.6 Danger-Zone Shot Share

> *"Of the team's high-danger shots, how many is this player taking?"*

```
Danger Share % = player's shots from scoring-chance area ÷ team's shots from scoring-chance area
Danger Shots/60 = player's SCA shots × 60 ÷ TOI
```

InStat: uses "shots from scoring chance area." 49ing fallback: slot-zone shot count.

**Limitations:** doesn't sub-differentiate within the scoring-chance zone.

### 9.7 Auto-Flag Engine (§5.3)

For each `Rule(stat, window, baseline, z_threshold)`:

```
baseline_mean, baseline_std = TOI-weighted stats over last {baseline} games
window_mean = TOI-weighted mean over last {window} games
z = (window_mean - baseline_mean) ÷ baseline_std
flag if |z| > z_threshold
```

Requires ≥ `baseline` games of history; no flags fire in first ~10 games.

### 9.8 TOI Trend / Single-Game Outlier (§5.2)

**Rolling trend:**
```
pct_shift = (toi_L3 - toi_L10) ÷ toi_L10
```
Flag: `|pct_shift| > 0.10`.

**Single-game outlier:**
```
game_ratio = game_toi ÷ toi_L10
```
"Reduced role" flag: `game_ratio < 0.50`.
"Expanded role" flag: `game_ratio > 1.50`.

### 9.9 Defensive Disruption Index (coach ask #7)

> *"Composite estimate of a player's off-puck defensive activity."*

```
DDI/60 = (takeaways + shots blocked + DZ puck battles won) × 60 ÷ TOI
```

Season: TOI-weighted mean of per-game DDI/60.

**Labeled clearly as a composite proxy, not a direct measurement.** UI footnote: "Combines takeaways, blocks, and DZ puck battles won per 60 minutes. Approximation of off-puck defensive contribution; does not directly measure stick disruption."

**Source:** blocks + takeaways from either; DZ puck battles from InStat only (component drops to 0 on 49ing weeks — indicated in UI).

**Limitations:**
- Composite of three loosely related activities.
- Doesn't measure positioning or gap control.
- Rewards volume; penalizes minimal-mistake defenders.

### 9.10 Goalie Stats (coach ask #8)

**Per-goalie personal stats** (when goalie ≥3 starts):
```
SV%    = 1 - (goals against ÷ shots on goal against)
GA/60  = goals against × 60 ÷ TOI
HD SV% = 1 - (goals from HD area ÷ HD shots faced)    [InStat only]
```

**Persistent caveats banner:**
- SV% is noisy under 300 shots-against.
- HD SV% depends on InStat's shot-area classification (not video-reviewed).
- No opponent-adjustment.

**Limitations:**
- No rebound tracking.
- No GSAx (would need per-shot xG on shots faced).
- Screen/deflection context missing.

### 9.11 Shot Threat by Scenario, All Players (coach ask #3)

Per-player shots view gains filters:
- Location: slot / center / flank / blue line
- Context: positional attack / counter-attack ("off the rush")
- Strength: 5v5 / PP / SH

For each filter combination:
```
Shots/60    = filtered shots × 60 ÷ TOI at strength
On-Goal %   = shots on goal ÷ total shots
Shooting %  = goals ÷ shots on goal
```

**Source:** InStat only.

**Limitations:** shooting % needs 200+ shots to stabilize; most players won't reach that in a season.

### 9.12 Position-Aware Comparison (§5.1)

Not a stat — a comparison layer. For each stat:
```
Team baseline     = mean across all players in window (TOI-weighted for per-60 stats)
Position baseline = same, filtered to player's position group
```

Position group per stat configured in rules file alongside flag engine.

---

## 10. Roadmap

| Phase | Contents | Effort |
|---|---|---|
| **0** | Schema migration (option B) + aggregation layer + source flag | ~4 days |
| **1** | Tier 1 quick wins (position comparisons, TOI flags, auto-flag engine) — ships on current schema | ~1 week |
| **2** | Ingest pipeline (single-upload, PDF parser, Claude vision, review UI) | ~2.5 weeks |
| **3** | Tier 2 stats (contested puck, Impact Score, ST v2, entry composition, turnover ratio, danger share) | ~2 weeks |
| **4** | Tier 3 stats (shot threat, disruption index, goalie) | ~1.5 weeks |
| **5** | Matrix stats (pass connectivity, hit engagement, pass isolation) — depends on Phase 2 | ~1 week |
| **6** | Chatbot — own design pass | ~2–3 weeks |

**Rough total to feature-complete (excluding chatbot):** ~8 weeks. +2–3 weeks for chatbot.

Phase 1 runs first because it's independent of the schema migration; ships visible coach value before the bigger architectural work.

---

## 11. Documentation strategy

**Decision: Option A — update in-app methodology page now with all stats, "🚧 Coming soon" badges on unbuilt ones.**

- All ~20 new + refined stats added to `frontend/src/pages/MethodologyPage.tsx` immediately.
- `StatEntry` interface gains a `status?: 'planned' | 'partial'` field.
- Planned stats get a "🚧 Coming Soon" pill badge (like the existing "Not Tracked" pill).
- Global caveats section updated to note the 49ing vs InStat source split.
- Data-source note updated to cover both platforms.
- Each build phase removes the "Coming Soon" badge for stats it ships (part of the phase's task list).

This makes the methodology page a single source of truth from day one, so the coach can review formulas before implementation. Reject: option B (per-phase updates only) — leaves methodology fragmented; option C (existing stats only) — doesn't give the coach a preview.

---

## 12. Open items

- **Anthropic API key** — pending from coach. SDK installed, integration code will be built with a mocked/optional key.
- **Flag thresholds** — 10%/z=1.0 defaults are guesses. Expect to tune after Phase 1 with real data.
- **Single-game outlier thresholds** (50% / 150% of L10) — same, may tune.
- **Attack scenario coverage on 49ing** — currently only team-level xG per scenario is exposed. If 49ing ever exposes per-player scenario data, coach ask #3 becomes source-agnostic (currently InStat-only).
- **Second goalie or more** — the goalie personal-stat block assumes multiple goalies play. Verify roster reflects this before Phase 4.

---

## 13. Deferred — do not lose track of

1. `PlayerPassMatrix` and `PlayerHitMatrix` tables + downstream visualizations (§3, §8).
2. Chatbot design (§8).
3. Cost-budget UI (currently backend-only per §4).
