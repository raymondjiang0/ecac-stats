# ECAC Stats Expansion — Design Spec

**Date:** 2026-08-18 (amended 2026-09-01)
**Author:** Raymond Jiang (w/ Claude)
**Status:** Approved for planning

**2026-09-01 amendment:** Phase 2 ingest is descoped to InStat-PDF-only (no Claude vision, no paid API dependencies — this is a free tool). `PlayerPassMatrix` and `PlayerHitMatrix` tables move from Phase 5 into Phase 2 (PDF parsing extracts them at no marginal cost). Review UI simplified to editable form (no split-screen PDF preview). See §4 for revised ingest design.

---

## 1. Overview

The current tool tracks 5 team stats and 4 player stats sourced from 49ing's Data Cockpit, entered manually per game. The coaches have requested ~10 additional stats/features, several of which require raw data that 49ing does not expose but InStat does. Manual entry is also the largest ongoing pain point.

This spec covers:

1. Adopting InStat as a second, coexisting data source (schema-level).
2. Building an automated ingest pipeline that parses InStat match-report PDFs (deterministic `pdfplumber` — no external services, no cost). 49ing data stays manual.
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

### Matrix tables (added in Phase 2)

- **`PlayerPassMatrix`** — per-game, per-player-pair pass counts (from InStat page 10/18).
  Row shape: `(id, game_id, from_player_id, to_player_id, count)` with `UNIQUE(game_id, from_player_id, to_player_id)`.
- **`PlayerHitMatrix`** — per-game, per-player-pair hit counts (from InStat page 9/17).
  Row shape: `(id, game_id, from_player_id, to_player_id, delivered, received)` with `UNIQUE(game_id, from_player_id, to_player_id)`. Each PDF cell reports "delivered—received" so the pair carries both counts.

These enable pass connectivity and hit engagement stats. Originally deferred (unreasonable to enter manually at ~200 non-zero cells per game), now pulled forward: PDF parsing extracts them at no marginal cost. Downstream visualizations still land in Phase 5 (§8).

---

## 4. Ingest pipeline

### Goal

One-upload workflow: user uploads an InStat match-report PDF, system extracts every field it can find, user reviews the parsed values in an editable form, commits to DB. Manual per-field entry remains available for 49ing (still a web dashboard — no free extraction path) and for corrections.

### Scope: PDF-only, deterministic parsing

This is a free tool. Inputs are limited to InStat match-report PDFs (text-layer, not scanned). Parsing uses `pdfplumber` — deterministic, ~100% accurate on structured tables. Claude vision, screenshot ingest, cost budgets, and audit-driven re-extraction from the original design are out of scope.

If InStat's PDF layout changes in a future season, the parser gets updated; there is no vision fallback.

### PDF structure (empirically verified against the sample report)

Reports are 19 pages, symmetric per team. Page 1 is a TOC; page 2 is match-wide team stats; pages 3–10 are the visiting team; pages 11–18 are the home team; page 19 is a glossary. Section headers on each page carry the team name (`"PLAYERS' STATS: HARVARD CRIMSON"`), so pages route by header text rather than fixed page numbers.

### Templates we parse

| PDF section header | Template name | Target table(s) |
|---|---|---|
| `TEAMS STATS 2` (page 2) | `instat_team_stats` | `TeamGameStatsInStat` |
| `PLAYERS' STATS: <our team>` | `instat_players_main` | `PlayerGameStatsInStat` main fields (shots, corsi, hits, entries, turnovers) |
| `GAME TIME DISTRIBUTION: <our team>` | `instat_time_distribution` | `PlayerGameStats` toi/pp/sh — only when the game is InStat-sourced |
| `CHALLENGES: <our team>` | `instat_challenges` | `PlayerGameStatsInStat` pb_* fields |
| `HITS DISTRIBUTION: <our team>` | `instat_hit_matrix` | `PlayerHitMatrix` |
| `PASSES DISTRIBUTION: <our team>` | `instat_pass_matrix` | `PlayerPassMatrix` |

Skipped for now (documented, not parsed):
- Cover page (P1) — no data.
- Line combinations (P4/12) — no downstream consumer yet.
- Shots log (P6/14) — needed for Tier 3 shot-threat stats; parse in Phase 4.
- Challenge distribution matrix (P8/16) — no downstream consumer.
- Notes and glossary (P19) — no data.

Templates are Python callables in `app/ingest/templates.py`, each returning a structured dict. Adding a new template is a code change (parser + validator + target-table mapping), not a config edit.

### "Which team is ours" resolution

`settings.our_team_name` (initially a constant in `app/config.py`, e.g. `"HARVARD CRIMSON"`) drives which team's pages get parsed. The team-stats template (P2) uses this to pick the correct column from the side-by-side layout. If the parser can't find a matching team in the PDF, it returns a 400 with the team names it did find.

### Extraction flow

```
1. User uploads a PDF and picks a target game (existing game or new game inline).
2. Server parses the PDF: identifies all six templates by header, runs each parser.
3. Per-template validation:
     - jersey numbers match roster (fail: flag row, keep going)
     - numeric fields parse (fail: null the field, flag it)
     - "won—total" cells satisfy won ≤ total
4. Result stored as an IngestRun row: parsed_json + status = "pending_review".
5. Frontend fetches the IngestRun, shows an editable review form (one collapsible section per template, one row per player where applicable, validator warnings inline).
6. User edits any values, hits Commit → server writes all rows atomically; IngestRun.status → "committed".
7. Discard → server soft-deletes the IngestRun.
```

No split-screen PDF viewer. Coach has the source PDF locally; if they need to double-check a value, they open it in a PDF viewer.

### Storage

- Uploaded PDFs: `backend/uploads/ingest/{ingest_run_id}.pdf`. Retained so a future parser improvement can re-run against them without a fresh upload.
- New table `IngestRun`: `(id, game_id, filename, uploaded_at, parsed_json TEXT, status, committed_at NULL, error TEXT NULL)`. Simple audit + re-parseability.

### Component breakdown

Backend:
- `app/ingest/pdf_parser.py` — one function per template
- `app/ingest/templates.py` — template registry: name → parser fn + target table + validator
- `app/ingest/validators.py` — jersey-vs-roster, numeric parse, won ≤ total checks
- `app/ingest/commit.py` — per-template DB writers (transactional)
- `app/routers/ingest.py` — upload, preview, commit, discard endpoints
- `app/models.py` — `IngestRun`, `PlayerHitMatrix`, `PlayerPassMatrix`
- `backend/migrate_v6.py` — new tables

Frontend:
- `/ingest` page — file input + game picker + submit
- `/ingest/{id}` review view — collapsible sections per template, editable fields, commit / discard buttons

### Estimated effort

~1–1.5 weeks focused work:
- Templates + PDF parsers + validators: ~4 days
- Schema + migration + endpoints: ~1 day
- Review UI: ~2 days
- Fixture-based tests + real-game verification: ~1 day

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

| Phase | Contents | Effort | Status |
|---|---|---|---|
| **0** | Schema migration (option B) + aggregation layer + source flag | ~4 days | ✅ shipped |
| **1** | Tier 1 quick wins (position comparisons, TOI flags, auto-flag engine) | ~1 week | ✅ shipped |
| **2** | InStat PDF ingest — 6 templates + `PlayerHitMatrix` / `PlayerPassMatrix` tables + review UI | ~1–1.5 weeks | next |
| **3** | Tier 2 stats (contested puck, Impact Score, ST v2, entry composition, turnover ratio, danger share) | ~2 weeks | after Phase 2 |
| **4** | Tier 3 stats (shot threat by scenario, disruption index, goalie) — includes InStat shots-log parser | ~1.5 weeks | after Phase 3 |
| **5** | Matrix visualizations (pass connectivity map, hit engagement profile, pass isolation flag) — matrix data already stored by Phase 2 | ~1 week | after Phase 4 |
| **6** | Chatbot — own design pass | ~2–3 weeks | independent |

**Rough total to feature-complete (excluding chatbot):** ~6.5 weeks remaining. +2–3 weeks for chatbot.

Phases 0 and 1 shipped in parallel. Phase 1 was independent of the schema migration and shipped first; Phase 0 landed alongside without changing any computed values.

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

- **`our_team_name` configuration** — hardcoded constant initially (§4). Move to a settings table if we ever track more than one team.
- **Flag thresholds** — 10%/z=1.0 defaults are guesses. Expect to tune after Phase 1 with real data.
- **Single-game outlier thresholds** (50% / 150% of L10) — same, may tune.
- **Attack scenario coverage on 49ing** — currently only team-level xG per scenario is exposed. If 49ing ever exposes per-player scenario data, coach ask #3 becomes source-agnostic (currently InStat-only).
- **Second goalie or more** — the goalie personal-stat block assumes multiple goalies play. Verify roster reflects this before Phase 4.
- **InStat template drift** — if InStat changes their PDF layout between seasons, all six parsers may need updates. Golden-fixture tests will catch this on the first game of a new season.

---

## 13. Deferred — do not lose track of

1. Pass connectivity / hit engagement visualizations (Phase 5). Matrix data now stored by Phase 2; only the UI remains.
2. InStat shots-log parser + shot-threat-by-scenario stats (Phase 4 / §9.11).
3. Chatbot design (§8, Phase 6).
